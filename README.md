# HPyX: Python Bindings for HPX C++ Parallelism Library

[![DOI](https://zenodo.org/badge/966326660.svg)](https://zenodo.org/badge/latestdoi/966326660)
<span><img src="https://img.shields.io/badge/SSEC-Project-purple?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA0AAAAOCAQAAABedl5ZAAAACXBIWXMAAAHKAAABygHMtnUxAAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAMNJREFUGBltwcEqwwEcAOAfc1F2sNsOTqSlNUopSv5jW1YzHHYY/6YtLa1Jy4mbl3Bz8QIeyKM4fMaUxr4vZnEpjWnmLMSYCysxTcddhF25+EvJia5hhCudULAePyRalvUteXIfBgYxJufRuaKuprKsbDjVUrUj40FNQ11PTzEmrCmrevPhRcVQai8m1PRVvOPZgX2JttWYsGhD3atbHWcyUqX4oqDtJkJiJHUYv+R1JbaNHJmP/+Q1HLu2GbNoSm3Ft0+Y1YMdPSTSwQAAAABJRU5ErkJggg==&style=plastic" /><span>
![BSD License](https://badgen.net/badge/license/BSD-3-Clause/blue)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[![Documentation Status](https://readthedocs.org/projects/hpyx/badge/?version=latest)](https://hpyx.readthedocs.io/en/latest/)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/uw-ssec/HPyX/main.svg)](https://results.pre-commit.ci/latest/github/uw-ssec/HPyX/main)
[![CI](https://github.com/uw-ssec/HPyX/actions/workflows/ci.yml/badge.svg)](https://github.com/uw-ssec/HPyX/actions/workflows/ci.yml)

## Project Overview

HPyX provides Python bindings for the HPX C++ Parallelism Library using Nanobind
and leveraging Python 3.13's free-threading capabilities. This project aims to make
HPX's powerful parallel processing features accessible to Python developers
while achieving optimal performance through true multi-threading.

**Status**: HPyX is currently in active development as part of a research project
at the University of Washington's Scientific Software Engineering Center (SSEC).
The project is experimental and APIs may change as we explore optimal integration
patterns between Python's free-threading mode and HPX's parallel execution model.

## What is HPX?

HPX (High Performance ParalleX) is a C++ Standard Library for Concurrency and
Parallelism that implements modern C++ parallelism features defined by the C++
Standard. It provides:

- A unified API for local and remote parallel operations
- Asynchronous execution through futures and dataflow
- Fine-grained task parallelism
- Support for distributed computing
- Performance counter frameworks for runtime adaptivity

## Features

- **Python Interface**: Clean Python API for HPX's parallel algorithms and components
- **True Parallel Execution**: Leverages Python 3.13's experimental free-threading mode
- **High-Performance Bindings**: Uses Nanobind for minimal-overhead C++ integration
- **Pythonic Design**: APIs that follow Python conventions while exposing HPX capabilities
- **Comprehensive Testing**: Automated testing and benchmarking framework
- **Cross-Platform Support**: Builds consistently on Linux, macOS, and Windows

### Current Development Focus

- Core HPX binding infrastructure
- Python 3.13 free-threading compatibility
- Parallel algorithm implementations
- Performance optimization and benchmarking
- API design and developer experience

## Installation and Building

**Note**: HPyX is currently in active development. Pre-built packages are not yet
available. Installation requires building from source using the provided build system.

HPyX uses [pixi](https://pixi.sh/) for environment and dependency management,
which provides reproducible builds and handles complex C++ dependencies automatically.

### Prerequisites

- Install pixi following the instructions on the
  [pixi documentation](https://pixi.sh/latest/install/)
- Python 3.13 built with `--disable-gil` option for optimal performance
- Modern C++ compiler with C++17 support (GCC 8+, Clang 8+, MSVC 2019+)

### Setting up the environment

Clone the repository and navigate to the project directory:

```bash
git clone https://github.com/uw-ssec/HPyX.git
cd HPyX
```

HPyX provides predefined pixi environments (see also `docs/CONTRIBUTING.md`):

| Environment | Purpose |
| ----------- | ------- |
| `py313t` | Default development (Python 3.13 free-threading) + editable HPyX install |
| `test-py313t` | Run test suite (pytest + test deps) |
| `build-py313t` | Build distributions (sdist / wheel + verification) |
| `benchmark-py313t` | Performance benchmarking (pytest-benchmark etc.) |
| `docs` | Documentation authoring (MkDocs + plugins) |
| `linting` | Lint / formatting (pre-commit) |
| `py313t-src` | Advanced: build HPX from source & test against it |

To create and activate an environment:

```bash
pixi shell -e py313t
```

**Note**: Environments that include the `hpyx` feature (e.g. `py313t`) automatically install HPyX in editable mode.

### Available Tasks (High-Level)

```bash
pixi run get-python-version   # Show Python version
pixi run test                 # Run full test suite
pixi run benchmark            # Run benchmarks
pixi run lint                 # Lint & format (pre-commit hooks)
pixi run build                # Build sdist + wheel
```

Underlying / environment-scoped examples:

```bash
pixi run -e build-py313t build-sdist
pixi run -e build-py313t build-wheel
pixi run -e build-py313t build-wheel-and-test   # build wheel, install, print versions
pixi run -e benchmark-py313t run-benchmark keyword_expression=for_loop
pixi run -e benchmark-py313t run-benchmark keyword_expression=hpx_linalg
```

### Building the Package

High-level aggregated build:

```bash
pixi run build    # Builds sdist (dist/) + wheel (wheelhouse/)
```

Granular control:

```bash
pixi run -e build-py313t build-sdist
pixi run -e build-py313t build-wheel
pixi run -e build-py313t build-wheel-and-test
```

### Running tests

To run the test suite:

```bash
pixi run test
```

### Performance Benchmarking

Run all benchmarks:

```bash
pixi run benchmark
```

Filter by keyword (raw task):

```bash
pixi run -e benchmark-py313t run-benchmark keyword_expression=for_loop
pixi run -e benchmark-py313t run-benchmark keyword_expression=hpx_linalg
```

Benchmark configuration highlights: group-by function, warmup enabled, minimum 3 rounds, time unit milliseconds.

#### Troubleshooting Test Issues

If you encounter errors related to duplicate library paths on macOS/Unix systems, such as:

```text
duplicate LC_RPATH '@loader_path'
```

Run the library path fix task (Unix):

```bash
pixi run -e py313t fix-lib-paths
```

This script will automatically detect and remove duplicate RPATH entries from dynamic libraries in your conda environment, which can occur due to dependency conflicts between conda packages.

### Code quality and linting

To run code quality checks and formatting:

```bash
pixi run lint
```

### Additional utilities

Check the Python version in your current environment:

```bash
pixi run get-python-version
```

### Documentation Development

Live docs server:

```bash
pixi run -e docs start
```

Simulate Read the Docs build (maintainers):

```bash
pixi run -e docs rtd-publish
```

## Development

HPyX uses [pixi](https://pixi.sh/) for reproducible development environments and
dependency management. This approach ensures consistent builds across different
platforms and simplifies the complex build process for HPX and its dependencies.

### Development Environment

See the environment table above (duplicated list removed for brevity).

### Build Process

The build system integrates several complex components:

1. **HPX C++ Library**: Conda package or optional source build via `py313t-src` environment
2. **Nanobind Integration**: Efficient Python–C++ bindings with minimal overhead
3. **Free-Threading Support**: Optimizations for Python 3.13's experimental free-threading mode
4. **Cross-Platform Support**: Consistent builds on Linux, macOS, and Windows

### Technical Approach

Our development approach consists of:

1. **Core Binding Layer**: Low-level bindings for HPX C++ core functionality using Nanobind
2. **High-Level Python API**: A Pythonic interface that wraps the core bindings
3. **Free-Threading Integration**: Mechanisms to ensure the bindings work optimally with Python's free-threading mode
4. **Comprehensive Testing**: Benchmarks + functionality tests to verify behavior

### Advanced: Building HPX From Source

For testing unreleased HPX versions or allocator variants use the `py313t-src` environment:

```bash
pixi shell -e py313t-src
```

Key tasks:

```bash
# Build specific HPX (defaults: tag=v1.11.0-rc1 malloc=system build_dir=build)
pixi run build-hpx tag=v1.11.0-rc1 malloc=system

# Install latest RC HPX + reinstall HPyX (all extras)
pixi run install-latest-lib

# Install stable HPX + reinstall HPyX (all extras)
pixi run install-stable-lib
```

Arguments:

- tag – HPX git tag
- malloc – allocator (system default)
- build_dir – build directory name

Helper tasks (implicit): `_fetch-hpx-source`, `_pip-install-all`, `_restore-submodule`.

## Contributing

We welcome contributions to HPyX! Whether you're interested in fixing bugs, adding new features, improving documentation, or helping with testing, your contributions are valuable.

Please see our [Contributing Guide](docs/CONTRIBUTING.md) for detailed information on:

- Setting up the development environment with pixi
- Understanding the build system and HPX integration
- Running tests and benchmarks
- Code quality standards and linting
- Pull request process

For a quick start:

1. Install [pixi](https://pixi.sh/) for environment management
2. Clone the repository and activate the development environment:

   ```bash
   git clone https://github.com/uw-ssec/HPyX.git
   cd HPyX
   pixi shell -e py313t
   ```

3. (Optional) Reinstall in editable mode (already done in `py313t`):

   ```bash
   pip install -e '.[all]'
   ```

4. Run tests to verify your setup:

   ```bash
   pixi run test
   ```

You can also explore other development tasks:

```bash
pixi run benchmark    # Run performance benchmarks
pixi run lint        # Check code quality and formatting  
pixi run build       # Build distribution packages
```

Thanks to our contributors so far!

[![Contributors](https://contrib.rocks/image?repo=uw-ssec/HPyX)](https://github.com/uw-ssec/HPyX/graphs/contributors)

## License

HPyX is licensed under the BSD 3-Clause License. See the [LICENSE](LICENSE) file
for details.
