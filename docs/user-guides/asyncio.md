# asyncio integration

HPyX's `Future` is awaitable. You can:

1. `await` an HPyX future directly.
2. Use `asyncio.wrap_future(hpyx_future)` (stdlib pattern).
3. Use `await loop.run_in_executor(HPXExecutor(), fn, ...)`.
4. Use the `hpyx.aio.*` combinators.

## Direct await

```python
import asyncio
import hpyx

async def main():
    result = await hpyx.async_(slow_compute, 42)
    return result

asyncio.run(main())
```

The `__await__` implementation uses `loop.call_soon_threadsafe` to post
the result back to the event loop from the HPX worker thread. It does
not block the event loop — other coroutines can run while the HPX task
is pending.

## Parallel algorithms with await

```python
import asyncio
import hpyx
from hpyx.execution import par

async def main():
    # transform_reduce with the task tag returns a Future.
    fut = hpyx.parallel.transform_reduce(
        par(hpyx.execution.task), range(1_000_000),
        init=0, reduce_op=lambda a, b: a + b,
        transform_op=lambda x: x * x,
    )
    return await fut
```

## Combinators

```python
f1 = hpyx.async_(fetch_a)
f2 = hpyx.async_(fetch_b)
f3 = hpyx.async_(fetch_c)

# Wait for all — result is a tuple.
a, b, c = await hpyx.aio.await_all(f1, f2, f3)

# Wait for first — result is (index, futures_list).
idx, futures = await hpyx.aio.await_any(f1, f2, f3)
winner = futures[idx].result()
```

## FastAPI / web server usage

```python
from fastapi import FastAPI
import hpyx

app = FastAPI()

@app.on_event("startup")
def startup():
    hpyx.init(os_threads=8)

@app.get("/process/{item_id}")
async def process(item_id: int):
    # Don't block the event loop on CPU-bound work.
    result = await hpyx.async_(expensive_compute, item_id)
    return {"result": result}
```

## Caveats

- The asyncio event loop thread and HPX worker threads are distinct.
  `call_soon_threadsafe` handles the cross-thread posting, but any code
  you run inside a callback that touches the event loop must not block.
- On free-threaded Python 3.13t, asyncio uses internal locks rather
  than the GIL. Our bridge works correctly on both builds.
