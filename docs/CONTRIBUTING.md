# Contributing to HPyX

Thank you for your interest in contributing to HPyX! This guide will help you set up your development environment and understand how the pixi task system maps to common contributor workflows.

## Development Environment Setup

HPyX uses [pixi](https://pixi.sh/) for deterministic environment and dependency management across platforms.

### Prerequisites

1. Install pixi – follow the [pixi install docs](https://pixi.sh/latest/install/)
2. Python 3.13 (preferably built with `--disable-gil` for optimal free‑threading performance)
3. Modern C++ compiler with C++17 support (GCC ≥8, Clang ≥8, MSVC 2019+)

### Getting Started

1. Fork and clone the repository:

   ```bash
   git clone https://github.com/yourusername/HPyX.git
   cd HPyX
   ```

2. Choose and activate a predefined environment:

   | Environment | Purpose |
   | ----------- | ------- |
   | `py313t` | Default development (Python 3.13 free‑threading) + editable HPyX install |
   | `test-py313t` | Run the test suite (pytest + test deps) |
   | `build-py313t` | Build distributions (sdist/wheel + verification) |
   | `benchmark-py313t` | Performance benchmarking (pytest-benchmark etc.) |
   | `docs` | Documentation authoring (MkDocs + plugins) |
   | `linting` | Lint / formatting (pre-commit hooks) |
   | `py313t-src` | Advanced: build HPX from source & test against it |

3. Activate (example):

   ```bash
   pixi shell -e py313t
   ```

**Note**: Environments containing the `hpyx` feature automatically install HPyX in editable mode.

## Development Workflow

### Environment Management

Check Python version:

```bash
pixi run get-python-version
```

### Building and Installation

Editable installation happens automatically in most dev environments. Manual commands (rarely needed):

```bash
pixi shell -e py313t
pip install -e .          # minimal deps
pip install -e '.[all]'   # all optional deps
```

#### Build Distribution Artifacts

High-level aggregated task:

```bash
pixi run build            # Builds sdist (dist/) + wheel (wheelhouse/)
```

Underlying tasks (explicit control):

```bash
pixi run -e build-py313t build-sdist
pixi run -e build-py313t build-wheel
pixi run -e build-py313t build-wheel-and-test   # build wheel, install, print versions
```

Auxiliary (used internally but callable):

```bash
pixi run -e build-py313t _install-wheel
pixi run -e build-py313t _print-versions
```

### Testing

Run full test suite:

```bash
pixi run test
```

Details:

* Uses `test-py313t` environment
* Verbose, short tracebacks (`-v --tb=short`)

### Benchmarking

Aggregate benchmarks:

```bash
pixi run benchmark
```

Filter via keyword expression (call raw task with argument):

```bash
pixi run -e benchmark-py313t run-benchmark keyword_expression=for_loop
pixi run -e benchmark-py313t run-benchmark keyword_expression=hpx_linalg
```

Benchmark configuration highlights:

* Group by function (`--benchmark-group-by=func`)
* Warmup enabled
* Minimum 3 rounds for statistical reliability
* Time unit: milliseconds

### Code Quality and Linting

Run pre-commit hooks across the repository:

```bash
pixi run lint
```

Internally runs in `linting` environment:

* Cleans pre-commit cache (`pre-commit clean`)
* Executes all hooks with diff on failure

### Documentation

HPyX uses MkDocs.

1. Live server (auto reload):

   ```bash
   pixi run -e docs start
   ```

2. Simulate Read the Docs build (maintainers):

   ```bash
   pixi run -e docs rtd-publish
   ```

   Generates `html/` output.

## Project Structure

Key directories:

* `src/` – C++ source & Python bindings
* `src/hpyx/` – Python package
* `tests/` – Unit / functional tests
* `benchmarks/` – Performance benchmarks
* `docs/` – Documentation sources
* `vendor/hpx/` – HPX C++ library submodule
* `scripts/` – Build & utility scripts

Configuration highlights:

* `pixi.toml` – Environments & tasks
* `pyproject.toml` – Python packaging config
* `CMakeLists.txt` – C++ build configuration

## Understanding HPyX Architecture

1. **Core Binding Layer** – Nanobind bindings to HPX C++
2. **High-Level Python API** – Pythonic wrappers & convenience utilities
3. **Free-Threading Integration** – Optimizations for Python 3.13 no-GIL mode
4. **Testing & Benchmarking** – Validation & performance tracking

## Contribution Guidelines

### Code Style

* Follow existing conventions
* Run `pixi run lint` before committing
* Use clear, descriptive commit messages

### Development Testing

* Add tests for new functionality
* Ensure `pixi run test` passes
* Provide benchmarks for performance-sensitive changes

### Documentation Guidelines

* Update docs for API changes
* Include docstrings for new functions/classes
* Add usage examples where helpful

### Pull Request Process

1. Fork the repository
2. Create a feature branch from `main`
3. Implement changes
4. Run validation: `pixi run test && pixi run lint`
5. Update docs if needed
6. Open a PR with a clear description (reference issues where applicable)

### Development Utilities

Check Python version:

```bash
pixi run get-python-version
```

#### Available High-Level Tasks

```bash
pixi run get-python-version   # Show Python version
pixi run test                 # Run full test suite
pixi run benchmark            # Run benchmarks
pixi run lint                 # Lint & format (pre-commit)
pixi run build                # Build sdist + wheel
```

#### Underlying Environment-Scoped Tasks

| Environment | Task | Purpose |
|-------------|------|---------|
| test-py313t | run-test | Raw pytest execution |
| benchmark-py313t | run-benchmark | Benchmarks (arg: keyword_expression=) |
| linting | linter | Run pre-commit hooks |
| linting | pre-commit-clean | Clean pre-commit cache |
| build-py313t | build-sdist | Build source distribution |
| build-py313t | build-wheel | Build wheel distribution |
| build-py313t | build-wheel-and-test | Build wheel, install, print versions |
| build-py313t | _install-wheel | Force reinstall built wheel |
| build-py313t | _print-versions | Show dependency versions |
| docs | start | Live docs server |
| docs | rtd-publish | Build docs (RTD style) |
| py313t-src | build-hpx | Build HPX from source (args: tag, malloc, build_dir) |
| py313t-src | install-latest-lib | Build RC HPX + reinstall HPyX (all extras) |
| py313t-src | install-stable-lib | Build stable HPX + reinstall HPyX (all extras) |
| py313t | fix-lib-paths | (Unix) fix HPX library paths |

(Tasks starting with an underscore are internal helpers but callable.)

## Advanced Development

### Working with HPX Source Builds (Advanced)

Use `py313t-src` when you need HPX built from source (e.g. testing a release candidate or allocator variations):

```bash
pixi shell -e py313t-src
```

Key tasks:

```bash
# Build a specific HPX version (defaults: tag=v1.11.0-rc1 malloc=system build_dir=build)
pixi run build-hpx tag=v1.11.0-rc1 malloc=system

# Install latest RC HPX + reinstall HPyX (all extras)
pixi run install-latest-lib

# Install stable HPX + reinstall HPyX (all extras)
pixi run install-stable-lib
```

Arguments for `build-hpx`:

* `tag` – HPX git tag (default: `v1.11.0-rc1`)
* `malloc` – allocator (`system` by default)
* `build_dir` – build directory name (`build` by default)

Helper tasks (invoked implicitly): `_fetch-hpx-source`, `_pip-install-all`, `_restore-submodule`.

## Debugging

* Confirm environment: `pixi env list` then `pixi shell -e <env>`
* Reproduce build issues: `pixi run -e build-py313t build-wheel-and-test`
* Inspect HPX source builds in the chosen `build_dir`
* Print dependency versions: `pixi run -e build-py313t _print-versions`
* Fix Unix library path issues: `pixi run -e py313t fix-lib-paths`

## Release Process

This project uses calendar-based versions (`YYYY.M.DD`). A typical release only requires a version bump in `pixi.toml` and a GitHub release tag.

### Steps

1. Create a branch.
2. Update the version in `pixi.toml` to `YYYY.M.DD`.
3. Create a release on GitHub with tag `vYYYY.M.DD` (same value for the release title) and use the auto‑generate feature for release notes.

### Recommended Detailed Flow

```bash
# 1. Create a branch (example date 2025.8.28)
git checkout -b release-2025.8.28

# 2. Edit pixi.toml: set [workspace] version = "2025.8.28"
git add pixi.toml
git commit -m "chore: release 2025.8.28"
git push -u origin release-2025.8.28

# Open a PR and merge after CI passes.
```

After the PR merges into `main`:

1. Navigate to GitHub → Releases → "Draft a new release".
2. Tag: `v2025.8.28` (create new tag on the main branch merge commit).
3. Release title: `v2025.8.28`.
4. Click "Generate release notes" (adjust if needed, but prefer auto format).
5. Publish.

### Notes

* If multiple releases occur the same day, append a suffix (e.g. `2025.8.28.1`) — keep the tag `v2025.8.28.1`.
* Ensure the version matches exactly between `pixi.toml` and the Git tag (minus the leading `v`).
* No separate CHANGELOG is required—GitHub auto‑generated notes act as the changelog.
* Avoid adding unrelated commits to the release branch—keep it minimal for clarity and traceability.

## Getting Help

* Review existing [GitHub Issues](https://github.com/uw-ssec/HPyX/issues)
* Read [HPX documentation](https://hpx-docs.stellar-group.org/)
* See [Nanobind documentation](https://nanobind.readthedocs.io/)
* Open discussion threads or ask questions in GitHub Discussions

## License

By contributing to HPyX, you agree that your contributions will be licensed under the BSD 3-Clause License.
