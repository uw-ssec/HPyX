# HPyX: Python Bindings for HPX C++ Parallelism Library

<span><img src="https://img.shields.io/badge/SSEC-Project-purple?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA0AAAAOCAQAAABedl5ZAAAACXBIWXMAAAHKAAABygHMtnUxAAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAMNJREFUGBltwcEqwwEcAOAfc1F2sNsOTqSlNUopSv5jW1YzHHYY/6YtLa1Jy4mbl3Bz8QIeyKM4fMaUxr4vZnEpjWnmLMSYCysxTcddhF25+EvJia5hhCudULAePyRalvUteXIfBgYxJufRuaKuprKsbDjVUrUj40FNQ11PTzEmrCmrevPhRcVQai8m1PRVvOPZgX2JttWYsGhD3atbHWcyUqX4oqDtJkJiJHUYv+R1JbaNHJmP/+Q1HLu2GbNoSm3Ft0+Y1YMdPSTSwQAAAABJRU5ErkJggg==&style=plastic" /><span>
![BSD License](https://badgen.net/badge/license/BSD-3-Clause/blue)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[![Documentation Status](https://readthedocs.org/projects/ssec-python-project-template/badge/?version=latest)](https://ssec-python-project-template.readthedocs.io/en/latest/?badge=latest)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/uw-ssec/python-project-template/main.svg)](https://results.pre-commit.ci/latest/github/uw-ssec/python-project-template/main)
[![CI](https://github.com/uw-ssec/python-project-template/actions/workflows/ci.yml/badge.svg)](https://github.com/uw-ssec/python-project-template/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/uw-ssec/python-project-template/graph/badge.svg?token=13LYMLQBZL)](https://codecov.io/gh/uw-ssec/python-project-template)

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

HPyX provides several predefined environments:

- `py313t` - Python 3.13 with free threading for testing
- `py313` - Standard Python 3.13 environment for testing
- `build313t` - Environment for building with Python 3.13 free threading

To create and activate an environment:

```bash
pixi shell -e py313
```

### Installing the package

To install the package in development mode with all optional dependencies:

```bash
pixi run install-all
```

For a standard installation:

```bash
pixi run install
```

To uninstall the package:

```bash
pixi run uninstall
```

### Building the package

To build a wheel:

```bash
pixi run build-wheel
```

### Running tests

To run tests:

```bash
pixi run test
```

#### Troubleshooting Test Issues

If you encounter errors related to duplicate library paths on macOS/Unix systems, such as:

```text
duplicate LC_RPATH '@loader_path'
```

Run the library path fix script in an environment:

```bash
pixi run fix-lib-paths
```

This script will automatically detect and remove duplicate RPATH entries from dynamic libraries in your conda environment, which can occur due to dependency conflicts between conda packages.

### Code quality

To run linting on all files:

```bash
pixi run lint
```

### Additional tasks

Check the Python version in your environment:

```bash
pixi run get-python-version
```

## Development

HPyX uses [pixi](https://pixi.sh/) for reproducible development environments and
dependency management. This approach ensures consistent builds across different
platforms and simplifies the complex build process for HPX and its dependencies.

### Development Environment

HPyX provides several predefined environments optimized for different use cases:

- `py313t` - Python 3.13 with free threading for testing and development
- `py313` - Standard Python 3.13 environment for compatibility testing
- `build313t` - Environment for building with Python 3.13 free threading
- `docs` - Environment for documentation development with MkDocs
- `linting` - Environment for code quality checks and pre-commit hooks

### Build Process

The build system integrates several complex components:

1. **HPX C++ Library**: Built from source using git submodules for optimal performance
2. **Nanobind Integration**: Efficient Python-C++ bindings with minimal overhead
3. **Free-Threading Support**: Optimizations for Python 3.13's experimental free-threading mode
4. **Cross-Platform Support**: Consistent builds on Linux, macOS, and Windows

### Technical Approach

Our development approach consists of:

1. **Core Binding Layer**: Low-level bindings for HPX C++ core functionality using Nanobind
2. **High-Level Python API**: A Pythonic interface that wraps the core bindings
3. **Free-Threading Integration**: Mechanisms to ensure the bindings work optimally with Python's free-threading mode
4. **Comprehensive Testing**: Performance benchmarks and functionality tests to verify behavior

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
   pixi shell -e py313
   ```

3. Install the package in development mode:

   ```bash
   pixi run install-all
   ```

4. Run tests to verify your setup:

   ```bash
   pixi run test
   ```

Thanks to our contributors so far!

[![Contributors](https://contrib.rocks/image?repo=uw-ssec/HPyX)](https://github.com/uw-ssec/HPyX/graphs/contributors)

## License

HPyX is licensed under the BSD 3-Clause License. See the [LICENSE](LICENSE) file
for details.
