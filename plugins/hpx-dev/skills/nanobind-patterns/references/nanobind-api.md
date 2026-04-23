# Nanobind API Reference for HPyX

Quick reference for Nanobind APIs commonly used in HPyX bindings.

## Module Definition

```cpp
#include <nanobind/nanobind.h>
namespace nb = nanobind;
using namespace nb::literals;

NB_MODULE(_core, m) {
    m.doc() = "Module docstring";

    // Function binding
    m.def("func_name", &namespace::function, "arg1"_a, "arg2"_a,
          "Docstring");

    // Lambda binding
    m.def("func_name", [](int x) { return x * 2; }, "x"_a);

    // Module attribute
    m.attr("__version__") = "1.0.0";
}
```

## Type Bindings

### Class Binding
```cpp
nb::class_<MyClass>(m, "MyClass")
    .def(nb::init<>())                          // Default constructor
    .def(nb::init<int, std::string>())          // Parameterized constructor
    .def("method", &MyClass::method)            // Member function
    .def("__repr__", &MyClass::to_string)       // Special method
    .def_rw("field", &MyClass::field)           // Read-write property
    .def_ro("const_field", &MyClass::const_field); // Read-only property
```

### Template Class Binding
```cpp
template <typename T>
void bind_type(nb::module_ &m, const char *name) {
    nb::class_<Container<T>>(m, name)
        .def(nb::init<>())
        .def("get", [](Container<T> &self) { return self.get(); })
        .def("set", [](Container<T> &self, T val) { self.set(val); }, "val"_a);
}

// In NB_MODULE:
bind_type<int>(m, "IntContainer");
bind_type<double>(m, "DoubleContainer");
```

## STL Type Conversions

```cpp
#include <nanobind/stl/string.h>    // std::string ↔ str
#include <nanobind/stl/vector.h>    // std::vector ↔ list
#include <nanobind/stl/pair.h>      // std::pair ↔ tuple
#include <nanobind/stl/tuple.h>     // std::tuple ↔ tuple
#include <nanobind/stl/optional.h>  // std::optional ↔ Optional
#include <nanobind/stl/map.h>       // std::map ↔ dict
#include <nanobind/stl/set.h>       // std::set ↔ set
```

## NumPy ndarray

```cpp
#include <nanobind/ndarray.h>

// Read-only double array, C-contiguous, NumPy
nb::ndarray<nb::numpy, const double, nb::c_contig> arr;

// Writable float array
nb::ndarray<nb::numpy, float, nb::c_contig> arr;

// Any dtype
nb::ndarray<nb::numpy> arr;

// Access data
const double* data = arr.data();
std::size_t size = arr.size();
std::size_t ndim = arr.ndim();
std::size_t shape_i = arr.shape(i);

// With shape constraints
nb::ndarray<nb::numpy, double, nb::shape<nb::any, 3>> matrix_nx3;
```

## Function Arguments

```cpp
// Named arguments
m.def("func", &func, "x"_a, "y"_a);

// Default values
m.def("func", &func, "x"_a, "y"_a = 0);

// Keyword-only
m.def("func", &func, "x"_a, nb::kw_only(), "y"_a = 0);

// Variadic args
m.def("func", [](nb::args args) { /* ... */ }, nb::arg("*args"));

// Callable
m.def("func", [](nb::callable f) { f(); }, "f"_a);
```

## GIL Management

```cpp
// Acquire GIL (when in C++ thread, need to call Python)
{
    nb::gil_scoped_acquire acquire;
    // Safe to call Python here
    nb::object result = callback(arg);
}

// Release GIL (when in Python thread, doing pure C++ work)
{
    nb::gil_scoped_release release;
    // Python threads can run while we do C++ work
    expensive_cpp_computation();
}
```

**HPyX-specific notes:**
- With `FREE_THREADED` module flag, GIL operations become no-ops when GIL is disabled
- Still include them for correctness — they protect against GIL-enabled Python builds
- Thread safety must come from explicit synchronization (mutexes), not GIL

## Python Object Manipulation

```cpp
// Create Python objects
nb::object obj = nb::cast(42);
nb::list lst;
lst.append(nb::cast(1));

// Call Python
nb::callable func = ...;
nb::object result = func(arg1, arg2);

// Extract C++ value
int value = nb::cast<int>(result);

// Check type
if (nb::isinstance<nb::int_>(obj)) { /* ... */ }

// None
nb::none();
```

## Error Handling

```cpp
// Raise Python exception from C++
throw nb::value_error("message");
throw nb::type_error("message");
throw nb::index_error("message");
throw nb::key_error("message");

// Translate C++ exception to Python
nb::register_exception_translator([](const std::exception_ptr &p, void *) {
    try { std::rethrow_exception(p); }
    catch (const MyException &e) {
        PyErr_SetString(PyExc_RuntimeError, e.what());
    }
});
```

## FREE_THREADED Module Flag

```cmake
nanobind_add_module(
  _core
  FREE_THREADED    # Required for Python 3.13 free-threading
  src/bind.cpp
  ...
)
```

This flag:
- Marks the module as supporting free-threading
- Enables per-object locking where needed
- Makes GIL acquire/release no-ops when GIL is disabled
- Must be set for all HPyX modules
