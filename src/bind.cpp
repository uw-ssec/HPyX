#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/string.h>
#include <hpx/hpx_start.hpp>
#include <hpx/numeric.hpp>
#include <hpx/iostream.hpp>
#include <nanobind/ndarray.h>
#include <hpx/algorithm.hpp>
#include <hpx/execution.hpp>
#include <hpx/version.hpp>
#include "init_hpx.hpp"
#include "algorithms.hpp"
#include "futures.hpp"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace nb = nanobind;
using namespace nb::literals;

// Function to bind HPX future for nanobind
// This function binds the hpx::future<T> type to nanobind, allowing it
// to be used in Python code. It provides methods to get the result,
// check if the future is ready, and to attach callbacks that will be
// called when the future is ready.
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
        // TODO: Implement .then function that works with nanobind callable
        // Currently, the chaining of futures is not working correctly
        .def("then", [](hpx::future<T> &f, nb::callable callback, nb::args args) {
            std::cout << "Calling then with callback" << std::endl;
            auto fut = f.then([callback, args](hpx::future<T> && future) -> nb::object {
                std::cout << "Inside then callback" << std::endl;
                nb::gil_scoped_acquire acquire;
                return callback(*args);
            });
            return fut; 
        }, "callback"_a, nb::arg("*args"))
        .def("is_ready", [](hpx::future<T> &f) -> bool {
            return f.is_ready();
        });
}

NB_MODULE(_core, m)
{
    m.doc() = "Python bindings for HPX C++ API";

    // Bind HPX future for nanobind
    bind_hpx_future<nb::object>(m, "future");

    // Binding futures/async functionalities
    m.def("hpx_async", &futures::hpx_async, "f"_a, nb::arg("*args"));
    m.def("hpx_async_add", &futures::hpx_async_add, "a"_a, "b"_a);

    // Binding algorithms functionalities
    m.def("dot1d", &algorithms::dot1d, "a"_a, "b"_a);
    m.def("hpx_for_loop", &algorithms::hpx_for_loop, "function"_a, "iterable"_a, "policy"_a, "Parallel for loop over an interable");
    
    // Binding HPX runtime initialization and shutdown
    m.def("init_hpx_runtime", &init_hpx_runtime);
    m.def("stop_hpx_runtime", &stop_hpx_runtime);

    // Binding HPX Utility functions
    m.def("get_num_worker_threads", []()
          { return hpx::get_num_worker_threads(); });
    m.def("hpx_complete_version", [](){
        return hpx::complete_version();
    });

    // TODO: Uncomment and implement the following if needed
    //
    // m.def("hpx_transform", [](nb::callable f, nb::args args)
    //       {
    //     auto result = hpx::transform(
    //         hpx::execution::par, *args,
    //         [f](auto &&x) {
    //             nb::gil_scoped_acquire acquire;
    //             return f(x);
    //         });
    //     return result; }, "f"_a, nb::arg("*args"));
    //
    // m.def("matmul2d", &matmul2d, "A"_a, "B"_a);

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
