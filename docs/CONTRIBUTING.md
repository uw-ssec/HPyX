# Contributing to HPyX

Thank you for your interest in contributing to HPyX! This guide will help you set up your development environment and understand the workflow for contributing to this project.

## Development Environment Setup

HPyX uses [pixi](https://pixi.sh/) for environment and dependency management, which ensures consistent development environments across different platforms.

### Prerequisites

1. Install pixi following the instructions on the [pixi documentation](https://pixi.sh/latest/install/)
2. Python 3.13 (preferably built with `--disable-gil` for optimal free-threading performance)
3. Modern C++ compiler with C++17 support (GCC 8+, Clang 8+, MSVC 2019+)

### Getting Started

1. Fork and clone the repository:

   ```bash
   git clone https://github.com/yourusername/HPyX.git
   cd HPyX
   ```

2. Set up the development environment using one of the predefined environments:

   - `py313t` - Python 3.13 with free threading for testing
   - `py313` - Standard Python 3.13 environment for testing
   - `build313t` - Environment for building with Python 3.13 free threading
   - `docs` - Environment for documentation development
   - `linting` - Environment for code linting

3. Activate your chosen environment:

   ```bash
   pixi shell -e py313
   ```

## Development Workflow

### Environment Management

Check your Python version:

```bash
pixi run get-python-version
```

### Building and Installation

#### Standard Installation

Install the package in development mode:

```bash
pixi run install
```

Install with all optional dependencies:

```bash
pixi run install-all
```

#### Advanced Installation Options

For working with the latest HPX features:

```bash
pixi run install-latest        # Install with latest HPX build
pixi run install-all-latest    # Install all dependencies with latest HPX
```

#### Building Source Dependencies

HPyX builds HPX from source for optimal performance. The following tasks manage HPX builds:

```bash
pixi run fetch-hpx-source     # Initialize/update HPX submodule
pixi run build-hpx-stable     # Build stable HPX version (v1.11.0)
pixi run build-hpx-latest     # Build latest HPX version (v1.11.0-rc1)
```

#### Building Distribution Packages

```bash
pixi run build-wheel          # Build wheel distribution
```

#### Uninstalling

```bash
pixi run uninstall           # Remove HPyX package
```

### Testing

Run the test suite:

```bash
pixi run test
```

The test task automatically:

- Builds the stable HPX version
- Installs the package
- Runs pytest with verbose output and short tracebacks

### Benchmarking

Run performance benchmarks:

```bash
pixi run benchmark                    # Run all benchmarks
pixi run benchmark --keyword_expression="specific_test"  # Run specific benchmarks
```

Benchmarks are configured to:

- Group results by function
- Enable warmup runs
- Run minimum 3 rounds per test
- Display timing in milliseconds

### Code Quality and Linting

#### Pre-commit Setup

HPyX uses pre-commit hooks to maintain code quality. Run linting on all files:

```bash
pixi run lint
```

Clean pre-commit cache:

```bash
pixi run pre-commit-clean
```

The linting process:

- Runs pre-commit hooks on all files
- Shows diffs when failures occur
- Includes formatters, linters, and other code quality tools

### Documentation

#### Working with Documentation

HPyX uses MkDocs for documentation. To work on documentation:

1. Switch to the docs environment:

   ```bash
   pixi shell -e docs
   ```

2. Start the documentation server:

   ```bash
   pixi run start  # Available in docs environment
   ```

3. Build documentation for Read the Docs:

   ```bash
   pixi run rtd-publish  # Available in docs environment
   ```

## Project Structure

### Key Directories

- `src/` - C++ source code and Python bindings
- `src/hpyx/` - Python package source
- `tests/` - Test suite
- `benchmarks/` - Performance benchmarks
- `docs/` - Documentation source
- `vendor/hpx/` - HPX C++ library submodule
- `scripts/` - Build and utility scripts

### Configuration Files

- `pixi.toml` - Project configuration and task definitions
- `pyproject.toml` - Python package configuration
- `CMakeLists.txt` - C++ build configuration

## Understanding HPyX Architecture

HPyX consists of several key components:

1. **Core Binding Layer**: Low-level Nanobind bindings for HPX C++ functionality
2. **High-Level Python API**: Pythonic interface wrapping core bindings
3. **Free-Threading Integration**: Optimizations for Python 3.13's free-threading mode
4. **Testing Framework**: Comprehensive tests for functionality and performance

## Contribution Guidelines

### Code Style

- Follow existing code conventions
- Use pre-commit hooks (run `pixi run lint` before committing)
- Write clear, descriptive commit messages

### Development Testing

- Add tests for new functionality
- Ensure all tests pass with `pixi run test`
- Include benchmarks for performance-critical features

### Documentation Guidelines

- Update documentation for API changes
- Include docstrings for new functions and classes
- Add examples for new features

### Pull Request Process

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Run tests and linting: `pixi run test && pixi run lint`
5. Update documentation as needed
6. Submit a pull request with a clear description

## Advanced Development

### Custom HPX Builds

The build system supports custom HPX configurations:

```bash
# Build with specific HPX version
pixi run build-hpx --tag=v1.10.0

# Build with custom malloc implementation
pixi run build-hpx --malloc=tcmalloc

# Build in custom directory
pixi run build-hpx --build_dir=custom_build
```

### Debugging

- Use `pixi run build-hpx-stable` to ensure consistent HPX builds
- Check `vendor/hpx/build/` for HPX build artifacts
- Run `pixi run restore-submodule` to reset HPX submodule state

## Getting Help

- Check existing [GitHub Issues](https://github.com/uw-ssec/HPyX/issues)
- Read the [HPX documentation](https://hpx-docs.stellar-group.org/) for C++ library details
- Review [Nanobind documentation](https://nanobind.readthedocs.io/) for binding patterns
- Ask questions in GitHub Discussions

## License

By contributing to HPyX, you agree that your contributions will be licensed under the BSD 3-Clause License.
