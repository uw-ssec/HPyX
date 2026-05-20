# Adding a New HPX Binding to HPyX

This guide walks through adding a new HPX-backed function to HPyX — both
as a **Python-callback parallel algorithm** (goes in `hpyx.parallel`) and
as a **C++-native kernel** (goes in `hpyx.kernels`). The worked example
here is verified by `tests/test_contributor_example.py` — if the test
passes, every snippet in this guide is correct.

## Prerequisites

- Read `docs/codebase-analysis/hpx/CODEBASE_KNOWLEDGE.md` sections 4.3
  (parallel algorithms) and 5.1 (GIL discipline).
- Read `docs/specs/2026-04-24-hpyx-pythonic-hpx-binding-design.md`
  sections 3.3, 3.4, and 3.5 (binding patterns).
- Build HPyX with `HPYX_BUILD_CONTRIBUTOR_EXAMPLE=ON` (default in dev).

## Decision: callback track or kernel track?

| Question | Answer track |
|---|---|
| Does your function operate per-element on a Python-callable input? | **Callback track** (`hpyx.parallel.*`) |
| Does it operate on a numpy array with pure C++ math inside? | **Kernel track** (`hpyx.kernels.*`) |

Callback track is more flexible (accepts any Python callable) but slower
(GIL acquire per iteration on GIL-mode Python; truly concurrent on 3.13t).
Kernel track is always fast but only works on numeric ndarrays of
supported dtypes.

## Callback-track example: `sum_of_squares`

We're adding `hpyx.parallel.sum_of_squares(policy, iterable)` — a
transform-reduce that squares each element then sums.

### Step 1: Write the C++ binding

In `src/_core/parallel.cpp` (or for a new module, create your own file
and register it in `bind.cpp`):

```cpp
// Policy parameters arrive as individual integers matching _Token in
// hpyx.execution (kind, task, chunk, chunk_size). Convert to PolicyToken
// so dispatch_policy can select the right HPX execution policy.
static double sum_of_squares(
    int kind, bool task_flag, int chunk, std::size_t chunk_size,
    nb::iterable src_it)
{
    ensure_runtime();
    std::vector<double> src;
    for (auto item : src_it) {
        src.push_back(nb::cast<double>(item));
    }
    hpyx::policy::PolicyToken tok{
        static_cast<hpyx::policy::Kind>(kind),
        task_flag,
        static_cast<hpyx::policy::ChunkKind>(chunk),
        chunk_size
    };
    HPYX_KERNEL_NOGIL;       // release the GIL for the HPX call
    return hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return hpx::transform_reduce(
            policy, src.begin(), src.end(), 0.0,
            std::plus<>{},                       // reduction op
            [](double x) { return x * x; });     // transform op
    });
}
```

Key points:
- `HPYX_KERNEL_NOGIL` releases the GIL for the entire HPX call. Our
  transform and reduce ops are pure C++ (`std::plus`, a lambda over
  `double`) — they never touch `nb::object`, so this is safe.
- If your transform op needs Python (e.g., `pred(x)`), use
  `HPYX_CALLBACK_GIL` inside the lambda. See `count_if` for reference.
- `dispatch_policy` handles seq/par/par_unseq + chunk-size modifiers.
  You just write one lambda that accepts `auto&& policy`.

### Step 2: Register the binding

In the `register_bindings(nb::module_& m)` function for your submodule:

```cpp
m.def("sum_of_squares",
      &sum_of_squares,
      "kind"_a, "task"_a, "chunk"_a, "chunk_size"_a, "src"_a);
```

### Step 3: Write the Python wrapper

Append to `src/hpyx/parallel.py`:

```python
def sum_of_squares(policy, iterable):
    """Sum of squares of elements under the given execution policy."""
    _runtime.ensure_started()
    t = policy._token()
    return _core.parallel.sum_of_squares(t.kind, t.task, t.chunk, t.chunk_size, iterable)
```

Add `"sum_of_squares"` to `__all__`.

### Step 4: Write the test

In `tests/test_parallel.py`:

```python
def test_sum_of_squares():
    assert hpyx.parallel.sum_of_squares(par, [1, 2, 3, 4]) == 30.0
```

### Step 5: Rebuild and run

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
pixi run -e test-py313t pytest tests/test_parallel.py::test_sum_of_squares -v
```

## Kernel-track example: `l2_norm_squared`

We're adding `hpyx.kernels.l2_norm_squared(a)` over a numpy ndarray.

### Step 1: Write the C++ binding (templated over dtype)

Append to `src/_core/kernels.cpp`:

```cpp
template <typename T>
static double l2_norm_squared(
    nb::ndarray<nb::numpy, const T, nb::c_contig> a)
{
    ensure_runtime();
    const T* p = a.data();
    std::size_t n = a.size();
    HPYX_KERNEL_NOGIL;
    return static_cast<double>(
        hpx::transform_reduce(
            hpx::execution::par, p, p + n, T{0},
            std::plus<T>{},
            [](T x) { return x * x; }));
}
```

### Step 2: Register for each dtype

```cpp
m.def("l2_norm_squared", &l2_norm_squared<float>,  "a"_a);
m.def("l2_norm_squared", &l2_norm_squared<double>, "a"_a);
m.def("l2_norm_squared", &l2_norm_squared<int32_t>, "a"_a);
m.def("l2_norm_squared", &l2_norm_squared<int64_t>, "a"_a);
```

### Step 3: Write the Python wrapper

In `src/hpyx/kernels.py`:

```python
def l2_norm_squared(a):
    """L2 norm squared — sum of squared elements of a numpy array."""
    _runtime.ensure_started()
    _check(a, "l2_norm_squared")
    return _core.kernels.l2_norm_squared(a)
```

### Step 4: Test against numpy

```python
def test_l2_norm_squared_matches_numpy():
    a = np.random.rand(10_000).astype(np.float64)
    assert hpyx.kernels.l2_norm_squared(a) == pytest.approx(np.sum(a * a))
```

## GIL discipline checklist

Before submitting a PR, verify:

- [ ] `nb::object` is never accessed from within a `HPYX_KERNEL_NOGIL` block.
- [ ] Every Python callback inside a C++ lambda uses `HPYX_CALLBACK_GIL`.
- [ ] Every kernel body over `nb::ndarray` uses `HPYX_KERNEL_NOGIL`.
- [ ] If you call `fn(*args)` or similar, you hold the GIL.
- [ ] If you block (e.g., wait on a future), you don't hold the GIL.

## Common mistakes

1. **Forgetting `ensure_runtime()` / `_runtime.ensure_started()`.** The
   C++ side will throw `RuntimeError`. Always call `ensure_runtime()` at
   the top of your C++ function and `_runtime.ensure_started()` in the
   Python wrapper.
2. **Capturing a `nb::callable` by reference in a task lambda.** The
   task may outlive the Python stack frame. Always capture by value.
3. **Using `HPYX_KERNEL_NOGIL` when the transform_op is a Python
   callable.** The callable can't run without the GIL. Either use
   `HPYX_CALLBACK_GIL` inside the transform lambda (callback track), or
   rewrite the op in pure C++ (kernel track).
4. **Forgetting the task-returning variant.** If your algorithm accepts
   a policy and the policy might carry the `task` tag, add a
   `_task`-suffixed C++ function that returns `HPXFuture<T>` and a
   matching branch in your Python wrapper.
5. **Non-contiguous ndarray.** Nanobind's `nb::c_contig` constraint
   will throw at the Python layer. Document that callers must pass
   `np.ascontiguousarray(a)` if needed, or add a Python-side check.
