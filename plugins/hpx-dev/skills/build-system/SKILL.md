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
  HPX::hpx
  HPX::wrap_main
  HPX::iostreams_component
)
```

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

When the latest HPX version is not yet on conda-forge:

```bash
pixi shell -e py313t-src
pixi run build-hpx tag=v1.11.0-rc1
pixi run install-latest-lib
```

This uses `scripts/build.sh` to:
1. Checkout the specified HPX version in `vendor/hpx/`
2. Build HPX with CMake + Ninja
3. Install to the pixi environment prefix

## Common Build Issues

### Missing HPX Package
```
Could not find a package configuration file provided by "HPX"
```
**Fix**: Ensure HPX is installed: `pixi shell -e py313t` (conda-forge provides HPX)

### Nanobind Not Found
```
Could not find a configuration file for package "nanobind"
```
**Fix**: Run `pip install nanobind>=2.7.0` or ensure the pixi environment is active

### RPATH Issues on macOS
```
dyld: Library not loaded...
```
**Fix**: The CMakeLists.txt sets `CMAKE_INSTALL_RPATH "$ORIGIN"`. On macOS, the `dynamic_lookup` flag handles Python symbol resolution. Ensure building within the pixi environment.

### Link Errors with HPX Components
```
undefined reference to `hpx::some_function`
```
**Fix**: Add the missing HPX component to `target_link_libraries`. Check which HPX target provides the symbol by searching `vendor/hpx/cmake/`.

### Rebuild After C++ Changes
```bash
pip install --no-build-isolation -ve .   # Editable install, fast rebuild
# Or with auto-rebuild on import:
pip install --no-build-isolation -ve . -Ceditable.rebuild=true
```

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

# 5. Benchmark (optional)
pixi run benchmark
```
