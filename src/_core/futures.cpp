#include <nanobind/nanobind.h>
#include <hpx/numeric.hpp>
#include <hpx/future.hpp>
#include <iostream>
#include <stdexcept>

namespace futures {

    namespace nb = nanobind;

    hpx::future<nb::object> hpx_async(nb::callable f, nb::args args) {
        auto result = hpx::async(
            hpx::launch::deferred,
            [f, args]() -> nb::object {
                std::cout << "Calling hpx::async with function" << std::endl;
                nb::gil_scoped_acquire acquire;
                return f(*args);
            });
        return result;
    }

    float hpx_async_add(float a, float b) {
        auto add = [](float number, float value_to_add)
        {
            return number + value_to_add;
        };

        hpx::future<float> add_lazy = hpx::async(add, a, b);
        std::cout << "Calling hpx::async(add, " << a << ", " << b
                << ")" << std::endl;
        auto lazy_result = add_lazy.get();
        std::cout << "Which returned: " << lazy_result << std::endl;
        return lazy_result;
    }

}
