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

Create `src/<feature_name>.cpp` with:

```cpp
#include <nanobind/nanobind.h>
// Include appropriate HPX and Nanobind headers
#include <hpx/algorithm.hpp>

namespace nb = nanobind;

namespace <feature_name> {

// Implementation following HPyX patterns:
// - Pure C++ operations: no GIL management needed
// - Python callbacks: use nb::gil_scoped_acquire
// - Return futures: use hpx::launch::deferred pattern

} // namespace <feature_name>
```

Create `src/<feature_name>.hpp` with declarations.

### Step 4: Register in bind.cpp

Add to `src/bind.cpp`:
1. `#include "<feature_name>.hpp"` at the top
2. `m.def(...)` calls inside `NB_MODULE(_core, m)` block

### Step 5: Update CMakeLists.txt

Add `src/<feature_name>.cpp` to the `nanobind_add_module()` call. If the feature requires additional HPX components, add them to `target_link_libraries`.

**Validation checkpoint**: run `pixi run build` and verify `_core.so` compiles before proceeding to the Python wrapper.

### Step 6: Create Python Wrapper

Create the Python package:

```
src/hpyx/<feature_name>/
├── __init__.py          # Re-exports the public API
└── _<feature_name>.py   # Implementation with type hints and docstrings
```

The Python wrapper should:
- Import from `hpyx._core`
- Add type hints and NumPy-style docstrings
- Validate inputs (raise clear Python exceptions)
- Provide sensible defaults
- Raise `NotImplementedError` for unimplemented execution policies

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
