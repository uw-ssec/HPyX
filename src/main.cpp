#include <nanobind/nanobind.h>
#include <hpx/hpx_main.hpp>
#include <hpx/iostream.hpp>

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace nb = nanobind;
using namespace nb::literals;

int hpx_hello()
{
    // Say hello to the world!
    hpx::cout << "Hello World!\n" << std::flush;
    return 0;
}

NB_MODULE(_core, m) {
    m.doc() = "Python bindings for HPX C++ API";
    m.def("add", [](int a, int b) { return a + b; }, "a"_a, "b"_a);
    m.def("hpx_hello", &hpx_hello);

    #ifdef VERSION_INFO
        m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
    #else
        m.attr("__version__") = "dev";
    #endif
}
