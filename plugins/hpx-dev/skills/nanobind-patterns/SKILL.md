---
name: nanobind-patterns
description: Writes Nanobind C++-to-Python bindings for HPX APIs following HPyX conventions — generates `m.def` function bindings, `nb::class_` wrappers, type conversions, and `nb::ndarray` patterns. Use when the user asks to "create a binding", "write nanobind code", "wrap a C++ function", "add a new HPX binding", "bind a C++ class", "expose C++ to Python", "nanobind template", "type conversion", "ndarray binding", or works in files under `src/*.cpp` or `src/*.hpp`.
---

# Nanobind Binding Patterns for HPyX

## HPyX Binding Architecture

HPyX uses a 3-layer architecture:

1. **C++ Binding Layer** (`src/*.cpp`) — Nanobind wrappers around HPX APIs
2. **Python API Layer** (`src/hpyx/*.py`) — Pythonic high-level wrappers
3. **Module Entry Point** (`src/bind.cpp`) — `NB_MODULE(_core, m)` registration

All bindings compile into a single `_core` module with the `FREE_THREADED` flag for Python 3.13 free-threading support.

## Pattern: Wrapping a Pure C++ Function

For HPX functions that do not call back into Python (e.g., numeric operations on raw data):

```cpp
// In src/new_feature.cpp
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <hpx/algorithm.hpp>

namespace nb = nanobind;

namespace new_feature {

double compute(
    nb::ndarray<nb::numpy, const double, nb::c_contig> input)
{
    const double* data = input.data();
    std::size_t size = input.size();

    // No GIL management needed — pure C++ computation
    return hpx::reduce(
        hpx::execution::par,
        data, data + size,
        0.0, std::plus<>()
    );
}

} // namespace new_feature
```

Register in `src/bind.cpp`:
```cpp
m.def("compute", &new_feature::compute, "input"_a);
```

Reference `src/algorithms.cpp` (`dot1d`) as the canonical example of this pattern.

## Pattern: Wrapping a Function with Python Callbacks

For HPX functions that invoke Python callables, GIL management is critical:

```cpp
// In src/new_feature.cpp
#include <nanobind/nanobind.h>
#include <hpx/future.hpp>

namespace nb = nanobind;

namespace new_feature {

hpx::future<nb::object> async_apply(nb::callable f, nb::args args) {
    return hpx::async(
        hpx::launch::deferred,
        [f, args]() -> nb::object {
            nb::gil_scoped_acquire acquire;  // MUST acquire GIL before calling Python
            return f(*args);
        });
}

} // namespace new_feature
```

Reference `src/futures.cpp` (`hpx_async`) as the canonical example.

## Pattern: Binding an HPX Class (Template)

For exposing HPX types like `hpx::future<T>`:

```cpp
template <typename T>
void bind_hpx_type(nb::module_ &m, const char *name) {
    nb::class_<hpx::some_type<T>>(m, name)
        .def(nb::init<>())
        .def("method", [](hpx::some_type<T> &self) {
            // Lambda wrapper for complex methods
            return self.method();
        })
        .def("method_with_callback", [](hpx::some_type<T> &self, nb::callable cb) {
            nb::gil_scoped_acquire acquire;
            return cb(self.get_value());
        }, "callback"_a);
}
```

Reference `src/bind.cpp` (`bind_hpx_future`) as the canonical example.

## Pattern: Python Wrapper Layer

Every C++ binding should have a corresponding Python wrapper in `src/hpyx/`:

```python
# src/hpyx/new_feature/_compute.py
from __future__ import annotations

from collections.abc import Callable
from .._core import raw_function_name

def compute(data, *, policy: str = "par") -> float:
    """
    High-level Python API with validation and docs.

    Parameters
    ----------
    data : array-like
        Input data array.
    policy : str
        Execution policy ("seq" or "par").
    """
    return raw_function_name(data, policy)
```

Import from `_core`, expose a Pythonic API (keyword arguments, sensible defaults), and raise `NotImplementedError` for unimplemented policies rather than crashing.

## Nanobind Type Mappings

| C++ Type | Nanobind Annotation | Python Type |
|---|---|---|
| `double` | automatic | `float` |
| `int` / `std::size_t` | automatic | `int` |
| `std::string` | `#include <nanobind/stl/string.h>` | `str` |
| `std::vector<T>` | `#include <nanobind/stl/vector.h>` | `list` |
| NumPy array | `nb::ndarray<nb::numpy, T, nb::c_contig>` | `numpy.ndarray` |
| Python callable | `nb::callable` | `Callable` |
| Python object | `nb::object` | `object` |
| Variadic args | `nb::args` | `*args` |

## CMake Integration

When adding new source files, update `CMakeLists.txt`:

```cmake
nanobind_add_module(
  _core
  FREE_THREADED
  src/bind.cpp
  src/init_hpx.cpp
  src/algorithms.cpp
  src/futures.cpp
  src/new_feature.cpp    # Add new source file here
)
```

For new headers, create `src/new_feature.hpp` with the function declarations and include it in `src/bind.cpp`.

## Validation Sequence After Adding a Binding

After writing the C++ binding, header, `bind.cpp` registration, and updating `CMakeLists.txt`, verify correctness in this order — each step gates the next:

```bash
# 1. Rebuild the extension (fast, editable)
pip install --no-build-isolation -ve .

# 2. Confirm the compiled module exists and the new symbol is exposed
python -c "from hpyx import _core; print(_core.new_function_name)"

# 3. Smoke-test in an HPX runtime
python -c "
from hpyx.runtime import HPXRuntime
from hpyx import _core
with HPXRuntime():
    print(_core.new_function_name(<test inputs>))
"

# 4. Run the associated test suite
pixi run test tests/test_new_feature.py
```

If step 2 fails with `AttributeError`, the `m.def(...)` registration is missing or misspelled. If step 3 hangs or segfaults, revisit GIL management (see **gil-management** skill). If step 4 fails, check type conversions and policy handling.

## File Organization

For the complete step-by-step scaffolding workflow and file checklist when adding a new binding, see the **add-binding** skill. The key files to create: C++ source + header in `src/`, register in `src/bind.cpp`, update `CMakeLists.txt`, Python wrapper in `src/hpyx/`, and tests in `tests/`.

## Common Pitfalls

- **Missing GIL acquire**: Any C++ lambda that calls Python (`nb::callable`, accessing `nb::object`) MUST use `nb::gil_scoped_acquire`. See the **gil-management** skill for full GIL rules.
- **Missing GIL release**: Long-running pure C++ operations should release the GIL with `nb::gil_scoped_release`.
- **Forgetting FREE_THREADED**: The `nanobind_add_module` call must include `FREE_THREADED` for Python 3.13 free-threading.
- **Moving futures**: `hpx::future` is move-only — use `std::move()` when capturing in lambdas.
- **Header includes**: Always include the specific HPX header, not the catch-all `<hpx/hpx.hpp>` (slower compilation).

For HPX runtime semantics that affect bindings — `hpx::function` vs `std::function`, invalid future handling, `.get()` GIL behavior by launch policy, executor lifetime, policy-object thread-safety — see **`references/nanobind-api.md`** ("HPX Runtime Semantics in Bindings" section).

## Additional Resources

### Reference Files

- **`references/nanobind-api.md`** — Nanobind API reference for common operations (ndarray, type casters, GIL management)
