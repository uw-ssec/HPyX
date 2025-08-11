#ifndef FUTURES_HPP
#define FUTURES_HPP

#include <nanobind/nanobind.h>
#include <hpx/numeric.hpp>
#include <hpx/future.hpp>
#include <iostream>
#include <stdexcept>

namespace futures {

    namespace nb = nanobind;

    // Function to create async futures with specified launch policy
    hpx::future<nb::object> hpx_async(nb::callable f, nb::args args);

    // Function to demonstrate async addition
    float hpx_async_add(float a, float b);

}

#endif // FUTURES_HPP
