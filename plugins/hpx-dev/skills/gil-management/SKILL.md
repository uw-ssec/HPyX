---
name: gil-management
description: Enforces correct GIL handling in HPyX's Nanobind bindings under Python 3.13 free-threading — diagnoses GIL deadlocks and callback segfaults, applies `gil_scoped_acquire`/`release` patterns, and validates thread safety in C++/Python code. Use when the user asks about "GIL management", "free-threading", "Python 3.13 free-threading", "gil_scoped_acquire", "gil_scoped_release", "thread safety", "GIL deadlock", "nogil", "disable-gil", or debugs threading issues, segfaults in callbacks, or race conditions in HPyX.
---

# GIL and Free-Threading Management

## HPyX Threading Model

HPyX targets Python 3.13 with free-threading (`--disable-gil`). The `_core` module is compiled with Nanobind's `FREE_THREADED` flag. Thread safety must be ensured through proper synchronization, not GIL reliance; `nb::gil_scoped_acquire` is a no-op when the GIL is disabled. HPX manages its own thread pool independently of Python's threading.

## GIL Rules for HPyX Bindings

### Rule 1: Acquire GIL Before Calling Python

Any C++ code that calls into Python (invoking callables, accessing Python objects, creating Python objects) must hold the GIL:

```cpp
// CORRECT: GIL acquired before Python callback
hpx::async(hpx::launch::deferred,
    [f, args]() -> nb::object {
        nb::gil_scoped_acquire acquire;  // Acquire before Python call
        return f(*args);
    });
```

```cpp
// WRONG: Calling Python without GIL — will segfault or corrupt state
hpx::async(hpx::launch::deferred,
    [f, args]() -> nb::object {
        return f(*args);  // DANGER: no GIL
    });
```

### Rule 2: Release GIL During Blocking C++ Operations

Long-running pure C++ operations should release the GIL to allow other Python threads to execute:

```cpp
// CORRECT: GIL released during HPX shutdown (blocking operation)
void stop_hpx_runtime() {
    global_runtime_manager *r = rts;
    rts = nullptr;
    if (r != nullptr) {
        nb::gil_scoped_release release;  // Release during blocking C++ work
        delete r;
    }
}
```

### Rule 3: Deferred Futures Keep GIL for Callbacks

HPyX uses `hpx::launch::deferred` for futures that invoke Python callbacks. The callable runs in the caller's thread at `.get()` time, so the GIL is already held:

```cpp
// The .get() method does NOT release the GIL because the deferred
// callable may call back into Python
.def("get", [](hpx::future<T> &f) {
    return f.get();  // Runs deferred callable in caller's thread
})
```

### Rule 4: .then() Continuations Need Explicit GIL

When chaining futures with `.then()`, the continuation creates a new deferred future that must acquire the GIL before invoking the Python callback:

```cpp
.def("then", [](hpx::future<T> &f, nb::callable callback, nb::args args) {
    hpx::future<T> cont = hpx::async(hpx::launch::deferred,
        [prev = std::move(f), callback, args]() mutable -> nb::object {
            nb::gil_scoped_acquire acquire;  // Must acquire for Python callback
            auto res = prev.get();
            return callback(res, *args);
        });
    return cont;
})
```

## Decision Matrix

| Scenario | GIL Action | Reason |
|---|---|---|
| C++ code calling `nb::callable` | `gil_scoped_acquire` | Python objects require GIL |
| C++ code creating `nb::object` | `gil_scoped_acquire` | Python heap allocation |
| Pure C++ computation (no Python) | No action needed (or `gil_scoped_release` if called from Python) | No Python interaction |
| Blocking C++ operation (runtime shutdown, network I/O) | `gil_scoped_release` | Allow other Python threads to proceed |
| Nanobind `.def()` method body | GIL is held by default | Nanobind acquires GIL for method calls |
| HPX async lambda (deferred, with Python callback) | `gil_scoped_acquire` inside lambda | Lambda runs in HPX thread, not Python thread |
| HPX async lambda (deferred, pure C++) | No GIL needed inside lambda | No Python interaction |

## Free-Threading Considerations

With Python 3.13 free-threading, `nb::gil_scoped_acquire` / `release` become no-ops. This means:

- **Thread safety cannot rely on the GIL** — use proper synchronization (mutexes, atomics) for shared state
- **Python reference counting is thread-safe** in free-threading mode (uses atomic refcounts)
- **Nanobind's FREE_THREADED flag** ensures the module supports free-threading correctly
- **HPX thread pool** operates independently — HPX threads are not Python threads

### Shared State Protection

```cpp
// CORRECT: Use mutex for shared state in free-threading
std::mutex mtx;
std::vector<nb::object> results;

hpx::for_each(hpx::execution::par, begin, end,
    [&](auto item) {
        nb::gil_scoped_acquire acquire;
        auto result = process(item);
        std::lock_guard<std::mutex> lock(mtx);
        results.push_back(result);
    });
```

## Debugging GIL Issues

Common symptoms and causes:

| Symptom | Likely Cause | Fix |
|---|---|---|
| Segfault in Python callback | Missing `gil_scoped_acquire` | Add acquire before Python calls |
| Deadlock on `.get()` | GIL held while waiting for future that needs GIL | Release GIL before `.get()` or use deferred launch |
| Corrupted Python objects | Race condition in free-threading | Add mutex around shared Python object access |
| "Fatal Python error: GIL not held" | Missing acquire in non-deferred async | Add `gil_scoped_acquire` in async lambda |

## HPyX-Specific Patterns

### Runtime Initialization

The runtime manager (`src/init_hpx.cpp`) acquires the GIL during init and releases during shutdown:

```
init_hpx_runtime() → gil_scoped_acquire (ensures Python is safe during setup)
stop_hpx_runtime() → gil_scoped_release (allows Python threads during HPX shutdown)
```

### The Deferred Execution Pattern

HPyX currently uses `hpx::launch::deferred` for all Python-facing async operations. This simplifies GIL management because:

1. Deferred futures don't execute until `.get()` is called
2. `.get()` runs in the caller's thread (which holds the GIL from Python)
3. No true parallel Python execution occurs — parallelism is in pure C++ operations

When implementing true parallel execution (non-deferred), switch to `hpx::launch::async` and ensure every lambda that touches Python acquires the GIL.
