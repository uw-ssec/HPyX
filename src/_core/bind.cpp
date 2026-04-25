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
#include "runtime.hpp"
#include "algorithms.hpp"
#include "futures.hpp"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace nb = nanobind;
using namespace nb::literals;

NB_MODULE(_core, m)
{
    m.doc() = "Python bindings for HPX C++ API";

    auto m_runtime = m.def_submodule("runtime");
    hpyx::runtime::register_bindings(m_runtime);

    auto m_futures = m.def_submodule("futures");
    hpyx::futures::register_bindings(m_futures);

    // Binding algorithms functionalities
    m.def("dot1d", &algorithms::dot1d, "a"_a, "b"_a);
    m.def("hpx_for_loop", &algorithms::hpx_for_loop, "function"_a, "iterable"_a, "policy"_a, "Parallel for loop over an interable");
    
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
