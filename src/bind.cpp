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
#include <memory>
#include <string>
#include "init_hpx.hpp"
#include "algorithms.hpp"
#include "futures.hpp"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace nb = nanobind;
using namespace nb::literals;

// Lightweight wrapper that holds a shared_ptr to an hpx::future<T>
// This keeps a stable C++ object to attach metadata (is_chained/origin)
template <typename T>
struct HPXFutureWrapper {
    std::shared_ptr<hpx::future<T>> fut;
    bool is_chained = false;
    std::string origin = "direct";
    nb::object custom_data = nb::none();

    HPXFutureWrapper() = default;
    HPXFutureWrapper(std::shared_ptr<hpx::future<T>> f, bool chained = false, const std::string &orig = "direct")
        : fut(std::move(f)), is_chained(chained), origin(orig) {}
};

// Function to bind HPX future for nanobind
// This function binds the hpx::future<T> type to nanobind, allowing it
// to be used in Python code. It provides methods to get the result,
// check if the future is ready, and to attach callbacks that will be
// called when the future is ready.
template <typename T>
void bind_hpx_future(nb::module_ &m, const char *name) {
    nb::class_<HPXFutureWrapper<T>>(m, name)
        .def(nb::init<>())
        .def("get", [](HPXFutureWrapper<T> &w) {
            // If this future is from a chained continuation, release the GIL
            // before blocking so other Python threads can run. For direct
            // (non-chained) futures we keep the previous behavior and do not
            // release the GIL before get().
            if (w.is_chained) {
                nb::gil_scoped_release release;
                return w.fut->get();
            } else {
                auto result = w.fut->get();
                nb::gil_scoped_release release;
                return result;
            }
        })
        .def("then", [](HPXFutureWrapper<T> &w, nb::callable callback, nb::args args) {
            // capture args
            std::vector<nb::object> captured_args;
            for (size_t i = 0; i < args.size(); ++i) captured_args.push_back(args[i]);

            // attach continuation to underlying future
            auto cont = w.fut->then([callback, captured_args](hpx::future<T> inner) -> nb::object {
                nb::gil_scoped_acquire acquire;
                try {
                    auto res = inner.get();
                    if (!captured_args.empty()) {
                        switch (captured_args.size()) {
                            case 1: return callback(res, captured_args[0]);
                            case 2: return callback(res, captured_args[0], captured_args[1]);
                            case 3: return callback(res, captured_args[0], captured_args[1], captured_args[2]);
                            case 4: return callback(res, captured_args[0], captured_args[1], captured_args[2], captured_args[3]);
                            default: throw std::runtime_error("Too many arguments (max 4 extra args supported)");
                        }
                    } else {
                        return callback(res);
                    }
                } catch (const std::exception &e) {
                    throw nb::python_error();
                }
            });

            auto shared_cont = std::make_shared<std::decay_t<decltype(cont)>>(std::move(cont));
            HPXFutureWrapper<T> out(shared_cont, true, "chained");
            return out;
        }, "callback"_a, nb::arg("*args"), "Attach a callback that will be called with the future's result and optional extra arguments")
        .def("is_ready", [](HPXFutureWrapper<T> &w) -> bool { return w.fut->is_ready(); })
        .def_prop_ro("is_chained", [](const HPXFutureWrapper<T> &w) { return w.is_chained; })
        .def_prop_ro("origin", [](const HPXFutureWrapper<T> &w) { return w.origin; })
        .def_prop_rw("custom_data",
            [](const HPXFutureWrapper<T> &w) { return w.custom_data; },
            [](HPXFutureWrapper<T> &w, nb::object val) { w.custom_data = val; });
}

NB_MODULE(_core, m)
{
    m.doc() = "Python bindings for HPX C++ API";

    // Bind HPX future for nanobind
    bind_hpx_future<nb::object>(m, "future");

    // Binding futures/async functionalities
    m.def("hpx_async", [](nb::callable f, nb::args args) {
        auto raw = futures::hpx_async(f, args); // hpx::future<nb::object>
        auto shared = std::make_shared<hpx::future<nb::object>>(std::move(raw));
        return HPXFutureWrapper<nb::object>(shared, false, "direct");
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
