---
name: add-binding
description: Generates the complete scaffolding (C++ source, header, `bind.cpp` registration, CMake update, Python wrapper package, tests, and optional benchmarks) for a new HPX algorithm binding in HPyX. Use when the user asks to "add a new binding", "scaffold a binding", "create an HPX wrapper", "add hpx::for_each binding", "add hpx::reduce binding", "wrap a new HPX algorithm", "add a new HPX feature to HPyX", or provides a specific HPX feature name and wants end-to-end scaffolding.
---

# Add HPX Binding Scaffold

## Workflow

### Step 1: Identify the HPX Feature

Determine which HPX C++ API to wrap. If the user provided a feature name, look it up in the HPX source:

```
vendor/hpx/libs/core/algorithms/  — Parallel algorithms (for_each, reduce, sort, etc.)
vendor/hpx/libs/core/futures/     — Future combinators (when_all, when_any)
vendor/hpx/libs/core/synchronization/ — Synchronization primitives (latch, barrier)
```

Search for the HPX header and understand the C++ API signature, template parameters, and execution policy support.

### Step 2: Plan the Binding

Checklist:
- Input/output types and their Python equivalents
- GIL acquisition needed (Python callbacks)
- Which execution policies to expose (seq/par/par_unseq)
- Python API name (snake_case)

### Step 3: Create C++ Source

Create `src/<feature_name>.cpp`. Concrete example for a `hpx::reduce` binding on a NumPy array:

```cpp
// src/reduce.cpp
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <hpx/algorithm.hpp>
#include <hpx/numeric.hpp>
#include <hpx/execution.hpp>
#include "reduce.hpp"

namespace nb = nanobind;

namespace reduce_binding {

double reduce_sum(
    nb::ndarray<nb::numpy, const double, nb::c_contig> input,
    const std::string& policy)
{
    const double* data = input.data();
    std::size_t size = input.size();

    // Pure C++ path — no GIL management needed; raw pointers only
    if (policy == "seq") {
        return hpx::reduce(hpx::execution::seq, data, data + size, 0.0);
    } else if (policy == "par") {
        return hpx::reduce(hpx::execution::par, data, data + size, 0.0);
    }
    throw std::invalid_argument("policy must be 'seq' or 'par'");
}

}  // namespace reduce_binding
```

Create `src/reduce.hpp` with the declaration:

```cpp
// src/reduce.hpp
#pragma once
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <string>

namespace nb = nanobind;

namespace reduce_binding {
    double reduce_sum(
        nb::ndarray<nb::numpy, const double, nb::c_contig> input,
        const std::string& policy);
}
```

### Step 4: Register in bind.cpp

```cpp
// At the top of src/bind.cpp:
#include "reduce.hpp"

// Inside NB_MODULE(_core, m):
m.def("reduce_sum", &reduce_binding::reduce_sum,
      "input"_a, "policy"_a = "par",
      "Parallel reduction (sum) over a contiguous double array.\n\n"
      "Parameters\n----------\n"
      "input : numpy.ndarray[float64]\n    Contiguous 1D array.\n"
      "policy : str\n    Execution policy: 'seq' or 'par'.");
```

### Step 5: Update CMakeLists.txt

Add `src/reduce.cpp` to the `nanobind_add_module()` call. If the feature needs extra HPX components (e.g., `HPX::iostreams_component`), add them to `target_link_libraries`.

**Validation checkpoint**: run `pip install --no-build-isolation -ve .` and confirm `src/hpyx/_core.*.so` rebuilds without errors before proceeding.

### Step 6: Create Python Wrapper

Create the Python package `src/hpyx/reduce/` with:

```python
# src/hpyx/reduce/__init__.py
from ._reduce import reduce_sum

__all__ = ["reduce_sum"]
```

```python
# src/hpyx/reduce/_reduce.py
from __future__ import annotations

from typing import Literal

import numpy as np
import numpy.typing as npt

from .._core import reduce_sum as _reduce_sum


def reduce_sum(
    data: npt.NDArray[np.float64],
    *,
    policy: Literal["seq", "par"] = "par",
) -> float:
    """Parallel sum reduction over a 1D float64 array.

    Parameters
    ----------
    data
        Contiguous 1D NumPy array of float64.
    policy
        Execution policy. ``"seq"`` runs sequentially;
        ``"par"`` uses the HPX thread pool.

    Returns
    -------
    float
        The sum of all elements in ``data``.
    """
    if data.dtype != np.float64:
        raise TypeError(f"data must be float64, got {data.dtype}")
    if data.ndim != 1:
        raise ValueError(f"data must be 1D, got {data.ndim}D")
    if not data.flags.c_contiguous:
        data = np.ascontiguousarray(data)
    return _reduce_sum(data, policy)
```

### Step 7: Export from Package

Update `src/hpyx/__init__.py` to import and export the new module.

### Step 8: Create Tests

Create `tests/test_<feature_name>.py` with:
- Basic functionality tests
- Different input types (scalars, lists, numpy arrays)
- Error handling tests (invalid inputs, edge cases)
- Execution policy tests (seq, par if supported)
- NumPy integration tests if applicable

**Validation checkpoint**: run `pixi run test tests/test_<feature_name>.py` and confirm all tests pass before committing.

### Step 9: Create Benchmarks (Optional)

Create `benchmarks/test_bench_<feature_name>.py` with:
- HPX vs NumPy comparison (if applicable)
- HPX vs pure Python comparison
- Thread scaling tests
- Different data sizes

## File Checklist

After scaffolding, verify all files are created:

- [ ] `src/<feature_name>.cpp` — C++ implementation
- [ ] `src/<feature_name>.hpp` — C++ header
- [ ] `src/bind.cpp` — Updated with new bindings
- [ ] `CMakeLists.txt` — Updated with new source file
- [ ] `src/hpyx/<feature_name>/__init__.py` — Python package
- [ ] `src/hpyx/<feature_name>/_<feature_name>.py` — Python wrapper
- [ ] `src/hpyx/__init__.py` — Updated exports
- [ ] `tests/test_<feature_name>.py` — Test suite
- [ ] `benchmarks/test_bench_<feature_name>.py` — Benchmarks (optional)

## Reference Patterns

Study these existing files as templates:
- **Pure C++ operation**: `src/algorithms.cpp` (`dot1d`)
- **Python callback wrapper**: `src/futures.cpp` (`hpx_async`)
- **Class binding**: `src/bind.cpp` (`bind_hpx_future`)
- **Python wrapper**: `src/hpyx/futures/_submit.py`
- **Benchmarks**: `benchmarks/test_bench_hpx_linalg.py`
