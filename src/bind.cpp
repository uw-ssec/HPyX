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
#include <vector>
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
            // Release GIL before blocking operation to allow other Python threads
            nb::gil_scoped_release release;
            auto result = f.get();
            // GIL is automatically reacquired when release goes out of scope
            return result; })
        .def("then", [](hpx::future<T> &f, nb::callable callback, nb::args args) {
            // Enhanced version: callback with optional extra args
            // Capture args by copying them to avoid lifetime issues
            std::vector<nb::object> captured_args;
            for (size_t i = 0; i < args.size(); ++i) {
                captured_args.push_back(args[i]);
            }
            
            auto fut = f.then([callback, captured_args](hpx::future<T>&& future) -> nb::object {
                nb::gil_scoped_acquire acquire;
                try {
                    auto result = future.get();
                    if (!captured_args.empty()) {
                        // Use nanobind's operator() with multiple arguments
                        switch (captured_args.size()) {
                            case 1: return callback(result, captured_args[0]);
                            case 2: return callback(result, captured_args[0], captured_args[1]);
                            case 3: return callback(result, captured_args[0], captured_args[1], captured_args[2]);
                            case 4: return callback(result, captured_args[0], captured_args[1], captured_args[2], captured_args[3]);
                            default:
                                throw std::runtime_error("Too many arguments (max 4 extra args supported)");
                        }
                    } else {
                        return callback(result);
                    }
                } catch (const std::exception& e) {
                    throw nb::python_error();
                }
            });

            return fut; 
        }, "callback"_a, nb::arg("*args"), "Attach a callback that will be called with the future's result and optional extra arguments")
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
