#include "kernels.hpp"

#include <nanobind/ndarray.h>
#include <hpx/numeric.hpp>
#include <hpx/algorithm.hpp>
#include <hpx/execution.hpp>

#include <cstdint>
#include <functional>
#include <stdexcept>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::kernels {

template <typename T>
double dot_kernel(
    nb::ndarray<nb::numpy, const T, nb::c_contig> a,
    nb::ndarray<nb::numpy, const T, nb::c_contig> b)
{
    if (a.size() != b.size()) {
        throw std::invalid_argument("dot: arrays must have the same size");
    }
    const T* a_data = a.data();
    const T* b_data = b.data();
    std::size_t n = a.size();
    nb::gil_scoped_release release;
    return hpx::transform_reduce(
        hpx::execution::par,
        a_data, a_data + n,
        b_data,
        0.0,
        std::plus<>(),
        [](T x, T y) -> double { return static_cast<double>(x) * static_cast<double>(y); });
}

template <typename T>
T sum_kernel(nb::ndarray<nb::numpy, const T, nb::c_contig> a)
{
    const T* data = a.data();
    std::size_t n = a.size();
    nb::gil_scoped_release release;
    return hpx::reduce(hpx::execution::par, data, data + n, T(0), std::plus<>());
}

template <typename T>
T max_val_kernel(nb::ndarray<nb::numpy, const T, nb::c_contig> a)
{
    if (a.size() == 0) {
        throw std::invalid_argument("max_val: array must not be empty");
    }
    const T* data = a.data();
    std::size_t n = a.size();
    T init = data[0];
    nb::gil_scoped_release release;
    return hpx::reduce(
        hpx::execution::par, data, data + n, init,
        [](T x, T y) { return x > y ? x : y; });
}

template <typename T>
T min_val_kernel(nb::ndarray<nb::numpy, const T, nb::c_contig> a)
{
    if (a.size() == 0) {
        throw std::invalid_argument("min_val: array must not be empty");
    }
    const T* data = a.data();
    std::size_t n = a.size();
    T init = data[0];
    nb::gil_scoped_release release;
    return hpx::reduce(
        hpx::execution::par, data, data + n, init,
        [](T x, T y) { return x < y ? x : y; });
}

void register_bindings(nb::module_& m)
{
    m.def("dot_f32", &dot_kernel<float>, "a"_a, "b"_a);
    m.def("dot_f64", &dot_kernel<double>, "a"_a, "b"_a);
    m.def("dot_i32", &dot_kernel<int32_t>, "a"_a, "b"_a);
    m.def("dot_i64", &dot_kernel<int64_t>, "a"_a, "b"_a);

    m.def("sum_f32", &sum_kernel<float>, "a"_a);
    m.def("sum_f64", &sum_kernel<double>, "a"_a);
    m.def("sum_i32", &sum_kernel<int32_t>, "a"_a);
    m.def("sum_i64", &sum_kernel<int64_t>, "a"_a);

    m.def("max_val_f32", &max_val_kernel<float>, "a"_a);
    m.def("max_val_f64", &max_val_kernel<double>, "a"_a);
    m.def("max_val_i32", &max_val_kernel<int32_t>, "a"_a);
    m.def("max_val_i64", &max_val_kernel<int64_t>, "a"_a);

    m.def("min_val_f32", &min_val_kernel<float>, "a"_a);
    m.def("min_val_f64", &min_val_kernel<double>, "a"_a);
    m.def("min_val_i32", &min_val_kernel<int32_t>, "a"_a);
    m.def("min_val_i64", &min_val_kernel<int64_t>, "a"_a);
}

}  // namespace hpyx::kernels
