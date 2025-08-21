#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/string.h>
#include <hpx/hpx_start.hpp>
#include <hpx/numeric.hpp>
#include <hpx/future.hpp>
#include <hpx/iostream.hpp>
#include <nanobind/ndarray.h>
#include <hpx/algorithm.hpp>
#include <hpx/execution.hpp>
#include <hpx/version.hpp>
#include <vector>
#include <memory>
#include <string>
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
        .def(nb::init<>())
        .def("get", [](hpx::future<T> &f) {
            // For deferred launch policy, the callable executes in the
            // calling thread when get() is invoked and may call back into
            // Python. Keep the GIL held here so Python callables can run
            // safely.
            return f.get();
        })
        .def("then", [](hpx::future<T> &f, nb::callable callback, nb::args args) {

            // Create a new deferred future that, when executed via get(),
            // will run predecessor.get() and then invoke the Python
            // callback while holding the GIL.
            hpx::future<T> cont = hpx::async(hpx::launch::deferred,
                [prev = std::move(f), callback, args]() mutable -> nb::object {
                    nb::gil_scoped_acquire acquire;
                    auto res = prev.get();
                    return callback(res, *args);
                });

            return cont;
        }, "callback"_a, nb::arg("*args"), "Attach a callback that will be called with the future's result and optional extra arguments")
        .def("is_ready", [](hpx::future<T> &f) -> bool { return f.is_ready(); });
}

NB_MODULE(_core, m)
{
    m.doc() = "Python bindings for HPX C++ API";

    // Bind HPX future for nanobind
    bind_hpx_future<nb::object>(m, "future");

    // Binding futures/async functionalities
    m.def("hpx_async", [](nb::callable f, nb::args args) {
        return futures::hpx_async(f, args); // return hpx::future<nb::object>
    }, "f"_a, nb::arg("*args"));
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
