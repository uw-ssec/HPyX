# Building HPX from Source

Reference for building HPX directly from the `vendor/hpx/` submodule when the latest version is not yet available on conda-forge.

## Build Workflow

```bash
pixi shell -e py313t-src
pixi run build-hpx tag=v1.11.0-rc1
pixi run install-latest-lib
```

`scripts/build.sh` performs:
1. Checkout the specified HPX version in `vendor/hpx/`
2. Build HPX with CMake + Ninja
3. Install to the pixi environment prefix

## Key CMake Options

From `vendor/hpx/CMakeLists.txt` and `scripts/build.sh`:

| Option | HPyX setting | Purpose |
|---|---|---|
| `HPX_WITH_DISTRIBUTED_RUNTIME` | ON (default, hard to disable) | Includes `libs/full/` (AGAS stubs, init_runtime) |
| `HPX_WITH_NETWORKING` | **OFF** in HPyX | Disables all parcelports (TCP, MPI, LCI) |
| `HPX_WITH_EXAMPLES` | OFF | Skip HPX's own examples |
| `HPX_WITH_TESTS` | OFF | Skip HPX's test suite |
| `HPX_WITH_MALLOC` | `system` | Can also be `jemalloc`, `tcmalloc` |
| `HPX_WITH_APEX` | OFF | Performance counter framework, not needed |
| `HPX_WITH_CUDA` | OFF | No GPU support currently |
| `HPX_WITH_MAX_CPU_COUNT` | 64 (default) | Increase for large-core machines |
| `HPX_WITH_LOGGING` | ON | ON in debug builds |

## Vendor vs conda-forge HPX

`pixi.toml` pins `hpx = ">=1.11.0,<2"` (from conda-forge) while `vendor/hpx/` is HPX 2.0.0. **This is not a bug**: `find_package(HPX)` finds the installed conda-forge headers during normal builds — the vendor submodule is used only when building HPX from source via `scripts/build.sh`. The conda-forge package is built with `HPX_WITH_NETWORKING=ON` but HPyX disables TCP at runtime via the config string `hpx.parcel.tcp.enable!=0`.

## Runtime Config Strings

The `cfg` vector in `hpx::init_params` takes INI-style strings. Format:

- `key!=value` — **override** (force this value)
- `key=value` — **default** (use if not otherwise set)

HPyX-relevant keys:

| Key | Effect |
|---|---|
| `hpx.os_threads!=N` | Use N OS worker threads |
| `hpx.run_hpx_main!=1` | Execute the `hpx_main` function (required for HPyX's pattern) |
| `hpx.commandline.allow_unknown!=1` | Don't error on unrecognized CLI args |
| `hpx.commandline.aliasing!=0` | Disable short aliases |
| `hpx.diagnostics_on_terminate!=0` | Suppress crash diagnostics |
| `hpx.parcel.tcp.enable!=0` | Disable TCP parcelport |

## Required C++ Standard

HPX 2.0 requires **C++17**. `CMakeLists.txt` sets `CMAKE_CXX_STANDARD 17`. HPX headers use structured bindings, `if constexpr`, fold expressions, and `std::optional` throughout. C++14 will not build.
