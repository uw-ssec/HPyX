#ifndef ALGORITHMS_HPP
#define ALGORITHMS_HPP

#include <nanobind/ndarray.h>

namespace algorithms {

namespace nb = nanobind;

double dot1d(
    nb::ndarray<nb::numpy, const double, nb::c_contig> a,
    nb::ndarray<nb::numpy, const double, nb::c_contig> b);

// nb::ndarray<nb::numpy, double, nb::c_contig>
// matmul2d(
//     nb::ndarray<nb::numpy, const double, nb::c_contig> A,
//     nb::ndarray<nb::numpy, const double, nb::c_contig> B
// );

// HPX For loop 
void hpx_for_loop(
    nb::callable function,
    nb::iterable iterable,
    std::string policy
);

}

#endif // ALGORITHMS_HPP
