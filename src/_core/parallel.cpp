#include "parallel.hpp"
#include "runtime.hpp"
// gil_macros.hpp and policy_dispatch.hpp are Phase 3 scaffolding (C++ dispatch
// path); not used by the current Python-dispatcher implementation.

#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/string.h>
#include <hpx/algorithm.hpp>
#include <hpx/execution.hpp>

// Python.h must come after HPX/nanobind headers to avoid macro conflicts.
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <atomic>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <vector>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::parallel {

namespace {

void ensure_runtime() {
    if (!hpyx::runtime::runtime_is_running()) {
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    }
}

// kind constants mirror execution.py _KIND_* values
constexpr int KIND_SEQ      = 0;
constexpr int KIND_PAR      = 1;
constexpr int KIND_PAR_UNSEQ = 2;
// KIND_UNSEQ = 3 maps to seq execution at the C++ layer

}  // namespace

// Sequential for_loop — called from the main Python thread with GIL held.
// The Python wrapper dispatches par/par_unseq policies via hpyx.async_
// to avoid free-threaded Python thread-state races in HPX's work-stealing.
// Policy parameters are enforced by the Python dispatcher; C++ always runs seq.
static void parallel_for_loop(
    int /*kind*/, bool /*task_flag*/, int /*chunk*/, std::size_t /*chunk_size*/,
    std::int64_t first,
    std::int64_t last,
    nb::callable body)
{
    ensure_runtime();
    for (std::int64_t i = first; i < last; ++i) {
        body(nb::int_(i));
    }
}

// Sequential for_each — iterates and calls fn(item) for each element.
// Policy parameters are enforced by the Python dispatcher; C++ always runs seq.
static void parallel_for_each(
    int /*kind*/, bool /*task_flag*/, int /*chunk*/, std::size_t /*chunk_size*/,
    nb::iterable iterable,
    nb::callable body)
{
    ensure_runtime();
    for (auto item : iterable) {
        body(item);
    }
}

// sort_impl / stable_sort_impl
//
// Implements hpx::sort and hpx::stable_sort over a Python list of arbitrary
// objects.  Comparison requires the GIL, so hpx::execution::par dispatches
// HPX's parallel sort infrastructure but comparisons serialize through GIL.
// The real throughput gain for pure-C++ numeric types lives in hpyx.kernels.
//
// Algorithm:
//   1. Snapshot borrowed PyObject* pointers from data (list stays alive).
//   2. If key_fn is provided, compute a parallel key array (new references).
//   3. Sort a std::vector<size_t> of indices using the computed comparator,
//      dispatching to hpx::sort (par) or hpx::stable_sort (par / seq).
//   4. Build and return the output list in sorted-index order.
//   5. Comparator errors are captured via an atomic flag; first failure
//      raises TypeError after the sort completes.
//
// GIL contract: GIL is held on entry.  Released before hpx::sort call via
// nb::gil_scoped_release; comparator re-acquires per comparison via
// PyGILState_Ensure/Release.
//
// Exception contract: when a comparator fails, the original Python exception
// is captured via PyErr_GetRaisedException and re-raised after the sort
// completes.  Subsequent comparator failures (after the first) are cleared.
// The original exception type and message are always preserved.
static nb::list sort_impl(
    int kind, bool /*task_flag*/, int /*chunk*/, std::size_t /*chunk_size*/,
    nb::list data, nb::handle key_fn, bool reverse, bool stable)
{
    ensure_runtime();

    auto n = static_cast<std::size_t>(PyList_GET_SIZE(data.ptr()));
    if (n <= 1) return data;

    // Snapshot borrowed item refs; list stays alive for the duration.
    std::vector<PyObject*> items(n);
    for (std::size_t i = 0; i < n; ++i)
        items[i] = PyList_GET_ITEM(data.ptr(), static_cast<Py_ssize_t>(i));

    // Compute key objects (new references); must happen with GIL held.
    const bool has_key = !key_fn.is_none();
    std::vector<PyObject*> keys;
    if (has_key) {
        keys.resize(n);
        for (std::size_t i = 0; i < n; ++i) {
            PyObject* k = PyObject_CallFunctionObjArgs(key_fn.ptr(), items[i], nullptr);
            if (!k) {
                // Cleanup keys computed so far then propagate.
                for (std::size_t j = 0; j < i; ++j) Py_DECREF(keys[j]);
                throw nb::python_error();
            }
            keys[i] = k;
        }
    }

    // Index vector to sort; avoids moving Python objects.
    std::vector<std::size_t> idx(n);
    std::iota(idx.begin(), idx.end(), 0);

    // Error flag: set inside comparator when PyObject_RichCompareBool fails.
    // Comparisons serialize through the GIL so non-atomic access is safe in
    // practice, but atomic avoids UB under the C++ memory model.
    std::atomic<bool> cmp_error{false};
    // Saved exception from first comparator failure; re-raised after the sort.
    // Written only once (guarded by cmp_error exchange); read after HPX joins.
    PyObject* saved_exc = nullptr;

    auto cmp = [&](std::size_t a, std::size_t b) -> bool {
        if (cmp_error.load(std::memory_order_relaxed)) return a < b;
        PyGILState_STATE gs = PyGILState_Ensure();
        PyObject* pa = has_key ? keys[a] : items[a];
        PyObject* pb = has_key ? keys[b] : items[b];
        int r = reverse
            ? PyObject_RichCompareBool(pb, pa, Py_LT)  // b < a → descending
            : PyObject_RichCompareBool(pa, pb, Py_LT); // a < b → ascending
        if (r < 0) {
            if (!cmp_error.exchange(true, std::memory_order_relaxed)) {
                // First failure: steal the exception so we can re-raise it
                // with its original type and message intact.
                saved_exc = PyErr_GetRaisedException();
            } else {
                PyErr_Clear();
            }
            PyGILState_Release(gs);
            return a < b;  // dummy ordering; result discarded after error
        }
        PyGILState_Release(gs);
        return r > 0;
    };

    // Release GIL before entering HPX; comparator re-acquires per comparison.
    const bool use_par = (kind == KIND_PAR || kind == KIND_PAR_UNSEQ);
    try {
        nb::gil_scoped_release release;
        if (stable) {
            if (use_par)
                hpx::stable_sort(hpx::execution::par, idx.begin(), idx.end(), cmp);
            else
                hpx::stable_sort(hpx::execution::seq, idx.begin(), idx.end(), cmp);
        } else {
            if (use_par)
                hpx::sort(hpx::execution::par, idx.begin(), idx.end(), cmp);
            else
                hpx::sort(hpx::execution::seq, idx.begin(), idx.end(), cmp);
        }
    } catch (...) {
        if (has_key) for (std::size_t i = 0; i < n; ++i) Py_XDECREF(keys[i]);
        Py_XDECREF(saved_exc);  // release saved exc if HPX threw independently
        throw;
    }

    if (has_key) for (std::size_t i = 0; i < n; ++i) Py_DECREF(keys[i]);

    if (cmp_error.load()) {
        PyErr_SetRaisedException(saved_exc);  // steals ref; restores original exception
        throw nb::python_error();
    }

    // Build the output list.
    PyObject* out_raw = PyList_New(static_cast<Py_ssize_t>(n));
    if (!out_raw) throw nb::python_error();
    for (std::size_t i = 0; i < n; ++i)
        PyList_SET_ITEM(out_raw, static_cast<Py_ssize_t>(i), Py_NewRef(items[idx[i]]));
    return nb::steal<nb::list>(out_raw);
}

void register_bindings(nb::module_& m) {
    m.def("for_loop", &parallel_for_loop,
          "kind"_a, "task"_a, "chunk"_a, "chunk_size"_a,
          "first"_a, "last"_a, "body"_a);
    m.def("for_each", &parallel_for_each,
          "kind"_a, "task"_a, "chunk"_a, "chunk_size"_a,
          "iterable"_a, "body"_a);
    m.def("sort", &sort_impl,
          "kind"_a, "task"_a, "chunk"_a, "chunk_size"_a,
          "data"_a, "key"_a.none(), "reverse"_a, "stable"_a);
}

}  // namespace hpyx::parallel
