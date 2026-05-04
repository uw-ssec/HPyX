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
#include "kernels.hpp"
#include "parallel.hpp"

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

    auto m_kernels = m.def_submodule("kernels");
    hpyx::kernels::register_bindings(m_kernels);

    auto m_parallel = m.def_submodule("parallel");
    hpyx::parallel::register_bindings(m_parallel);

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
