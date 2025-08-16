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

   - `py313t` - Python 3.13 with free threading for development and testing
   - `test-py313t` - Testing environment with all test dependencies
   - `build-py313t` - Build environment for creating distribution packages
   - `benchmark-py313t` - Performance benchmarking with specialized tools
   - `docs` - Documentation development with MkDocs and extensions
   - `linting` - Code quality checks and pre-commit hooks
   - `py313t-src` - Environment for building HPX from source (experimental)

3. Activate your chosen environment:

   ```bash
   pixi shell -e py313t
   ```

**Note**: The `py313t` environment automatically installs HPyX in development mode with all optional dependencies when activated.

## Development Workflow

### Environment Management

Check your Python version:

```bash
pixi run get-python-version
```

### Building and Installation

**Note**: Most installation tasks are currently integrated into the pixi environments. The `py313t` environment automatically handles package installation in development mode.

#### Manual Installation (if needed)

For manual installation in a specific environment:

```bash
pixi shell -e py313t
pip install -e ".[all]"  # Development mode with all dependencies
pip install -e .         # Development mode, minimal dependencies
```

#### Building Distribution Packages

Build source distribution and wheel packages:

```bash
pixi run build              # Build both source distribution and wheel
```

### Testing

Run the test suite:

```bash
pixi run test
```

The test task:

- Uses the `test-py313t` environment with all test dependencies
- Runs pytest with verbose output and short tracebacks

### Benchmarking

Run performance benchmarks:

```bash
pixi run benchmark                         # Run all benchmarks
```

You can also filter benchmarks using pytest's keyword expressions by passing arguments:

```bash
# Note: Benchmark filtering is handled internally by the benchmark task
# Check the benchmark task configuration for filtering options
```

The benchmark task:

- Uses the `benchmark-py313t` environment with specialized profiling tools
- Groups results by function for better organization
- Enables warmup runs for accurate measurements
- Runs minimum 3 rounds per test for statistical reliability
- Displays timing in milliseconds
- Supports keyword filtering for running specific benchmarks

### Code Quality and Linting

#### Pre-commit Setup

HPyX uses pre-commit hooks to maintain code quality. Run linting on all files:

```bash
pixi run lint
```

The linting task:

- Uses the `linting` environment with pre-commit and formatting tools
- Runs pre-commit hooks on all files
- Shows diffs when failures occur
- Includes formatters, linters, and other code quality tools

### Documentation

#### Working with Documentation

HPyX uses MkDocs for documentation. To work on documentation:

1. Start the documentation server (requires the docs environment):

   ```bash
   pixi run -e docs start
   ```

   Open the url provided in the terminal.

2. For testing out the Read the Docs publishing (maintainers only):

   ```bash
   pixi run -e docs rtd-publish
   ```

   This will create an `html` directory with the built documentation.

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

### Development Utilities

#### Check Python Version

```bash
pixi run get-python-version
```

#### Available Development Tasks

```bash
pixi run test          # Run the complete test suite
pixi run benchmark     # Execute performance benchmarks
pixi run lint          # Run code quality checks and formatting
pixi run build         # Build distribution packages
```

## Advanced Development

### Working with HPX Source Builds

For advanced development that requires building HPX from source, use the experimental `py313t-src` environment:

```bash
pixi shell -e py313t-src
```

This environment provides tools for:

- Building HPX from source with different configurations
- Testing against development versions of HPX
- Custom HPX build options and parameters

**Note**: Source builds are experimental and primarily for advanced development use cases.

### Debugging

- Use the appropriate pixi environment for your development task
- Check build logs and outputs within each environment
- The `py313t` environment provides the most stable development setup
- For HPX-specific issues, the `py313t-src` environment allows source-level debugging

## Getting Help

- Check existing [GitHub Issues](https://github.com/uw-ssec/HPyX/issues)
- Read the [HPX documentation](https://hpx-docs.stellar-group.org/) for C++ library details
- Review [Nanobind documentation](https://nanobind.readthedocs.io/) for binding patterns
- Ask questions in GitHub Discussions

## License

By contributing to HPyX, you agree that your contributions will be licensed under the BSD 3-Clause License.
