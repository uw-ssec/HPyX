#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/string.h>
#include <nanobind/ndarray.h>
#include <hpx/numeric.hpp>
#include <hpx/algorithm.hpp>

namespace nb = nanobind;

namespace algorithms {

double dot1d(
    nb::ndarray<nb::numpy, const double, nb::c_contig> a,
    nb::ndarray<nb::numpy, const double, nb::c_contig> b)
{
    if (a.size() != b.size()) {
        throw std::invalid_argument("Arrays must have the same size");
    }

    const double* a_data = a.data();
    const double* b_data = b.data();
    std::size_t size = a.size();

    return hpx::transform_reduce(
        hpx::execution::par,          // parallel execution policy
        a_data, a_data + size,        // range of first array
        b_data,                       // beginning of second array
        0.0,                          // initial sum
        std::plus<>(),                // reduction operation
        [](double x, double y) {      // transform operation
            return x * y;
        }
    );
}

// nb::ndarray<nb::numpy, double, nb::c_contig>
// matmul2d(
//     nb::ndarray<nb::numpy, const double, nb::c_contig> A,
//     nb::ndarray<nb::numpy, const double, nb::c_contig> B
// ) {
//     // 1. Extract dimensions from A and B
//     int64_t rowsA = A.shape(0);   // number of rows in A
//     int64_t colsA = A.shape(1);   // number of columns in A
//     int64_t rowsB = B.shape(0);   // number of rows in B
//     int64_t colsB = B.shape(1);   // number of columns in B

//     // 2. Validate that inner dimensions match: colsA == rowsB
//     if (colsA != rowsB) {
//         throw std::invalid_argument(
//             "hpx_matmul_nd: A.shape[1] must equal B.shape[0]"
//         );  //
//     }

//     // 3. Allocate output ndarray C of shape (rowsA, colsB), C-contiguous
//     //    Use nb::ndarray with shape<2> and c_contig flag
//     auto C = nb::ndarray<nb::numpy, double, nb::c_contig>({
//         rowsA, colsB
//     });

//     // 4. Get raw pointers to the data buffers for A, B, and C
//     const double* A_data = A.data();                        // input A data
//     const double* B_data = B.data();                        // input B data
//     double*       C_data = C.data();                        // output C buffer

//     std::fill_n(C_data, static_cast<size_t>(rowsA * colsB), 0.0);  //

//     hpx::experimental::for_loop(
//         hpx::execution::par,                     // parallel execution policy
//         (std::size_t)0, (std::size_t)rowsA,      // outer loop: over rows of A
//         [&](std::size_t i) {
//             const double* A_row = A_data + i * (std::size_t)colsA;
//             double* C_row = C_data + i * (std::size_t)colsB;
//             for (std::size_t j = 0; j < (std::size_t)colsB; ++j) {
//                 double sum = 0.0;
//                 const double* B_col = B_data + j;
//                 for (std::size_t k = 0; k < (std::size_t)colsA; ++k) {
//                     sum += A_row[k] * B_col[k * (std::size_t)colsB];
//                 }
//                 C_row[j] = sum;
//             }
//         }
//     );
//     return C;
// }

// HPX For loop 
void hpx_for_loop(
    nb::callable function,
    nb::iterable iterable,
    std::string policy = "seq"
) {
    // Get start and end indices
    int start = 0;
    int end = nb::len(iterable);

    // Use hpx for_loop to apply the function to each element in the iterable
    if (policy == "par") {
        hpx::experimental::for_loop(
            hpx::execution::par, start, end,
            [&](std::size_t i) {
                auto data = iterable[i];
                iterable[i] = function(data);
            }
        );
    } else if (policy == "seq") {
        hpx::experimental::for_loop(
            hpx::execution::seq, start, end,
            [&](std::size_t i) {
                auto data = iterable[i];
                iterable[i] = function(data);
            }
        );
    } else {
        throw std::invalid_argument("Invalid execution policy: " + policy);
    }
}


} // namespace algorithms
