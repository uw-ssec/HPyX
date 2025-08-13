# Welcome to HPyX Documentation

HPyX is a high-performance Python library providing bindings to the HPX C++ runtime system, enabling efficient parallel and distributed computing in Python. This documentation will help you get started, understand the architecture, and use HPyX effectively for your scientific and engineering workloads.

## Key Features

- Pythonic interface to HPX parallelism and distributed computing
- Asynchronous programming with futures
- Parallel processing with for_loop
- Seamless integration with NumPy
- Free-threading support for Python 3.13+
- Comprehensive API and usage documentation

---

## Getting Started

HPyX provides:

- `HPXRuntime`: Context manager for HPX runtime lifecycle
- `hpyx.futures.submit`: Submit functions for asynchronous execution
- `hpyx.multiprocessing.for_loop`: Parallel iteration over collections

**Example:**

```python
from hpyx.runtime import HPXRuntime
from hpyx.futures import submit
from hpyx.multiprocessing import for_loop

with HPXRuntime():
	future = submit(lambda x: x * x, 5)
	print(future.get())
	data = [1, 2, 3]
	for_loop(lambda x: x + 1, data, "seq")
	print(data)
```

For more details, see the [Usage Guide](usage.md).

---

## API Reference

Full API documentation is available in the [API Reference](reference/api.md).

---

## Usage Guide

The [Usage Guide](usage.md) provides comprehensive examples and best practices for:

- Runtime management
- Asynchronous programming with futures
- Parallel processing with for_loop
- Working with NumPy
- Error handling
- Performance considerations
- Best practices for scalable and efficient code

---

## Contributing

Interested in contributing? See the [Contributing Guide](CONTRIBUTING.md) for:

- Development environment setup
- Building and testing
- Benchmarking
- Linting and code quality
- Documentation workflow
- Project structure and architecture
- Pull request process

---

## Project Structure

- `src/` – C++ source code and Python bindings
- `src/hpyx/` – Python package source
- `tests/` – Test suite
- `benchmarks/` – Performance benchmarks
- `docs/` – Documentation source
- `vendor/hpx/` – HPX C++ library submodule
- `scripts/` – Build and utility scripts

---

## Getting Help

- [GitHub Issues](https://github.com/uw-ssec/HPyX/issues)
- [HPX documentation](https://hpx-docs.stellar-group.org/)
- [Nanobind documentation](https://nanobind.readthedocs.io/)

---

## License

HPyX is released under the BSD 3-Clause License. By contributing, you agree your contributions will be licensed under the same terms.
