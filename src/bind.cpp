#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/string.h>
#include <hpx/hpx_start.hpp>
#include <hpx/numeric.hpp>
#include <hpx/iostream.hpp>
#include <nanobind/ndarray.h>
#include <hpx/algorithm.hpp>
#include <hpx/execution.hpp>
#include "init_hpx.hpp"
#include "algorithms.hpp"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace nb = nanobind;
using namespace nb::literals;

int hpx_hello()
{
    // Say hello to the world!
    hpx::cout << "Hello World!\n"
              << std::flush;
    return 0;
}

void hpx_async_add(int a, int b)
{
    auto add = [](int number, int value_to_add)
    {
        return number + value_to_add;
    };

    hpx::future<int> add_lazy = hpx::async(add, a, b);
    std::cout << "Calling hpx::async(add, " << a << ", " << b
              << ")" << std::endl;
    int lazy_result = add_lazy.get();
    std::cout << "Which returned: " << lazy_result << std::endl;
}

template <typename T>
void bind_hpx_future(nb::module_ &m, const char *name) {
    nb::class_<hpx::future<T>>(m, name)
        .def("get", [](hpx::future<T> &f) {
            // TODO: Experiment with an approach that keeps result object in Python
            // Current version retrieves value in C++ and returns it to Python even though computation and result are in Python
            // Alternatively, return a pointer to the result object instead of copying it so that the async is compatible with Python and C++ objects
            auto result = f.get();
            nb::gil_scoped_release release;
            return result; })
        .def("then", [](hpx::future<T> &f, nb::callable callback, nb::args args)
             {
            auto fut = f.then([callback, args](hpx::future<T> && f) -> nb::object {
                nb::gil_scoped_acquire acquire;
                T result = f.get();
                return callback(result, *args);
            });
            return fut; }, "callback"_a, nb::arg("*args"));
}

NB_MODULE(_core, m)
{
    m.doc() = "Python bindings for HPX C++ API";
    m.def("add", [](int a, int b)
          { return a + b; }, "a"_a, "b"_a);
    m.def("hpx_hello", &hpx_hello);
    m.def("hpx_async_add", &hpx_async_add, "a"_a, "b"_a);

    bind_hpx_future<nb::object>(m, "future");

    m.def("hpx_async", [](nb::callable f, nb::args args)
          {
        auto result = hpx::async([f, args]() {
            nb::gil_scoped_acquire acquire;
            return f(*args);
        });
        return result; }, "f"_a, nb::arg("*args"));

    // m.def("hpx_transform", [](nb::callable f, nb::args args)
    //       {
    //     auto result = hpx::transform(
    //         hpx::execution::par, *args,
    //         [f](auto &&x) {
    //             nb::gil_scoped_acquire acquire;
    //             return f(x);
    //         });
    //     return result; }, "f"_a, nb::arg("*args"));

    m.def("dot1d", &algorithms::dot1d, "a"_a, "b"_a);
    // m.def("matmul2d", &matmul2d, "A"_a, "B"_a);
    m.def("init_hpx_runtime", &init_hpx_runtime);
    m.def("stop_hpx_runtime", &stop_hpx_runtime);

    m.def("get_num_worker_threads", []()
          { return hpx::get_num_worker_threads(); });

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
