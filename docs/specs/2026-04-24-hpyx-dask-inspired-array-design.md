# HPyX v1 — Dask-Inspired Array + Delayed Design

**Status:** Draft for review
**Date:** 2026-04-24
**Author:** brainstorming session between Don Setiawan and Claude Opus 4.7
**Supersedes:** portions of `hpyx_improvement_roadmap.md` (Phases 1–3)

---

## 1. Problem statement

HPyX today wraps roughly 5% of HPX, and the parts it does wrap are largely non-functional:

- `hpx_async` only exposes `hpx::launch::deferred` — the Python callable runs in the thread that calls `.get()`, not on HPX worker threads. The library does not actually perform asynchronous execution.
- `HPXExecutor.submit` calls `hpyx._core.hpx_async_set_result`, which is not a bound symbol. The executor is broken.
- The parallel `for_loop` binding raises `NotImplementedError` for the `par` policy from Python.
- There is no future composition (`when_all`, `when_any`, `dataflow`), no broader algorithm coverage, no executor control, no synchronization primitives.
- Users coming from dask — the natural audience for a Python parallel-computing library — cannot write familiar collection-style code today.

The result: HPyX has the ceremony of a C++ binding project (build system, nanobind surface, runtime lifecycle) without the surface area or behavior users need to adopt it for real workloads.

## 2. Goal

Deliver a v1 of HPyX that is **a standalone, dask-inspired Python parallel-computing library** whose user-facing API mirrors `dask.array` and `dask.delayed` signatures but whose execution is driven by the HPX C++ runtime's native task graph and work-stealing scheduler.

Users familiar with dask should be able to write `hpyx.Array` code with the same shape as `dask.array` code. Under the hood, computation runs on HPX lightweight threads via `hpx::dataflow`, `hpx::when_all`, and curated C++ kernels — bypassing Python's threadpool scheduler and giving true parallelism for numeric workloads even under the GIL.

**Non-goals for v1:**

- Full dask compatibility / being a dask fork. HPyX is inspired by dask, not a variant of it.
- DataFrame and Bag collections.
- Distributed multi-locality computation.
- GPU execution.
- Dask interop dunders (`__dask_graph__`, etc.) — designed in, shipped in v1.1.

## 3. Strategic decisions

The design rests on six decisions taken during brainstorming:

1. **Integration posture:** HPyX is a *standalone dask-inspired library*. It does not depend on or import dask. The `vendor/dask/` submodule is kept for reference. (Brainstorm Q1: option B.)
2. **Scope:** v1 ships `hpyx.Array` (chunked N-d array) and `hpyx.delayed` (lazy Python function wrapper) only. No bag, no dataframe. (Q2: option B.)
3. **Evaluation model:** fully lazy by default — nothing runs until `.compute()`. `.persist()` provides an opt-in switch to deferred/future-based execution so users can pipeline work with HPX running in the background. (Q3: option B + `.persist()`.)
4. **Kernel strategy:** chunks live as `numpy.ndarray` on the Python heap; core numeric ops ("Tier 1") are hand-bound C++ kernels over `nb::ndarray` zero-copy views that release the GIL; everything else ("Tier 2") is a thin Python wrapper that runs the equivalent numpy function inside a GIL-acquiring HPX continuation. (Q4: option C.)
5. **Runtime lifecycle:** implicit auto-init on first use, with `hpyx.init(...)` as an explicit override. The existing `HPXRuntime` context manager is kept as a convenience but no longer required. `atexit` owns shutdown. (Q5: option C.)
6. **Graph representation:** expression tree (immutable, structurally hashable `Expr` nodes), not dict-of-tasks. Modern graph-oriented Python libraries (JAX, PyTorch FX, Polars, dask-expr) have all converged on this. (Q6: option B.)

## 4. Architecture

### 4.1 Layers

```
┌────────────────────────────────────────────────────────────┐
│  User-facing Python API                                    │
│  hpyx.Array, hpyx.delayed, hpyx.compute, hpyx.persist      │
│  hpyx.from_array, hpyx.arange, hpyx.ones, hpyx.zeros, ...  │
│  hpyx.init(os_threads=…), hpyx.HPXRuntime (ctx mgr)        │
├────────────────────────────────────────────────────────────┤
│  Expression IR (pure Python)                               │
│  Expr base + nodes: FromArray, Add, Mul, MatMul, Sum,      │
│     Reduce, MapBlocks, Slice, Rechunk, DelayedCall, ...    │
│  optimization passes: cull, CSE, fuse-elementwise          │
├────────────────────────────────────────────────────────────┤
│  Compiler / runner                                         │
│  walk expression tree → emit hpx::dataflow calls through   │
│  the C++ binding → await output futures                    │
├────────────────────────────────────────────────────────────┤
│  Python/C++ boundary (hpyx._core, nanobind)                │
│  HPXFuture, dataflow_py, dataflow_k, when_all, ready_future│
│  async_submit, runtime_start/stop, num_worker_threads      │
│  numeric kernels (C++ over nb::ndarray):                   │
│    elementwise, reductions, linalg, sort, scan, ...        │
├────────────────────────────────────────────────────────────┤
│  HPX C++ runtime (vendor or conda-forge)                   │
│  hpx::async, dataflow, when_all, parallel algorithms,      │
│  work-stealing scheduler, resource partitioner             │
└────────────────────────────────────────────────────────────┘
```

### 4.2 Package layout

```
src/
  _core/                  # nanobind module
    bind.cpp              # top-level NB_MODULE definition
    runtime.cpp           # init/stop, was init_hpx.cpp
    futures.cpp           # HPXFuture, dataflow_py/_k, when_all, async_submit
    kernels/
      elementwise.cpp     # add, sub, mul, div, pow, neg, abs, sqrt, exp, log, sin, cos, ...
      comparison.cpp      # equal, less, greater, logical_and/or/not, ...
      reductions.cpp      # sum, mean, max, min, prod, std, var, any, all, argmax, argmin
      linalg.cpp          # dot, matmul, tensordot, inner, outer
      sort.cpp            # sort, argsort
      scan.cpp            # cumsum, cumprod
      indexing.cpp        # take, where, clip
      shape.cpp           # concatenate, stack (trivial cases)
  hpyx/
    __init__.py           # public API exports
    _runtime.py           # ensure_started, atexit hook, config reader
    _expr/
      base.py             # Expr, ArrayMeta, DelayedMeta, tokenize
      array_ops.py        # FromArray, Elementwise, Reduction, MatMul, ...
      delayed_ops.py      # DelayedCall, DelayedAttr, DelayedItem
      optimize.py         # cull, CSE, fuse_elementwise
    _compile.py           # expression tree → hpx::dataflow calls
    array.py              # Array class (facade over ArrayExpr)
    delayed.py            # @delayed decorator, Delayed class
    creation.py           # from_array, arange, ones, zeros, full, empty
    reductions.py         # sum, mean, max, min, ... (free functions)
    linalg/               # dot, matmul, tensordot, inner, outer, norm, inv, solve, svd, qr, ...
    random/               # normal, uniform, randint, choice, ... (Tier 2 wrappers)
    fft/                  # fft, ifft, rfft, irfft, ... (Tier 2 wrappers)
    HPXRuntime.py         # context manager (thin wrapper on _runtime)
    config.py             # runtime defaults, chunk-size target
    debug.py              # task tracing, timeline dump
tests/
  test_runtime.py
  test_expr/
  test_compile/
  test_kernels/
  test_array_api/
  test_delayed/
  test_integration/
  test_errors/
benchmarks/
  ...
```

### 4.3 Invariants

- **Chunks are always `numpy.ndarray` on the Python heap.** Never C++-owned buffers. C++ sees them through `nb::ndarray` zero-copy views inside kernels; lifetime stays in Python.
- **The C++ binding surface is small and stable.** Six concepts total: `HPXFuture`, `async_submit`, `dataflow_py`, `dataflow_k`, `when_all`, `ready_future`; plus runtime control and the kernel library. Every numeric op that needs speed goes through the kernel library; everything else rides on `dataflow_py` with a GIL-acquiring Python callback.
- **No dask import.** v1 does not import dask; the expression tree is shaped so a future `__dask_graph__()` method can walk it and emit a HighLevelGraph without restructuring.
- **Runtime is a process singleton hidden behind `hpyx.init()`.** Can only be started once and cannot be restarted — this is an HPX constraint, not a library choice.
- **`Array` and `Delayed` objects are immutable.** Every op creates a new `Expr` node; inputs are never mutated. Safe to share across threads.

## 5. Expression IR

### 5.1 Base class

```python
class Expr:
    """Immutable node in a lazy computation tree.

    Invariants:
    - `children` lists all sub-expressions this node depends on
    - `meta` carries shape/chunks/dtype (computed once, cached)
    - structural hash enables dedup (CSE)
    - `kernel_name` (if set) points at a C++ kernel; absent means the
      compiler must emit a dataflow_py (Python callback) task
    """
    __slots__ = ("children", "meta", "_hash")

    children: tuple[Expr, ...]
    meta: ArrayMeta | DelayedMeta

    def __hash__(self) -> int: ...   # structural
    def __eq__(self, other) -> bool: ...
```

### 5.2 Node taxonomy (v1)

```
Expr
 ├── ArrayExpr                   (meta: ArrayMeta)
 │   ├── FromArray(ndarray, chunks)                     # leaf, numpy literal
 │   ├── FromFunction(build_fn, chunks, dtype)          # leaf, arange/ones/zeros
 │   ├── Elementwise(kernel_name, *inputs)              # Add, Mul, ... + all ufunc-likes
 │   ├── Reduction(kernel_name, input, axis, keepdims)
 │   ├── MatMul(left, right)
 │   ├── Dot(left, right)                               # 1D inner product, specialized
 │   ├── Sort(input, axis)
 │   ├── Scan(kernel_name, input, axis)                 # CumSum, CumProd
 │   ├── Slice(input, key)
 │   ├── Rechunk(input, new_chunks)
 │   ├── MapBlocks(user_fn, inputs, kwargs, out_meta)   # Python callback (Tier 2 & user)
 │   ├── FusedElementwise(kernel_names, *inputs)        # produced by fusion pass
 │   └── Persisted(inner_expr, chunk_futures)           # post-.persist(): holds live futures
 └── DelayedExpr                  (meta: DelayedMeta)
     ├── DelayedCall(fn, args, kwargs)
     ├── DelayedAttr(parent, attr)
     └── DelayedItem(parent, key)
```

### 5.3 Metadata

```python
@dataclass(frozen=True)
class ArrayMeta:
    shape: tuple[int, ...]
    chunks: tuple[tuple[int, ...], ...]   # dask-compatible
    dtype: np.dtype

    @property
    def numblocks(self) -> tuple[int, ...]: ...
    @property
    def chunk_grid(self) -> Iterator[tuple[int, ...]]: ...

@dataclass(frozen=True)
class DelayedMeta:
    """No shape/dtype info for Delayed — the output is opaque Python."""
    name: str | None
```

Metadata follows dask's `chunks` tuple-of-tuples convention: `((10, 10, 5), (8, 8))` describes a 25×16 array split into a 3×2 chunk grid. This deliberately matches dask so users feel at home and a future `__dask_graph__()` doesn't need shape translation.

### 5.4 Optimization passes

Run in order before compile:

1. **Culling.** Drop sub-expressions whose outputs are not reachable from requested result keys (relevant after `Slice`).
2. **CSE.** Hash-cons nodes so `a + a` reuses one `FromArray(a)` child per chunk rather than producing two identical futures.
3. **Elementwise fusion.** Collapse chains of `Elementwise` nodes into a single `FusedElementwise` node whose compile step emits a single C++ kernel per chunk combining all arithmetic. Example: `(a + b) * c - d` becomes one `FusedElementwise(["add","mul","sub"], a, b, c, d)`.

Later passes (v2+): reduction-tree rewriting, rechunk elimination, stencil inference.

### 5.5 Compilation

```python
def compile_to_futures(expr: ArrayExpr) -> dict[ChunkKey, HPXFuture]:
    """Walk expr bottom-up, emit one hpx::dataflow per chunk per node.
    Returns {chunk_key → future} for the root expression."""
    futures_by_expr: dict[Expr, dict[ChunkKey, HPXFuture]] = {}
    for node in topo_sort(expr):
        if isinstance(node, FromArray):
            futures_by_expr[node] = {
                k: _core.ready_future(chunk) for k, chunk in node.chunks.items()
            }
        elif isinstance(node, Elementwise):
            futures_by_expr[node] = {
                k: _core.dataflow_k(
                    node.kernel_name,
                    [futures_by_expr[child][k] for child in node.children],
                )
                for k in node.meta.chunk_grid
            }
        elif isinstance(node, Reduction):
            # tree-reduce chunks along axis via dataflow_k
            ...
        elif isinstance(node, MapBlocks):
            futures_by_expr[node] = {
                k: _core.dataflow_py(
                    node.user_fn,
                    [futures_by_expr[c][k] for c in node.children],
                )
                for k in node.meta.chunk_grid
            }
        # ...
    return futures_by_expr[expr]
```

The compiler is the single module that touches `_core`. Everything above it is pure Python.

## 6. User-facing APIs

### 6.1 `hpyx.Array`

```python
class Array:
    def __init__(self, expr: ArrayExpr):
        self._expr = expr

    # Shape metadata
    @property
    def shape(self) -> tuple[int, ...]: ...
    @property
    def chunks(self) -> tuple[tuple[int, ...], ...]: ...
    @property
    def dtype(self) -> np.dtype: ...
    @property
    def ndim(self) -> int: ...
    @property
    def size(self) -> int: ...
    @property
    def nbytes(self) -> int: ...

    # Execution
    def compute(self) -> np.ndarray: ...
    def persist(self) -> Array: ...
    def visualize(self, filename: str | None = None) -> str | None: ...

    # Arithmetic / dunder ops — build Elementwise nodes
    def __add__(self, other): ...
    def __sub__(self, other): ...
    def __mul__(self, other): ...
    def __truediv__(self, other): ...
    def __pow__(self, other): ...
    def __neg__(self): ...
    __radd__ = __add__; __rmul__ = __mul__
    def __rsub__(self, other): ...
    def __rtruediv__(self, other): ...

    # Indexing
    def __getitem__(self, key): ...   # builds Slice node

    # Reductions
    def sum(self, axis=None, keepdims=False) -> Array: ...
    def mean(self, axis=None, keepdims=False) -> Array: ...
    def max(self, axis=None) -> Array: ...
    def min(self, axis=None) -> Array: ...
    def std(self, axis=None) -> Array: ...
    def var(self, axis=None) -> Array: ...
    def argmax(self, axis=None) -> Array: ...
    def argmin(self, axis=None) -> Array: ...

    # Shape manipulation
    def reshape(self, *shape) -> Array: ...
    def rechunk(self, chunks) -> Array: ...
    def astype(self, dtype) -> Array: ...

    # Custom user kernels (Python callback via MapBlocks)
    def map_blocks(self, fn, *args, dtype=None, **kwargs) -> Array: ...

    # Rendering / interop
    def __repr__(self) -> str: ...
    # Deliberately NO __array__ — users must call .compute() explicitly.
```

**Creation functions:**

```python
hpyx.from_array(x: np.ndarray, chunks="auto" | int | tuple) -> Array
hpyx.from_delayed(d: Delayed, shape, dtype) -> Array
hpyx.arange(stop, *, chunks="auto", dtype=None) -> Array
hpyx.arange(start, stop, step=1, *, chunks="auto") -> Array
hpyx.ones(shape, *, chunks="auto", dtype=float64) -> Array
hpyx.zeros(shape, *, chunks="auto", dtype=float64) -> Array
hpyx.full(shape, fill_value, *, chunks="auto") -> Array
hpyx.empty(shape, *, chunks="auto", dtype=float64) -> Array
hpyx.eye(n, *, chunks="auto", dtype=float64) -> Array
hpyx.linspace(start, stop, num=50, *, chunks="auto", dtype=None) -> Array
```

**`chunks="auto"` heuristic:** target ~128 MiB per chunk (dask's default), configurable via `hpyx.config.chunk_size_target`.

**Free-function API (dask.array mirror):** `hpyx.sum`, `hpyx.mean`, `hpyx.max`, `hpyx.dot`, `hpyx.matmul`, `hpyx.sort`, `hpyx.concatenate`, `hpyx.stack`, `hpyx.where`, `hpyx.clip`, etc. Each is a one-liner delegating to method form.

### 6.2 `hpyx.delayed`

```python
@hpyx.delayed
def parse(path: str) -> dict:
    return json.load(open(path))

records = [parse(p) for p in paths]       # list[Delayed]
summary = combine(records)                # Delayed
result = summary.compute()                # runs everything via HPX
```

```python
def delayed(fn=None, /, *, name: str | None = None) -> Callable: ...

class Delayed:
    def __init__(self, expr: DelayedExpr): ...
    def compute(self) -> Any: ...
    def persist(self) -> Delayed: ...
    def visualize(self, filename=None) -> str | None: ...

    # Attribute / item access build more Delayed nodes
    def __getattr__(self, name): ...
    def __getitem__(self, key): ...

    # If the underlying result is callable, further () calls are also lazy
    def __call__(self, *args, **kwargs): ...
```

**v1 simplifications versus dask.delayed:**

- No `pure=True` content-hash tokenization. Identity-based keys only; two identical calls produce two tasks.
- No `traverse=True` into arbitrary containers. Combining delayed values requires passing them explicitly into another `@delayed` function.
- `nout=N` for multi-return functions is supported.

### 6.3 Top-level `hpyx.compute` / `hpyx.persist`

```python
hpyx.compute(*collections) -> tuple[Any, ...]
hpyx.persist(*collections) -> tuple[Collection, ...]
```

These merge the expression trees of all inputs, share common sub-expressions through CSE, emit one unified set of HPX dataflow calls, and return results in input order.

## 7. C++ binding surface

### 7.1 Futures

```cpp
// src/_core/futures.cpp

class HPXFuture {
    hpx::shared_future<nb::object> fut_;
public:
    nb::object get();                              // releases GIL while blocking
    nb::object result();                           // alias for get(), dask-compatible name
    void add_done_callback(nb::callable cb);       // dask-compatible
    bool done();                                   // like .ready()
    void cancel();                                 // no-op stub in v1
};

// Set __dask_future__ = True on the class attr for future dask interop
```

### 7.2 Scheduling primitives

```cpp
HPXFuture async_submit(nb::callable fn, nb::args args);
HPXFuture dataflow_py(nb::callable fn, std::vector<HPXFuture> inputs);
HPXFuture dataflow_k(std::string kernel_name, std::vector<HPXFuture> inputs,
                     nb::kwargs kwargs);
HPXFuture when_all(std::vector<HPXFuture> inputs);
HPXFuture ready_future(nb::object value);
```

`dataflow_py` and `dataflow_k` differ only in task-body signature:

- **`dataflow_py`** lambda: `nb::gil_scoped_acquire acquire; return fn(*resolved);`
- **`dataflow_k`** lambda: looks up `kernel_name` in a C++ function-pointer table, extracts `nb::ndarray` views from input futures, calls the kernel in pure C++, returns the result ndarray. GIL is released for the duration of the kernel.

### 7.3 Kernel library

One C++ function per kernel, templated over `float32 | float64 | int32 | int64`. Example:

```cpp
template <typename T>
nb::ndarray<T, nb::c_contig> elementwise_add(
    nb::ndarray<const T, nb::c_contig> a,
    nb::ndarray<const T, nb::c_contig> b)
{
    // validate shape; allocate output; release GIL
    nb::gil_scoped_release release;
    hpx::transform(hpx::execution::par,
        a.data(), a.data() + a.size(),
        b.data(),
        out.data(),
        std::plus<T>{});
    // reacquire GIL automatically on return scope
    return out;
}
```

A `HPYX_KERNEL` helper macro will standardize GIL release, shape validation, and output allocation so each kernel is ~15-20 lines.

**Kernel catalog for v1:**

| Module | Kernels |
|---|---|
| `elementwise` | add, sub, mul, div, floordiv, mod, pow, neg, abs, sqrt, exp, log, log2, log10, exp2, expm1, log1p, sin, cos, tan, arcsin, arccos, arctan, sinh, cosh, tanh |
| `comparison` | equal, not_equal, less, less_equal, greater, greater_equal, logical_and, logical_or, logical_not, logical_xor |
| `reductions` | sum, mean, max, min, prod, std, var, any, all, argmax, argmin |
| `linalg` | dot, matmul, tensordot (simple cases), inner, outer |
| `sort` | sort, argsort |
| `scan` | cumsum, cumprod |
| `indexing` | take (1d), where (elementwise), clip |
| `shape` | concatenate, stack (cheap cases) |

~60 kernel functions, each templated over 4 dtypes. Kernels that don't fit (ragged shapes, non-numeric dtypes, object arrays) fall through to Tier 2.

### 7.4 Runtime control

```cpp
void runtime_start(std::vector<std::string> cfg);   // was init_hpx_runtime
void runtime_stop();                                // was stop_hpx_runtime
bool runtime_is_running();                          // NEW
int  num_worker_threads();
```

### 7.5 GIL discipline

A normative section, to become the basis for `CONTRIBUTING.md`:

1. Every `dataflow_py` lambda must start with `nb::gil_scoped_acquire`.
2. Every `dataflow_k` lambda and every kernel function body must not touch `nb::object`. Raw pointers and `nb::ndarray` views only. Kernels explicitly release the GIL at entry and reacquire at return.
3. `HPXFuture::get()` releases the GIL while blocking so other Python threads (on free-threaded builds) can make progress.
4. `runtime_start` is called under GIL; `runtime_stop` releases the GIL while waiting for HPX to drain.

## 8. Execution model

### 8.1 `.compute()` end-to-end

```
Python                                 _core (C++)                HPX runtime
──────                                 ───────────                ───────────
1. Array(Sum(Elementwise("add", a, b)))
2. .compute()
3. ensure_started()              ────► runtime_start(cfg)          start workers
4. optimize(expr_tree):
   ├── cull
   ├── CSE
   └── fuse elementwise
5. compile_to_futures(optimized):
   for each FromArray chunk:
     ready_future(chunk)         ────► hpx::make_ready_future(...)
   for each Elementwise:
     dataflow_k("elementwise.add", [a,b]) ────► hpx::dataflow(kernel, fs)
                                               hpx::transform(par, ...)
   for each Reduction:
     tree-reduce via dataflow_k  ────► hpx::dataflow chain
6. result = when_all([chunk_futs])
7. release GIL:
   result.get()                  ────► hpx::future::get() (blocks)
8. reacquire GIL, assemble numpy.ndarray
9. return
```

### 8.2 `.persist()` semantics

`.persist()` runs steps 1–6 but stops before `.get()`. It wraps the output chunk futures in a `Persisted(inner_expr, chunk_futures)` node and returns a new `Array` whose root is that node. The original `inner_expr` is retained for `.visualize()`.

Chunks in a `Persisted` node are `hpx::shared_future` so multiple downstream consumers can read the same result. Idempotent: `arr.persist().persist()` returns the same object.

### 8.3 Error handling

1. Any task throwing → containing `HPXFuture.get()` re-raises the exception at `.compute()` time.
2. Tasks that have already started when a sibling fails will finish; tasks dependent on the failed task short-circuit and never run.
3. The first exception raised from `.compute()` wins; other failures are discarded.
4. `nb::error_scope` around the `dataflow_py` lambda captures Python exceptions and rethrows them at `.get()` time with the original traceback.
5. Kernel-level errors (shape/dtype mismatch, empty input) are raised as `ValueError` / `TypeError` and surfaced the same way.

Out of scope for v1: retries, resilience fallbacks, cancellation tokens. Each is HPX-supported but adds meaningful design surface we defer to v1.x.

### 8.4 Thread safety

- `Array` and `Delayed` objects are immutable. Any thread can read them.
- Building new expressions from existing ones is safe because every op creates a new `Expr` node without mutating inputs.
- `.compute()` and `.persist()` lock only the runtime-started check; two threads calling them concurrently on independent expressions both proceed.
- `hpyx.init()` and `HPXRuntime.__enter__` are idempotent and thread-safe.

This matters because free-threaded Python 3.13t users will call `.compute()` from multiple threads simultaneously, and the library must not surprise them.

## 9. Dtype and shape support for v1

**dtypes:**

- Tier 1 kernels: `float32`, `float64`, `int32`, `int64`. Other numeric dtypes auto-promote (e.g., `int8` → `int32`) when crossing the Tier-1 boundary.
- Tier 2 wrappers: whatever numpy supports. Chunks are handed to numpy as-is.
- Object dtypes and mixed-dtype arithmetic are Tier 2 only.

**Shapes:**

- Arbitrary ndim.
- Broadcasting is handled in the Python layer: the `Elementwise` node inserts explicit broadcast-shape metadata and the kernel receives aligned inputs. Complex broadcasts (e.g., strided views over non-contiguous memory) are rejected at graph-build time with a clear error pointing to Tier 2.
- Chunks must be C-contiguous for Tier-1 kernels. Rechunking to enforce contiguity is automatic where safe, explicit via `rechunk()` where expensive.

## 10. Testing and benchmarks

### 10.1 Test layout

```
tests/
  test_runtime.py            init, stop, idempotency, atexit, ensure_started
  test_expr/
    test_base.py             Expr equality, tokenization, immutability
    test_array_ops.py        per-node meta propagation
    test_optimize.py         cull/CSE/fuse passes as tree rewrites
  test_compile/
    test_chunking.py
    test_ready_future.py
    test_dataflow.py
  test_kernels/
    test_elementwise.py      vs numpy, per dtype
    test_reductions.py       vs numpy, per axis
    test_linalg.py
    test_sort.py
    test_scan.py
  test_array_api/
    test_creation.py
    test_arithmetic.py
    test_reductions.py
    test_linalg.py
    test_map_blocks.py
    test_fft.py              Tier 2
    test_random.py           Tier 2 with per-chunk seeding
  test_delayed/
    test_basic.py
    test_composition.py
    test_nout.py
  test_integration/
    test_persist.py
    test_free_threaded.py    multi-thread .compute() safety
    test_large_graph.py      10k+ chunks
  test_errors/
    test_kernel_errors.py
    test_user_fn_errors.py
```

### 10.2 Property-based testing

Hypothesis-generated:
- Random well-typed expressions vs numpy reference on the same input.
- Random chunk grids + shapes; verify broadcasting and rechunking preserve values.
- Random fusion-candidate sub-trees; verify fused and unfused trees produce identical results.

### 10.3 Reference comparison

Every Tier-1 kernel has a test that runs both the hpyx and numpy implementations on random input with tolerance assertions. Every Tier-2 wrapper tests against the single-chunk numpy call it wraps.

### 10.4 Benchmarks

pytest-benchmark plus asv, tracking:

- HPyX vs numpy single-threaded (should be close; exposes chunking overhead).
- HPyX vs dask.array with `threaded` scheduler (should win on CPU-bound work).
- HPyX with varying thread counts (strong scaling — expect near-linear for Tier-1 ops on CPU-bound work).
- Graph construction time (lazy build for large chunk grids).
- `.persist()` + downstream compute (verify pipelining speedup over `.compute()` twice).

### 10.5 Debug / trace facility

`hpyx.debug.enable_tracing()` populates a per-task log with `(task_name, input_chunks, duration, worker_id)`. Useful for diagnosing whether a slow workload is GIL-bound, kernel-bound, or scheduler-bound.

### 10.6 CI matrix

- Existing pixi-based CI.
- Add dimension for free-threaded vs GIL Python 3.13.
- Nightly benchmark job with regression tracking.

## 11. Out of scope for v1

- Distributed / multi-locality computation. No parcelports, no AGAS, no HPX actions.
- DataFrame and Bag collections.
- Dask interop dunders (`__dask_graph__`, `__dask_keys__`, `__dask_tokenize__`). Planned for v1.1.
- `pure=True`, `traverse=True`, and content-hash tokenization of Delayed.
- Task retries, resilience, cancellation tokens.
- Custom executors, thread pools, NUMA-pinned pools. One default HPX pool in v1.
- GPU support (CUDA / ROCm / SYCL).
- `hpyx.ma` (masked arrays), `hpyx.overlap` (ghost cells).
- Graphviz visualization — v1 ships a text tree printer; graphviz is v1.2.
- Auto-chunking heuristics beyond the static 128 MiB target.

## 12. Roadmap beyond v1

| Version | Theme | Key additions |
|---|---|---|
| v1.0 | Array + Delayed MVP (this spec) | Lazy IR, HPX compile, Tier-1 kernels, Tier-2 fallbacks, `.persist()` |
| v1.1 | Dask interop bridge | `__dask_graph__`, `__dask_keys__`, `__dask_tokenize__`. Enables `dask.compute(hpyx_arr)` and mixing with `dask.delayed`. |
| v1.2 | Diagnostics & viz | Graphviz visualization, task tracing dashboard, HPX performance counters exposed to Python |
| v1.3 | Executor control | Custom thread pools via resource partitioner, per-op chunk size, annotation support for scheduling hints |
| v2.0 | Distributed | HPX localities exposed as a cluster abstraction, distributed Array with partition-placement hints |
| v2.x | Advanced numerics | `hpyx.ma`, `hpyx.overlap`, GPU backend investigation, windowed / stencil ops |

## 13. Risk register

1. **The current `hpx_async` uses `launch::deferred`, not `launch::async`.** Switching to true async will surface whatever GIL bugs the deferred model has been papering over. Expect real debugging work in the futures module.
2. **Free-threaded Python 3.13t is still experimental.** Nanobind supports it, HPX is Python-agnostic, but numpy and pytest versions we depend on may have issues. Mitigation: CI matrix covers both builds.
3. **Expression fusion bugs.** Any CSE or fusion rewrite that is wrong will silently return incorrect results without a segfault. Mitigation: every fusion rule has a property test comparing fused vs unfused trees on random inputs.
4. **Per-chunk kernel dispatch overhead.** If a kernel is cheap (elementwise add on tiny chunks), the cost of `hpx::dataflow` + nanobind marshalling may dominate. Mitigation: benchmark early; implement chunk-batching (combine small chunks into chunk-groups that one kernel call iterates internally).
5. **Runtime-cannot-restart constraint breaking tests.** Pytest's default isolation wants a fresh runtime per test. Mitigation: session-scoped runtime fixture plus documentation that all tests share one HPX runtime.

## 14. Migration notes for existing HPyX code

- `hpyx.HPXRuntime` context manager stays usable but becomes optional. Existing code continues to work unchanged.
- `hpyx.HPXExecutor` is deprecated in favor of the new Array/Delayed APIs. The underlying `async_submit` primitive exposed by `_core` is what the executor should have been doing — a thin wrapper around it can be retained under `hpyx.futures.submit` for backward compatibility (removing the current `launch::deferred` misbehavior).
- `hpyx.multiprocessing.for_loop` is deprecated. Users wanting fine-grained parallelism use `hpyx.Array.map_blocks` or `hpyx.delayed`.
- The four `.cpp` files at the root of `src/` (`bind.cpp`, `algorithms.cpp`, `futures.cpp`, `init_hpx.cpp`) are refactored into `src/_core/` with clearer module boundaries (runtime, futures, kernels).

## 15. Open questions the implementation plan must answer

These are deferred to the writing-plans stage but noted here so they're not forgotten:

- Exact layout of the C++ kernel registry — should it be a hash-map string lookup, or an `enum class` of kernel IDs with a switch? Trade-off is extensibility vs dispatch cost.
- How `dataflow_k` threads kwargs through to typed kernel functions. Kernels like `elementwise_add(a, b)` take only inputs, but reductions and scans take `axis`, `keepdims`, etc. The dispatch layer needs a consistent story — either a `kernel_params` struct per kernel family, or kwargs translated to a fixed C++ dispatch context. Decide at plan stage.
- Chunk-key type in `HPXFuture` registries — tuple of ints, or compact int-encoded? Matters for dict lookup cost on large graphs.
- Whether to expose `hpx::shared_future` directly to Python under a separate `HPXSharedFuture` class or always shared-internally. Simpler to always shared-internally; deferred for plan stage.
- Broadcast validation: done in Python layer or C++ kernel? Python is safer (clean errors) but adds import-time cost. Probably Python with a fast path in C++.
- Test fixture strategy for the single-shot runtime: pytest `session` fixture plus a "guard" that skips runtime-touching tests if the runtime has already been shut down.
- What's the packaging story for kernels? One giant compilation unit, or per-module .o files? Affects incremental build times significantly.
