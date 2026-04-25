#include "futures.hpp"
#include "runtime.hpp"

#include <hpx/async.hpp>
#include <hpx/async_combinators/when_all.hpp>
#include <hpx/async_combinators/when_any.hpp>
#include <hpx/future.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

// Python.h must come last to avoid macro conflicts with HPX/Boost.
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <chrono>
#include <cstdlib>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::futures {

// ---- GILDecref implementation ----

void GILDecref::operator()(PyObject* p) const noexcept {
    if (!p) return;
    PyGILState_STATE gs = PyGILState_Ensure();
    Py_DECREF(p);
    PyGILState_Release(gs);
}

namespace {

// Wrap a PyObject* in a GIL-safe shared_ptr. Steals the reference (no INCREF).
// Caller must hold the GIL when calling.
PyPayload steal_to_payload(PyObject* obj) {
    return PyPayload(obj, GILDecref{});
}

// ---- Sentinel layout for cross-thread Python exception transport ----
//
// When the user's callable raises a Python exception, we cannot let
// nb::python_error propagate through HPX's exception_ptr machinery: the
// underlying PyObject* references are GIL-thread-local and HPX may
// copy/move the exception on a thread without an attached interpreter.
//
// Instead we box the exception into a 4-tuple:
//     ("__hpyx_exc__", exc_type, exc_value, exc_tb)
// stored as a PyPayload. result() / exception() detect the sentinel and
// re-raise / return the value when the GIL is held.
const char* kExcTag = "__hpyx_exc__";

// Box the *currently set* Python exception into a sentinel payload.
// Clears Python error state. GIL must be held.
PyPayload box_current_exception() {
    PyObject *type_raw = nullptr, *val_raw = nullptr, *tb_raw = nullptr;
    PyErr_Fetch(&type_raw, &val_raw, &tb_raw);
    PyErr_NormalizeException(&type_raw, &val_raw, &tb_raw);
    if (!type_raw) type_raw = Py_NewRef(Py_None);
    if (!val_raw)  val_raw  = Py_NewRef(Py_None);
    if (!tb_raw)   tb_raw   = Py_NewRef(Py_None);
    PyErr_Clear();

    PyObject* tag = PyUnicode_FromString(kExcTag);
    PyObject* tup = PyTuple_New(4);
    if (!tag || !tup) {
        Py_XDECREF(tag);
        Py_XDECREF(tup);
        Py_XDECREF(type_raw);
        Py_XDECREF(val_raw);
        Py_XDECREF(tb_raw);
        return {};
    }
    PyTuple_SET_ITEM(tup, 0, tag);       // steals
    PyTuple_SET_ITEM(tup, 1, type_raw);  // steals
    PyTuple_SET_ITEM(tup, 2, val_raw);   // steals
    PyTuple_SET_ITEM(tup, 3, tb_raw);    // steals
    return steal_to_payload(tup);
}

// Detect a sentinel payload. If `out_value` is non-null, fills it with
// the exc_value (borrowed reference) when the sentinel matches.
bool is_exc_sentinel(PyObject* raw, PyObject** out_value = nullptr) {
    if (!raw || !PyTuple_Check(raw) || PyTuple_GET_SIZE(raw) != 4)
        return false;
    PyObject* tag = PyTuple_GET_ITEM(raw, 0);
    if (!PyUnicode_Check(tag)) return false;
    const char* s = PyUnicode_AsUTF8(tag);
    if (!s || std::string(s) != kExcTag) return false;
    if (out_value) *out_value = PyTuple_GET_ITEM(raw, 2);  // borrowed
    return true;
}

// Re-raise the boxed Python exception on the current thread (GIL held).
[[noreturn]] void reraise_sentinel(PyObject* tup) {
    PyObject* val = PyTuple_GET_ITEM(tup, 2);  // borrowed
    if (!val || val == Py_None) {
        throw std::runtime_error("hpyx: stored exception has no value");
    }
    Py_INCREF(val);
    PyErr_SetRaisedException(val);  // steals
    throw nb::python_error();
}

// Wait on a shared_future<PyPayload> with optional timeout (GIL released
// during the wait). Returns false if timed out, true if ready.
bool wait_payload(hpx::shared_future<PyPayload> const& fut,
                  std::optional<double> timeout) {
    nb::gil_scoped_release release;
    if (timeout.has_value()) {
        auto st = fut.wait_for(std::chrono::duration<double>(*timeout));
        return (st != hpx::future_status::timeout);
    }
    fut.wait();
    return true;
}

[[noreturn]] void raise_timeout() {
    nb::object cls = nb::module_::import_("concurrent.futures").attr("TimeoutError");
    PyErr_SetNone(cls.ptr());
    throw nb::python_error();
}

// Read HPYX_ASYNC_MODE env to decide launch::async vs launch::deferred.
// Default is "async"; "deferred" is the v0.x rollback per spec risk #1.
hpx::launch resolve_launch_policy() {
    const char* mode = std::getenv("HPYX_ASYNC_MODE");
    if (mode && std::string(mode) == "deferred")
        return hpx::launch::deferred;
    return hpx::launch::async;
}

}  // namespace

// ---- HPXFuture methods ----

HPXFuture::HPXFuture(hpx::shared_future<PyPayload> fut)
    : fut_(std::move(fut)) {}

nb::object HPXFuture::result(std::optional<double> timeout) {
    if (!fut_.valid())
        throw std::runtime_error("Future is invalid (default-constructed or moved-from)");
    if (!wait_payload(fut_, timeout)) raise_timeout();

    // GIL is held here (release in wait_payload destructed and reacquired).
    const PyPayload& payload = fut_.get();
    if (!payload) return nb::none();
    PyObject* raw = payload.get();
    if (is_exc_sentinel(raw)) {
        reraise_sentinel(raw);
    }
    return nb::borrow(raw);
}

nb::object HPXFuture::exception(std::optional<double> timeout) {
    if (!fut_.valid()) return nb::none();
    if (!wait_payload(fut_, timeout)) raise_timeout();

    const PyPayload& payload = fut_.get();
    if (!payload) return nb::none();
    PyObject* raw = payload.get();
    PyObject* exc_value = nullptr;
    if (is_exc_sentinel(raw, &exc_value)) {
        return nb::borrow(exc_value);
    }
    return nb::none();
}

bool HPXFuture::done() const {
    if (!fut_.valid()) return true;
    return fut_.is_ready();
}

bool HPXFuture::running() const {
    return running_->load() && !done();
}

bool HPXFuture::cancelled() const {
    return cancelled_->load();
}

bool HPXFuture::cancel() {
    // Per spec §5.4: only cancels if not started.
    if (running_->load() || done()) return false;
    bool expected = false;
    return cancelled_->compare_exchange_strong(expected, true);
}

void HPXFuture::add_done_callback(nb::callable cb) {
    if (!fut_.valid()) {
        // Already invalid; invoke immediately with the current Future.
        try { cb(nb::cast(*this)); } catch (...) {}
        return;
    }
    // Capture cb in a GIL-safe wrapper so the lambda can sit in HPX state
    // without an nb::callable destructor running off-GIL.
    Py_INCREF(cb.ptr());
    auto safe_cb = std::shared_ptr<PyObject>(cb.ptr(), GILDecref{});
    auto captured = *this;  // shared_future copy is cheap
    fut_.then([safe_cb, captured](hpx::shared_future<PyPayload> const&) mutable {
        PyGILState_STATE gs = PyGILState_Ensure();
        try {
            nb::callable fn = nb::borrow<nb::callable>(safe_cb.get());
            fn(nb::cast(captured));
        } catch (nb::python_error& e) {
            // concurrent.futures.Future swallows callback errors via
            // sys.unraisablehook (defaults to stderr).
            e.discard_as_unraisable("hpyx.Future callback");
        } catch (...) {
            PyErr_Clear();
        }
        PyGILState_Release(gs);
    });
}

HPXFuture HPXFuture::then(nb::callable cb) {
    if (!fut_.valid())
        throw std::runtime_error("Cannot call .then() on an invalid future");
    Py_INCREF(cb.ptr());
    auto safe_cb = std::shared_ptr<PyObject>(cb.ptr(), GILDecref{});
    auto new_fut = fut_.then(
        [safe_cb](hpx::shared_future<PyPayload> prev) -> PyPayload {
            PyGILState_STATE gs = PyGILState_Ensure();
            PyPayload result;
            try {
                const PyPayload& payload = prev.get();
                PyObject* raw = payload ? payload.get() : nullptr;
                if (!raw || is_exc_sentinel(raw)) {
                    // Propagate upstream payload (or null) unchanged.
                    result = payload;
                } else {
                    nb::callable fn = nb::borrow<nb::callable>(safe_cb.get());
                    nb::object arg  = nb::borrow(raw);
                    nb::object ret  = fn(arg);
                    PyObject* ptr   = ret.ptr();
                    Py_INCREF(ptr);  // payload owns one ref; ret releases its own
                    result = steal_to_payload(ptr);
                }
            } catch (nb::python_error& e) {
                e.restore();
                result = box_current_exception();
            } catch (std::exception& e) {
                PyErr_SetString(PyExc_RuntimeError, e.what());
                result = box_current_exception();
            }
            PyGILState_Release(gs);
            return result;
        }).share();
    return HPXFuture(std::move(new_fut));
}

HPXFuture HPXFuture::share() const {
    return HPXFuture(fut_);  // already shared internally
}

// ---- Free functions ----

namespace {

HPXFuture async_submit(nb::callable fn, nb::handle call_args, nb::handle call_kwargs) {
    if (!hpyx::runtime::runtime_is_running())
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    // call_args and call_kwargs are nb::handle (not nb::tuple/dict) to avoid
    // nanobind's auto-collection of multiple positional nb::object/handle
    // params into **kwargs in the function signature display. The runtime
    // PyTuple_Check / PyDict_Check below validates the actual types.
    if (!PyTuple_Check(call_args.ptr()))
        throw std::runtime_error("async_submit: args must be a tuple");
    if (!PyDict_Check(call_kwargs.ptr()))
        throw std::runtime_error("async_submit: kwargs must be a dict");

    // Wrap fn/args/kwargs in GIL-safe shared_ptrs so the lambda's captures
    // can be destroyed on an HPX worker thread without holding the GIL.
    Py_INCREF(fn.ptr());
    Py_INCREF(call_args.ptr());
    Py_INCREF(call_kwargs.ptr());
    auto safe_fn   = std::shared_ptr<PyObject>(fn.ptr(),          GILDecref{});
    auto safe_args = std::shared_ptr<PyObject>(call_args.ptr(),   GILDecref{});
    auto safe_kw   = std::shared_ptr<PyObject>(call_kwargs.ptr(), GILDecref{});

    auto policy = resolve_launch_policy();
    nb::gil_scoped_release release;
    auto fut = hpx::async(policy,
        [safe_fn, safe_args, safe_kw]() -> PyPayload {
            // Attach this HPX worker thread to the Python interpreter.
            PyGILState_STATE gs = PyGILState_Ensure();
            PyPayload result;
            try {
                // Call fn(*args, **kwargs) via the C API.
                PyObject* raw = PyObject_Call(
                    safe_fn.get(), safe_args.get(), safe_kw.get());
                if (!raw) {
                    // Python exception is set; box and clear it.
                    result = box_current_exception();
                } else {
                    result = steal_to_payload(raw);  // payload owns the ref
                }
            } catch (nb::python_error& e) {
                e.restore();
                result = box_current_exception();
            } catch (std::exception& e) {
                PyErr_SetString(PyExc_RuntimeError, e.what());
                result = box_current_exception();
            } catch (...) {
                PyErr_SetString(PyExc_RuntimeError, "unknown C++ exception");
                result = box_current_exception();
            }
            PyGILState_Release(gs);
            return result;
        }).share();
    return HPXFuture(std::move(fut));
}

HPXFuture ready_future(nb::object value) {
    PyObject* ptr = value.ptr();
    Py_INCREF(ptr);
    auto payload = steal_to_payload(ptr);
    auto fut = hpx::make_ready_future<PyPayload>(std::move(payload)).share();
    return HPXFuture(std::move(fut));
}

// ---- Composition helpers (when_all / when_any / dataflow / shared_future) ----

// Extract the underlying shared_futures from a vector of HPXFuture wrappers.
std::vector<hpx::shared_future<PyPayload>> extract_raw(
    std::vector<HPXFuture> const& inputs) {
    std::vector<hpx::shared_future<PyPayload>> out;
    out.reserve(inputs.size());
    for (auto const& f : inputs) out.push_back(f.raw());
    return out;
}

HPXFuture when_all_impl(std::vector<HPXFuture> inputs) {
    auto raws = extract_raw(inputs);
    auto fut = hpx::when_all(std::move(raws)).then(
        [](hpx::future<std::vector<hpx::shared_future<PyPayload>>> f)
            -> PyPayload {
            auto vec = f.get();
            PyGILState_STATE gs = PyGILState_Ensure();
            PyPayload result;
            try {
                // Per spec §5.2: first-to-fail wins. Surface the first
                // upstream sentinel without aggregating siblings.
                for (auto const& sf : vec) {
                    PyPayload const& p = sf.get();
                    PyObject* raw = p ? p.get() : nullptr;
                    if (is_exc_sentinel(raw)) {
                        result = p;
                        PyGILState_Release(gs);
                        return result;
                    }
                }
                PyObject* tup =
                    PyTuple_New(static_cast<Py_ssize_t>(vec.size()));
                if (!tup) {
                    result = box_current_exception();
                    PyGILState_Release(gs);
                    return result;
                }
                for (std::size_t i = 0; i < vec.size(); ++i) {
                    PyPayload const& p = vec[i].get();
                    PyObject* raw = p ? p.get() : Py_None;
                    Py_INCREF(raw);
                    PyTuple_SET_ITEM(tup, static_cast<Py_ssize_t>(i), raw);
                }
                result = steal_to_payload(tup);
            } catch (nb::python_error& e) {
                e.restore();
                result = box_current_exception();
            } catch (std::exception& e) {
                PyErr_SetString(PyExc_RuntimeError, e.what());
                result = box_current_exception();
            } catch (...) {
                PyErr_SetString(PyExc_RuntimeError,
                                "unknown C++ exception in when_all");
                result = box_current_exception();
            }
            PyGILState_Release(gs);
            return result;
        }).share();
    return HPXFuture(std::move(fut));
}

HPXFuture when_any_impl(std::vector<HPXFuture> inputs) {
    auto raws = extract_raw(inputs);
    // Capture the original wrappers so we can return them in the result tuple.
    auto captured =
        std::make_shared<std::vector<HPXFuture>>(std::move(inputs));
    auto fut = hpx::when_any(std::move(raws)).then(
        [captured](hpx::future<hpx::when_any_result<
                       std::vector<hpx::shared_future<PyPayload>>>> f)
            -> PyPayload {
            auto wa = f.get();
            std::size_t idx = wa.index;
            PyGILState_STATE gs = PyGILState_Ensure();
            PyPayload result;
            try {
                PyObject* lst =
                    PyList_New(static_cast<Py_ssize_t>(captured->size()));
                if (!lst) {
                    result = box_current_exception();
                    PyGILState_Release(gs);
                    return result;
                }
                for (std::size_t i = 0; i < captured->size(); ++i) {
                    nb::object obj = nb::cast((*captured)[i]);
                    PyObject* ptr = obj.ptr();
                    Py_INCREF(ptr);
                    PyList_SET_ITEM(lst, static_cast<Py_ssize_t>(i), ptr);
                }
                PyObject* idx_obj = PyLong_FromSize_t(idx);
                if (!idx_obj) {
                    Py_DECREF(lst);
                    result = box_current_exception();
                    PyGILState_Release(gs);
                    return result;
                }
                PyObject* tup = PyTuple_New(2);
                if (!tup) {
                    Py_DECREF(idx_obj);
                    Py_DECREF(lst);
                    result = box_current_exception();
                    PyGILState_Release(gs);
                    return result;
                }
                PyTuple_SET_ITEM(tup, 0, idx_obj);  // steals
                PyTuple_SET_ITEM(tup, 1, lst);      // steals
                result = steal_to_payload(tup);
            } catch (nb::python_error& e) {
                e.restore();
                result = box_current_exception();
            } catch (std::exception& e) {
                PyErr_SetString(PyExc_RuntimeError, e.what());
                result = box_current_exception();
            } catch (...) {
                PyErr_SetString(PyExc_RuntimeError,
                                "unknown C++ exception in when_any");
                result = box_current_exception();
            }
            PyGILState_Release(gs);
            return result;
        }).share();
    return HPXFuture(std::move(fut));
}

HPXFuture dataflow_impl(nb::callable fn,
                        std::vector<HPXFuture> inputs,
                        nb::handle kwargs) {
    if (!hpyx::runtime::runtime_is_running())
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    if (!PyDict_Check(kwargs.ptr()))
        throw std::runtime_error("dataflow: kwargs must be a dict");
    auto raws = extract_raw(inputs);
    Py_INCREF(fn.ptr());
    Py_INCREF(kwargs.ptr());
    auto safe_fn = std::shared_ptr<PyObject>(fn.ptr(), GILDecref{});
    auto safe_kw = std::shared_ptr<PyObject>(kwargs.ptr(), GILDecref{});
    auto fut = hpx::when_all(std::move(raws)).then(
        [safe_fn, safe_kw](
            hpx::future<std::vector<hpx::shared_future<PyPayload>>> f)
            -> PyPayload {
            auto vec = f.get();
            PyGILState_STATE gs = PyGILState_Ensure();
            PyPayload result;
            try {
                // Propagate first upstream exception without invoking fn.
                for (auto const& sf : vec) {
                    PyPayload const& p = sf.get();
                    PyObject* raw = p ? p.get() : nullptr;
                    if (is_exc_sentinel(raw)) {
                        result = p;
                        PyGILState_Release(gs);
                        return result;
                    }
                }
                PyObject* args =
                    PyTuple_New(static_cast<Py_ssize_t>(vec.size()));
                if (!args) {
                    result = box_current_exception();
                    PyGILState_Release(gs);
                    return result;
                }
                for (std::size_t i = 0; i < vec.size(); ++i) {
                    PyPayload const& p = vec[i].get();
                    PyObject* raw = p ? p.get() : Py_None;
                    Py_INCREF(raw);
                    PyTuple_SET_ITEM(args, static_cast<Py_ssize_t>(i), raw);
                }
                PyObject* raw =
                    PyObject_Call(safe_fn.get(), args, safe_kw.get());
                Py_DECREF(args);
                if (!raw) {
                    result = box_current_exception();
                } else {
                    result = steal_to_payload(raw);
                }
            } catch (nb::python_error& e) {
                e.restore();
                result = box_current_exception();
            } catch (std::exception& e) {
                PyErr_SetString(PyExc_RuntimeError, e.what());
                result = box_current_exception();
            } catch (...) {
                PyErr_SetString(PyExc_RuntimeError,
                                "unknown C++ exception in dataflow");
                result = box_current_exception();
            }
            PyGILState_Release(gs);
            return result;
        }).share();
    return HPXFuture(std::move(fut));
}

HPXFuture shared_future_impl(HPXFuture input) {
    // No-op: HPXFuture already wraps hpx::shared_future. Returning .share()
    // yields a wrapper over the same underlying shared state, which is what
    // the spec contract calls for.
    return input.share();
}

}  // namespace

void register_bindings(nb::module_& m) {
    nb::class_<HPXFuture>(m, "HPXFuture")
        .def(nb::init<>())
        .def("result", &HPXFuture::result,
             "timeout"_a = nb::none(),
             "Block until the future is done; return the result or raise its exception.")
        .def("exception", &HPXFuture::exception,
             "timeout"_a = nb::none(),
             "Block until done; return the exception or None.")
        .def("done", &HPXFuture::done)
        .def("running", &HPXFuture::running)
        .def("cancelled", &HPXFuture::cancelled)
        .def("cancel", &HPXFuture::cancel)
        .def("add_done_callback", &HPXFuture::add_done_callback, "callback"_a)
        .def("then", &HPXFuture::then, "callback"_a,
             "Attach a continuation; return a new Future for the continuation's result.")
        .def("share", &HPXFuture::share);

    m.def("async_submit", &async_submit,
          "Submit a callable to HPX; return a Future for its result.");
    m.def("ready_future", &ready_future, "value"_a,
          "Return an already-completed future wrapping `value`.");
    m.def("when_all", &when_all_impl, "inputs"_a,
          "Return a future whose result is a tuple of all input results "
          "in input order. First-to-fail wins per spec §5.2.");
    m.def("when_any", &when_any_impl, "inputs"_a,
          "Return a future whose result is (index, [HPXFuture, ...]) where "
          "`index` is the position of the first completed input.");
    m.def("dataflow", &dataflow_impl,
          "fn"_a, "inputs"_a, "kwargs"_a = nb::dict(),
          "Wait for all inputs, then call fn(*results, **kwargs) on an HPX "
          "worker. Upstream exceptions short-circuit fn.");
    m.def("shared_future", &shared_future_impl, "future"_a,
          "Return a shared-future view of `future`. HPXFuture is already "
          "shared internally, so this is effectively a no-op pass-through.");
}

}  // namespace hpyx::futures
