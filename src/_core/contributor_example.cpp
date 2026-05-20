// Worked example for docs/adding-a-binding.md. Adds a minimal parallel
// algorithm (sum_of_squares, callback track) and a minimal kernel
// (l2_norm_squared, kernel track) so contributors have a reference they can
// read end-to-end. Built by default in development; excluded from release
// wheels via the HPYX_BUILD_CONTRIBUTOR_EXAMPLE CMake flag.

#include "contributor_example.hpp"
#include "gil_macros.hpp"
#include "runtime.hpp"

#include <hpx/numeric.hpp>
#include <hpx/execution.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/vector.h>

#include <cstddef>
#include <cstdint>
#include <functional>
#include <stdexcept>
#include <vector>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::contrib {

namespace {

void ensure_runtime() {
    if (!hpyx::runtime::runtime_is_running()) {
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    }
}

}  // namespace

// Callback-track example: sum of squares via transform_reduce.
// Follows the same calling convention as parallel.cpp — individual policy
// fields so the Python wrapper can use _token_fields(). The C++ layer always
// runs hpx::execution::par; task dispatch is handled at the Python level.
static double sum_of_squares(
    int /*kind*/, bool /*task_flag*/, int /*chunk*/, std::size_t /*chunk_size*/,
    nb::iterable src_it)
{
    ensure_runtime();
    std::vector<double> src;
    for (auto item : src_it) {
        src.push_back(nb::cast<double>(item));
    }
    HPYX_KERNEL_NOGIL;
    return hpx::transform_reduce(
        hpx::execution::par, src.begin(), src.end(), 0.0,
        std::plus<>{},
        [](double x) { return x * x; });
}

// Kernel-track example: L2-norm squared over a numpy ndarray.
// Templated over dtype; always runs par. No Python callback — safe to
// release GIL for the entire kernel duration.
template <typename T>
static double l2_norm_squared(nb::ndarray<nb::numpy, const T, nb::c_contig> a)
{
    ensure_runtime();
    const T* p = a.data();
    std::size_t n = a.size();
    HPYX_KERNEL_NOGIL;
    return static_cast<double>(
        hpx::transform_reduce(
            hpx::execution::par, p, p + n, T{0},
            std::plus<T>{},
            [](T x) { return x * x; }));
}

void register_bindings(nb::module_& m) {
    m.def("sum_of_squares",
          &sum_of_squares,
          "kind"_a, "task"_a, "chunk"_a, "chunk_size"_a, "src"_a);
    m.def("l2_norm_squared", &l2_norm_squared<float>,  "a"_a);
    m.def("l2_norm_squared", &l2_norm_squared<double>, "a"_a);
}

}  // namespace hpyx::contrib
