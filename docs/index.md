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

!!! tip "Hands-on tour"
    Prefer to learn by running code? Start with the
    [**Quickstart notebook**](quickstart.ipynb) — a runnable walkthrough of
    every Phase 1 feature in this guide.

HPyX v1 auto-initializes the HPX runtime on first use — no setup boilerplate required:

```python
import hpyx
from hpyx.multiprocessing import for_loop

# Submit work asynchronously — runtime starts automatically
future = hpyx.async_(lambda x: x * x, 5)
print(future.result())  # 25

# Compose futures with the standard combinators
f1 = hpyx.async_(lambda: 1)
f2 = hpyx.async_(lambda: 2)
print(hpyx.when_all(f1, f2).result())  # (1, 2)

# Parallel iteration
data = [1, 2, 3]
for_loop(lambda x: x + 1, data, "seq")
print(data)  # [2, 3, 4]
```

To control thread count or configuration explicitly:

```python
import hpyx

hpyx.init(os_threads=8)  # or set HPYX_OS_THREADS=8 in the environment
```

For more details, see the [Usage Guide](usage.md).

---

## API Reference

Full API documentation is available in the [API Reference](reference/api.md).

---

## Architecture Decisions

Significant design choices and their rationale are recorded in the [Architecture Decisions](architecture-decisions.md) log.

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
