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
and leveraging Python 3.13's free-threading capabilities. The goal is to make
HPX's powerful parallel processing features accessible to Python developers
while achieving optimal performance through true multi-threading.

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

- Python interface to HPX's parallel algorithms and components
- True parallel execution using Python 3.13's free-threading mode (experimental)
- High-performance bindings using Nanobind
- Pythonic API that follows Python conventions while exposing HPX power
- Comprehensive documentation and examples

## Installation and Building

HPyX uses [pixi](https://pixi.sh/) for environment and dependency management.
This allows for consistent development environments across platforms.

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

HPyX uses Nanobind to create efficient Python bindings for the HPX C++ library.
The build system is based on CMake and scikit-build-core for seamless
integration between C++ and Python components.

### Technical Approach

Our approach consists of the following components:

1. **Core Binding Layer**: Low-level bindings for HPX C++ core functionality
   using Nanobind
2. **High-Level Python API**: A Pythonic interface that wraps the core bindings
3. **Free-Threading Integration**: Mechanisms to ensure the bindings work
   optimally with Python's free-threading mode
4. **Testing Framework**: Comprehensive tests to verify functionality and
   performance

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

Thanks to our contributors so far!

[![Contributors](https://contrib.rocks/image?repo=uw-ssec/HPyX)](https://github.com/uw-ssec/HPyX/graphs/contributors)

## License

HPyX is licensed under the BSD 3-Clause License. See the [LICENSE](LICENSE) file
for details.
