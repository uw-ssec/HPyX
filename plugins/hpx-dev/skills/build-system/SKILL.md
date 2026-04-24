---
name: build-system
description: Guides building and configuring HPyX (CMake + scikit-build-core + Nanobind + pixi), diagnoses CMake/compilation/link errors, explains `nanobind_add_module` usage, configures conda-forge dependencies, and resolves RPATH issues. Use when the user asks about "build system", "CMake configuration", "scikit-build-core", "pixi", "build errors", "compilation errors", "link errors", "nanobind_add_module", "CMakeLists.txt", "pyproject.toml", "pixi.toml", "build HPX from source", "install dependencies", "RPATH", "conda-forge", or hits build failures, missing library errors, or environment setup issues.
---

# HPyX Build System

## Build Stack Overview

```
pixi.toml          → Environment & dependency management (conda-forge + PyPI)
pyproject.toml      → Python package metadata + scikit-build-core config
CMakeLists.txt      → C++ compilation, Nanobind module, HPX linking
```

The build flow:
1. `pixi` resolves and installs all dependencies (HPX, Nanobind, compilers, Python 3.13t)
2. `pip install -e .` (or `pixi run test`) triggers scikit-build-core
3. scikit-build-core invokes CMake to compile the `_core` Nanobind module
4. CMake finds HPX, Nanobind, and Python, then links everything together
5. The compiled `_core.so` / `_core.pyd` is installed into the `hpyx` package

## Pixi Environments

Key environments defined in `pixi.toml`:

| Environment | Purpose | Features |
|---|---|---|
| `py313t` | Default development | Python 3.13 free-threading + HPX + HPyX |
| `test-py313t` | Testing | Above + pytest |
| `benchmark-py313t` | Benchmarking | Above + pytest-benchmark + threadpoolctl |
| `build-py313t` | Distribution builds | Python 3.13 free-threading + build tools |
| `docs` | Documentation | Python 3.13 + MkDocs |
| `linting` | Code quality | Python 3.13 + pre-commit |
| `py313t-src` | Build HPX from source | Python 3.13 free-threading + HPX build deps |

Common pixi commands:
```bash
pixi shell -e py313t          # Enter dev environment
pixi run test                  # Run tests
pixi run benchmark             # Run benchmarks
pixi run lint                  # Run linters
pixi run -e docs start         # Start docs server
```

## CMake Configuration

The `CMakeLists.txt` key sections:

### Finding Dependencies
```cmake
find_package(Python 3.13 COMPONENTS Interpreter Development.Module REQUIRED)
find_package(nanobind CONFIG REQUIRED)
find_package(HPX REQUIRED)
```

### Building the Module
```cmake
nanobind_add_module(
  _core
  FREE_THREADED          # Required for Python 3.13 free-threading
  src/bind.cpp
  src/init_hpx.cpp
  src/algorithms.cpp
  src/futures.cpp
  # Add new source files here
)
```

### Linking HPX Libraries
```cmake
target_link_libraries(_core PRIVATE
  HPX::hpx                  # main HPX library (pulls in libs/full via HPX_WITH_DISTRIBUTED_RUNTIME)
  HPX::wrap_main            # replaces main() to bootstrap HPX command-line parsing (Boost.ProgramOptions)
  HPX::iostreams_component  # hpx::cout support
)
```

**Why `HPX::wrap_main` is required**: `hpx::start` internally parses `argc`/`argv` via Boost.ProgramOptions. Without `wrap_main`, command-line argument processing may fail in a Python extension context where there is no conventional `main()`.

### Adding a New Source File

1. Create `src/new_feature.cpp` and `src/new_feature.hpp`
2. Add to `nanobind_add_module()`:
   ```cmake
   nanobind_add_module(
     _core
     FREE_THREADED
     src/bind.cpp
     src/init_hpx.cpp
     src/algorithms.cpp
     src/futures.cpp
     src/new_feature.cpp    # New file
   )
   ```
3. If the new feature needs additional HPX components, add to `target_link_libraries`:
   ```cmake
   target_link_libraries(_core PRIVATE
     HPX::hpx
     HPX::wrap_main
     HPX::iostreams_component
     HPX::new_component       # Additional HPX component
   )
   ```

## pyproject.toml Key Settings

```toml
[build-system]
requires = ["scikit-build-core>=0.10", "nanobind>=2.7.0"]
build-backend = "scikit_build_core.build"

[tool.scikit-build]
wheel.packages = ["src/hpyx"]
```

The `src/` layout means Python sources live in `src/hpyx/` while C++ sources are in `src/` at the project root.

## Building HPX from Source

When the conda-forge HPX build lags behind a needed upstream feature, build from the `vendor/hpx/` submodule:

```bash
pixi shell -e py313t-src
pixi run build-hpx tag=v1.11.0-rc1
pixi run install-latest-lib
```

For full CMake options, the vendor vs conda-forge relationship, runtime config strings (`cfg` keys like `hpx.os_threads!=N`), and the C++17 requirement, see **`references/hpx-from-source.md`**.

## Development Workflow

```bash
# 1. Enter dev environment
pixi shell -e py313t

# 2. Edit C++ source files

# 3. Rebuild (fast, editable)
pip install --no-build-isolation -ve .

# 4. Verify the rebuild: _core.*.so should exist under src/hpyx/
ls src/hpyx/_core*.so

# 5. Test
pixi run test

# 6. Benchmark (optional)
pixi run benchmark
```

## Diagnosing Build Failures

For common errors — missing HPX package, Nanobind not found, macOS RPATH issues, HPX component link errors, rebuild commands, Python ABI mismatch — see **`references/build-errors.md`**.

## Additional Resources

### Reference Files

- **`references/hpx-from-source.md`** — Building HPX from vendor submodule, CMake options, runtime config strings, C++17 requirement
- **`references/build-errors.md`** — Common build errors with diagnostic commands and fixes
