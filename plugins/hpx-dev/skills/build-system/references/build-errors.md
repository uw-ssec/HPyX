# Common Build Issues

Diagnostic reference for HPyX build failures.

## Missing HPX Package

```
Could not find a package configuration file provided by "HPX"
```

**Fix**: Ensure HPX is installed. Enter the pixi environment with `pixi shell -e py313t` — conda-forge provides HPX via the environment's installed packages.

## Nanobind Not Found

```
Could not find a configuration file for package "nanobind"
```

**Fix**: Run `pip install nanobind>=2.7.0`, or ensure the pixi environment is active. Nanobind is a build-system requirement in `pyproject.toml`, so scikit-build-core should install it automatically during `pip install -e .`.

## RPATH Issues on macOS

```
dyld: Library not loaded...
```

**Fix**: `CMakeLists.txt` sets `CMAKE_INSTALL_RPATH "$ORIGIN"`. On macOS, the `dynamic_lookup` flag handles Python symbol resolution. Build within the pixi environment so that HPX's library paths resolve correctly.

## Link Errors with HPX Components

```
undefined reference to `hpx::some_function`
```

**Fix**: Add the missing HPX component to `target_link_libraries`. To find which HPX target provides the symbol:

```bash
# Search the HPX CMake targets for the component exporting the symbol:
grep -r "some_function" vendor/hpx/cmake/
# Or inspect installed HPX CMake config files in the pixi prefix:
find "$(pixi info --json | jq -r '.environments_info[0].prefix')" -name "HPX*Targets*.cmake"
```

Common HPX components:
- `HPX::hpx` — main library (most symbols)
- `HPX::wrap_main` — bootstrap for `argc`/`argv` parsing
- `HPX::iostreams_component` — `hpx::cout`
- `HPX::component` — distributed components (not used by HPyX)

## Rebuild After C++ Changes

```bash
# Editable install, fast rebuild:
pip install --no-build-isolation -ve .

# With auto-rebuild on import (recommended for iterative development):
pip install --no-build-isolation -ve . -Ceditable.rebuild=true
```

After rebuild, verify `_core.*.so` exists under `src/hpyx/`:

```bash
ls src/hpyx/_core*.so
```

## Python Version Mismatch

If the `_core` module loads but imports fail with ABI errors, confirm the build used the free-threaded Python 3.13 ABI. The `FREE_THREADED` flag in `nanobind_add_module` requires a free-threading-capable Python. Enter the right environment:

```bash
pixi shell -e py313t  # Free-threaded Python 3.13
python -c "import sys; print(sys._is_gil_enabled())"  # should print False
```
