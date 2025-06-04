#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/string.h>
#include <hpx/hpx_start.hpp>
#include <hpx/numeric.hpp>
#include <hpx/iostream.hpp>
#include <nanobind/ndarray.h>
#include <hpx/algorithm.hpp>
#include <hpx/execution.hpp>

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace nb = nanobind;
using namespace nb::literals;

int hpx_hello()
{
    // Say hello to the world!
    hpx::cout << "Hello World!\n"
              << std::flush;
    return 0;
}

void hpx_async_add(int a, int b)
{
    auto add = [](int number, int value_to_add)
    {
        return number + value_to_add;
    };

    hpx::future<int> add_lazy = hpx::async(add, a, b);
    std::cout << "Calling hpx::async(add, " << a << ", " << b
              << ")" << std::endl;
    int lazy_result = add_lazy.get();
    std::cout << "Which returned: " << lazy_result << std::endl;
}

struct global_runtime_manager
{
    global_runtime_manager(std::vector<std::string> const &config)
        : running_(false), rts_(nullptr), cfg(config)
    {
        hpx::init_params params;
        params.cfg = cfg;
        // params.mode = hpx::runtime_mode::console;

        hpx::function<int(int, char **)> start_function =
            hpx::bind_front(&global_runtime_manager::hpx_main, this);

        if (!hpx::start(start_function, 0, nullptr, params))
        {
            std::abort(); // Failed to initialize runtime
        }

        // Wait for the main HPX thread to start
        std::unique_lock<std::mutex> lk(startup_mtx_);
        while (!running_)
            startup_cond_.wait(lk);
    }

    ~global_runtime_manager()
    {
        {
            std::lock_guard<hpx::spinlock> lk(mtx_);
            rts_ = nullptr;
        }

        cond_.notify_one();
        hpx::stop(); // Stop the runtime
    }

    int hpx_main(int argc, char *argv[])
    {
        rts_ = hpx::get_runtime_ptr();

        {
            std::lock_guard<std::mutex> lk(startup_mtx_);
            running_ = true;
        }

        startup_cond_.notify_one();

        // Wait for the destructor to signal exit
        {
            std::unique_lock<hpx::spinlock> lk(mtx_);
            if (rts_ != nullptr)
                cond_.wait(lk);
        }

        return hpx::finalize(); // Allow runtime to exit
    }

private:
    hpx::spinlock mtx_;
    hpx::condition_variable_any cond_;

    std::mutex startup_mtx_;
    std::condition_variable startup_cond_;
    bool running_;

    hpx::runtime *rts_;
    std::vector<std::string> const cfg;
};

global_runtime_manager *rts = nullptr;

void init_hpx_runtime(std::vector<std::string> const &cfg)
{
    if (rts == nullptr)
    {
        nb::gil_scoped_acquire acquire;
        rts = new global_runtime_manager(cfg);
    }
}

void stop_hpx_runtime()
{
    global_runtime_manager *r = rts;
    rts = nullptr;
    if (r != nullptr)
    {
        nb::gil_scoped_release release;
        delete r;
    }
}

template <typename T>
void bind_hpx_future(nb::module_ &m, const char *name) {
    nb::class_<hpx::future<T>>(m, name)
        .def("get", [](hpx::future<T> &f) {
            auto result = f.get();
            nb::gil_scoped_release release;
            return result; })
        .def("then", [](hpx::future<T> &f, nb::callable callback, nb::args args)
             {
            auto fut = f.then([callback, args](hpx::future<T> && f) -> nb::object {
                nb::gil_scoped_acquire acquire;
                T result = f.get();
                return callback(result, *args);
            });
            return fut; }, "callback"_a, nb::arg("*args"));
}

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
        // hpx::execution::,          // parallel execution policy
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
//     int64_t rowsA = A.shape(0);   // number of rows in A  [oai_citation:2‡nanobind.readthedocs.io](https://nanobind.readthedocs.io/en/latest/ndarray.html?utm_source=chatgpt.com)
//     int64_t colsA = A.shape(1);   // number of columns in A  [oai_citation:3‡nanobind.readthedocs.io](https://nanobind.readthedocs.io/en/latest/ndarray.html?utm_source=chatgpt.com)
//     int64_t rowsB = B.shape(0);   // number of rows in B  [oai_citation:4‡nanobind.readthedocs.io](https://nanobind.readthedocs.io/en/latest/ndarray.html?utm_source=chatgpt.com)
//     int64_t colsB = B.shape(1);   // number of columns in B  [oai_citation:5‡nanobind.readthedocs.io](https://nanobind.readthedocs.io/en/latest/ndarray.html?utm_source=chatgpt.com)

//     // 2. Validate that inner dimensions match: colsA == rowsB
//     if (colsA != rowsB) {
//         throw std::invalid_argument(
//             "hpx_matmul_nd: A.shape[1] must equal B.shape[0]"
//         );  // 
//     }

//     // 3. Allocate output ndarray C of shape (rowsA, colsB), C-contiguous
//     //    Use nb::ndarray with shape<2> and c_contig flag  [oai_citation:6‡nanobind.readthedocs.io](https://nanobind.readthedocs.io/en/latest/ndarray.html?utm_source=chatgpt.com)
//     auto C = nb::ndarray<nb::numpy, double, nb::c_contig>({
//         rowsA, colsB
//     });

//     // 4. Get raw pointers to the data buffers for A, B, and C
//     const double* A_data = A.data();                        // input A data  [oai_citation:7‡nanobind.readthedocs.io](https://nanobind.readthedocs.io/en/latest/ndarray.html?utm_source=chatgpt.com)
//     const double* B_data = B.data();                        // input B data  [oai_citation:8‡nanobind.readthedocs.io](https://nanobind.readthedocs.io/en/latest/ndarray.html?utm_source=chatgpt.com)
//     double*       C_data = C.data();                        // output C buffer  [oai_citation:9‡Stack Overflow](https://stackoverflow.com/questions/78777991/return-ndarray-in-nanobind-with-owned-memory?utm_source=chatgpt.com)

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

NB_MODULE(_core, m)
{
    m.doc() = "Python bindings for HPX C++ API";
    m.def("add", [](int a, int b)
          { return a + b; }, "a"_a, "b"_a);
    m.def("hpx_hello", &hpx_hello);
    m.def("hpx_async_add", &hpx_async_add, "a"_a, "b"_a);

    bind_hpx_future<nb::object>(m, "future");

    m.def("hpx_async", [](nb::callable f, nb::args args)
          {
        auto result = hpx::async([f, args]() {
            nb::gil_scoped_acquire acquire;
            return f(*args);
        });
        return result; }, "f"_a, nb::arg("*args"));

    // m.def("hpx_transform", [](nb::callable f, nb::args args)
    //       {
    //     auto result = hpx::transform(
    //         hpx::execution::par, *args,
    //         [f](auto &&x) {
    //             nb::gil_scoped_acquire acquire;
    //             return f(x);
    //         });
    //     return result; }, "f"_a, nb::arg("*args"));

    m.def("dot1d", &dot1d, "a"_a, "b"_a);
    // m.def("matmul2d", &matmul2d, "A"_a, "B"_a);
    m.def("init_hpx_runtime", &init_hpx_runtime);
    m.def("stop_hpx_runtime", &stop_hpx_runtime);

    m.def("get_num_worker_threads", []()
          { return hpx::get_num_worker_threads(); });

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
