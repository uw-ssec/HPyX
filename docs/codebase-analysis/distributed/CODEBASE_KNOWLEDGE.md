# Dask Distributed: Master Codebase Knowledge Document

**Source location:** `vendor/distributed/distributed/`
**Document purpose:** Self-contained reference for an LLM with no repo access, covering everything needed to implement features, fix bugs, and refactor safely.
**Generated:** 2026-04-24

---

## Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [System Architecture](#2-system-architecture)
3. [Feature-by-Feature Analysis](#3-feature-by-feature-analysis)
4. [Nuances, Subtleties, and Gotchas](#4-nuances-subtleties-and-gotchas)
5. [Technical Reference and Glossary](#5-technical-reference-and-glossary)
6. [Cross-Cutting Concerns](#6-cross-cutting-concerns)

---

## 1. High-Level Overview

### Purpose

`dask.distributed` is the distributed task scheduler for the Dask ecosystem. It implements a dynamic, fault-tolerant, multi-client task graph executor. Where `dask` core converts Python collection operations into task graphs, `distributed` actually executes those graphs across a cluster of processes.

### Users and Entry Points

- **Data scientists** call `client.submit()`, `client.compute()`, `client.map()`, `client.scatter()`, `client.gather()`.
- **Library authors** use `distributed` as a backend for Dask collections (`Array`, `DataFrame`, `Bag`) by registering it as the global scheduler via `client.register_as_default()`.
- **Platform engineers** deploy clusters using `LocalCluster`, `SSHCluster`, `SpecCluster`, or third-party cluster managers (Kubernetes, YARN, SLURM via dask-jobqueue).

### Deployment Models

| Model | Entry Point | Description |
|-------|-------------|-------------|
| `LocalCluster` | `deploy/local.py:23` | Scheduler + Workers in the same machine, multiple processes or threads |
| `SpecCluster` | `deploy/spec.py` | Cluster defined by a spec dict; base class for all cloud/HPC deployments |
| `SSHCluster` | `deploy/ssh.py` | Workers spawned via SSH on remote hosts |
| `Client()` auto-cluster | `client.py:952` | When no address given, creates a LocalCluster automatically |

### Relationship to Dask Core

Dask core (`dask/`) converts high-level collection APIs to task graphs (`dict[key, GraphNode]`). `distributed` receives those graphs via `Client.compute()` → `Scheduler.update_graph()`, schedules them, executes them on workers, and returns results as `Future` objects. The connection is through `dask.base.compute()` which checks for a globally-registered `distributed.Client`.

### Main Features

- Dynamic task graph execution with dependency tracking
- Work stealing for load balancing
- Memory management with spill-to-disk, pause, and terminate thresholds
- P2P (peer-to-peer) shuffle for large dataset repartitioning
- Actors for stateful long-lived objects on workers
- Adaptive scaling (auto scale workers up/down based on load)
- Cluster dashboard (Bokeh-based) for real-time diagnostics
- Publish/subscribe datasets across clients
- Coordination primitives: `Lock`, `Semaphore`, `Event`, `Queue`, `Variable`
- TLS/mTLS security for all communications
- Plugin API for `Scheduler`, `Worker`, and `Nanny`
- Preloading (custom Python modules run at startup of each component)
- Spans for distributed tracing/performance attribution

---

## 2. System Architecture

### Component Overview

```
  User Code
      |
  [Client]  client.py:952
      |  TCP/TLS BatchedSend
      |
  [Scheduler] scheduler.py:3640      <-- single-threaded asyncio event loop
      |
      +-- SchedulerState  scheduler.py:1610  (pure state, all slots)
      |      |-- tasks: dict[Key, TaskState]
      |      |-- workers: SortedDict[addr, WorkerState]
      |      |-- clients: dict[str, ClientState]
      |      +-- queued: HeapSet[TaskState]
      |
      +-- Extensions (dict[str, Any])
             WorkStealing, ActiveMemoryManager, ShuffleSchedulerPlugin,
             SpansExtension, PublishExtension, QueueExtension,
             SemaphoreExtension, EventExtension, VariableExtension, ...
      |
  [Worker]  worker.py:279            <-- async event loop + thread pool
      |
      +-- BaseWorker  worker_state_machine.py:3582
      |      |-- state: WorkerState  (pure state machine)
      |      +-- _async_instructions: set[asyncio.Task]
      |
      +-- WorkerMemoryManager  worker_memory.py:74
      |      +-- SpillBuffer  spill.py:69  (zict.Buffer wrapping)
      |
      +-- BatchedSend → Scheduler
      |
  [Nanny]  nanny.py:69               <-- supervisor process
      +-- WorkerProcess  nanny.py:657  (subprocess management)
```

For Mermaid architecture and sequence diagrams, see:
- `docs/codebase-analysis/distributed/assets/architecture_diagram.md`
- `docs/codebase-analysis/distributed/assets/task_lifecycle_sequence.md`

### Communication Layer (`distributed/comm/`)

All communication is message-oriented. The `Comm` abstract base class (`comm/core.py:33`) defines:
- `async read(deserializers=None)` — read one message
- `async write(msg, serializers=None, on_error=None)` — write one message
- `async close()` — flush and close

Concrete implementations:
- **TCP/TLS** (`comm/tcp.py`): default transport; uses Tornado `IOStream`. TLS wraps the same with `ssl.SSLContext`.
- **UCX** (`comm/ucx.py`): high-performance RDMA transport for GPU clusters; optional, requires `ucp`.
- **WebSocket** (`comm/ws.py`): browser-accessible transport.
- **InProcess** (`comm/inproc.py`): shared-memory transport for testing and LocalCluster with threads.

Transport registry (`comm/registry.py`) maps URI schemes (`tcp://`, `tls://`, `ucx://`, `ws://`, `inproc://`) to listener and connector factories.

### `BatchedSend` (`batched.py:20`)

The scheduler and workers do not call `Comm.write()` directly for most messages. Instead they use `BatchedSend`, which:
1. Accumulates messages in a `buffer` list.
2. A background coroutine (`_background_send`) fires every `interval` ms (configured per-comm).
3. All buffered messages are sent in one `Comm.write()` call as a list.

This is critical for throughput: sending 10,000 tiny task-finished acknowledgments as a single batch is far more efficient than 10,000 individual writes.

`Scheduler.stream_comms` and `Scheduler.client_comms` are both `dict[str, BatchedSend]` (`scheduler.py:3734–3735`).

### Protocol Layer (`distributed/protocol/`)

Serialization is pluggable. The main entry points are `serialize()` and `deserialize()` in `protocol/serialize.py`.

Serializer priority order (highest to lowest):
1. **`dask`** serializer — dispatched via `dask_serialize` / `dask_deserialize` registries. Used for NumPy arrays, cuPy arrays, PyTorch tensors, Pandas DataFrames, etc.
2. **`pickle`** serializer (`protocol/serialize.py:69`) — fallback for arbitrary Python objects using Python's `pickle` with out-of-band buffer support (PEP 574 `PickleBuffer`).
3. **`error`** — used when serialization fails; captures exception information.

Messages on the wire are `msgpack`-encoded dicts. Frames (binary buffers) are sent separately after the header to enable zero-copy on the receive side for large arrays.

The `Serialized` and `ToPickle` wrapper types signal to the comm layer how to handle specific fields:
- `Serialized(header, frames)` — already serialized, pass frames through.
- `ToPickle(obj)` — serialize this field with pickle on the wire.

### Dashboard (`distributed/dashboard/`, `distributed/http/`)

The scheduler runs a Bokeh-based web application on a configurable port (default `:8787`). It shows:
- Task stream (Gantt of task execution)
- Workers memory / CPU utilization
- Cluster-wide memory usage over time
- Progress bars per computation
- Profile (statistical profiler data from workers)

HTTP routes are defined in `distributed/http/` and registered via `distributed.yaml:scheduler.http.routes`. Prometheus metrics are exposed at `/metrics`.

---

## 3. Feature-by-Feature Analysis

### 3.1 Task Submission Lifecycle

**Entry points:** `Client.submit()` (`client.py:2050`), `Client.compute()` (`client.py:3597`), `Client.map()`.

**Step 1 — Client side:**

`Client.submit(func, *args, **kwargs)` builds a single-task Dask graph, computes a key from `dask.base.tokenize(func, args, kwargs)` (unless `pure=False`, in which case a UUID is used), and creates a `Future` object locally. The graph and desired keys are passed to `_graph_to_futures()`, which calls the async `_update_graph()`.

`_update_graph()` serializes the graph expression using `protocol.serialize()` into a `Serialized` object, then calls `scheduler.update_graph(expr_ser=..., keys=..., ...)` over the RPC connection.

**Step 2 — Scheduler receives `update_graph`:** (`scheduler.py:4845`)

1. Deserializes the graph expression on an offload thread (keeps event loop free).
2. Materializes the graph: calls `_materialize_graph()` which converts the expression to a `dict[Key, GraphNode]`.
3. Runs `dask.order.order(dsk)` on an offload thread to compute task priorities.
4. Back on the event loop: calls `_create_taskstate_from_graph()` which creates `TaskState` objects and calls `_transition(key, "released", ...)` for each.
5. `_transitions()` runs the recommendations queue until stable.

**Step 3 — Scheduler transitions tasks:**

Each task key goes through `_transition(key, finish, stimulus_id)` (`scheduler.py:1987`). The transition calls the appropriate function from `_TRANSITIONS_TABLE` (class variable at `scheduler.py:3101`). The full table of valid scheduler transitions:

```
(released, waiting)       → _transition_released_waiting
(waiting, processing)     → _transition_waiting_processing
(waiting, queued)         → _transition_waiting_queued
(waiting, no-worker)      → _transition_waiting_no_worker
(waiting, memory)         → _transition_waiting_memory
(queued, processing)      → _transition_queued_processing
(processing, memory)      → _transition_processing_memory
(processing, erred)       → _transition_processing_erred
(processing, released)    → _transition_processing_released
(memory, released)        → _transition_memory_released
(memory, forgotten)       → _transition_memory_forgotten
(erred, released)         → _transition_erred_released
... and ~10 more
```

Transitions return `(Recs, ClientMsgs, WorkerMsgs)` where `Recs` is `dict[Key, new_state]`, a further set of recommended transitions processed in `_transitions()`.

**Step 4 — Worker assignment:**

When transitioning `waiting → processing`, `decide_worker_non_rootish()` (`scheduler.py:2397`) or `decide_worker_rootish_*()` is called:

- `decide_worker_non_rootish`: calls the module-level `decide_worker()` (`scheduler.py:9044`) which finds workers that already have the most dependency data, then picks the least busy among them.
- `decide_worker_rootish_queuing_enabled()` (`scheduler.py:2345`): for root tasks when `WORKER_SATURATION` is finite, picks the least-busy idle worker, or returns `None` to transition to `queued`.
- `decide_worker_rootish_queuing_disabled()` (`scheduler.py:2285`): sends tasks to workers in batches to encourage sibling co-location.

The `is_rootish()` check (`scheduler.py:3139`) heuristically identifies tasks whose group size exceeds `2 * total_nthreads` with few dependencies (and no restrictions).

**Step 5 — Worker receives compute-task:**

The worker's `stream_handlers` dict maps `"compute-task"` → `handle_compute_task()`. This creates a `ComputeTaskEvent` and calls `BaseWorker.handle_stimulus()` (`worker_state_machine.py:3701`), which delegates to `WorkerState.handle_stimulus()` (`worker_state_machine.py:1318`).

**Step 6 — Worker state machine transitions:**

`WorkerState.handle_stimulus()` processes each event, calls `_handle_event(stim)` to get recommendations, then calls `_transitions(recs)` to cascade. For a `ComputeTaskEvent`, the task moves `released → waiting` (if deps are missing) or `released → ready` (if all deps in memory).

When a thread slot is available, `ready → executing` fires and returns an `Execute(key, stimulus_id)` instruction. `BaseWorker.handle_stimulus()` sees this instruction and calls `asyncio.create_task(self.execute(key, ...))` (`worker_state_machine.py:3736–3744`).

**Step 7 — Task execution:**

`Worker.execute()` (`worker.py`, via `BaseWorker.execute()`) runs the task in the thread pool executor. On success it returns `ExecuteSuccessEvent`; on exception it returns `ExecuteFailureEvent`. These events are fed back into `handle_stimulus()` which triggers `executing → memory` or `executing → error`.

The state machine also emits `TaskFinishedMsg` or `TaskErredMsg` instructions, which `BaseWorker.handle_stimulus()` sends via `self.batched_send()`.

**Step 8 — Scheduler receives task-finished:**

`handle_task_finished()` (`scheduler.py:6048`) triggers `stimulus_task_finished()` (`scheduler.py:5253`), which transitions the task `processing → memory`. This cascades to notify `who_wants` (clients waiting for the result) and unblocks waiting dependents.

**Step 9 — Client retrieves result:**

`Future.result()` calls `client.gather([future])` which either sends a `gather` RPC to the scheduler (scheduler proxies the data) or directly calls `get-data` on the worker if `direct_to_workers=True`.

---

### 3.2 Scheduler State Machine

The scheduler state machine is split across two classes:

- **`SchedulerState`** (`scheduler.py:1610`): Pure state; holds all the dicts, sets, and state variables. All fields are declared as `__slots__`. No async I/O.
- **`Scheduler`** (`scheduler.py:3640`): Inherits `SchedulerState` + `ServerNode`. Handles network I/O, RPC handlers, periodic callbacks.

**TaskState states (scheduler side):** (`scheduler.py:159–168`)

| State | Meaning |
|-------|---------|
| `released` | Known but not computing; no worker assigned |
| `waiting` | Waiting for dependencies to enter `memory` |
| `queued` | Root-ish task waiting for a free worker thread slot |
| `no-worker` | No valid worker available (resource restrictions unmet) |
| `processing` | Assigned to a worker; worker is executing or about to |
| `memory` | Result available in memory on at least one worker |
| `erred` | Failed; exception is stored |
| `forgotten` | No longer tracked; TaskState will be GC'd |

**`_transition()` mechanics** (`scheduler.py:1987`):

1. Looks up `(start, finish)` in `_TRANSITIONS_TABLE`.
2. If not found and neither is `"released"`, does a two-step: `start → released → finish`.
3. Appends to `transition_log` (`deque` capped by config `distributed.admin.low-level-log-length`).
4. If `validate=True`, calls `validate_key()` after each batch.
5. Notifies all `SchedulerPlugin.transition()` hooks.
6. Increments `transition_counter`; raises if `transition_counter_max` exceeded (debug only).

**Transition recommendations cascade:** `_transitions()` (`scheduler.py:2133`) processes a `dict[Key, new_state]` queue in a while loop until empty. This allows one transition to produce recommendations for other keys, e.g., a task entering `memory` recommends that its dependents be re-evaluated.

---

### 3.3 Worker State Machine

The worker state machine (`worker_state_machine.py`) is deliberately separated from `worker.py`. The separation is a critical design choice explained in depth in Section 4.

**`WorkerState`** (`worker_state_machine.py:1048`): Pure state, no I/O. Key collections:

| Attribute | Type | Meaning |
|-----------|------|---------|
| `tasks` | `dict[Key, TaskState]` | All tasks this worker knows about |
| `ready` | `HeapSet[TaskState]` | Priority queue of tasks ready to execute |
| `constrained` | `HeapSet[TaskState]` | Ready but waiting on resources |
| `executing` | `set[TaskState]` | Currently running (counts toward nthreads limit) |
| `long_running` | `set[TaskState]` | Seceded tasks (do not count toward limit) |
| `in_flight_tasks` | `set[TaskState]` | Data being fetched from peers |
| `in_flight_workers` | `dict[str, set[Key]]` | Ongoing peer data transfers |
| `data_needed` | `defaultdict[str, HeapSet]` | Per-source-worker heap of tasks to fetch |
| `has_what` | `defaultdict[str, set[Key]]` | What data we think each peer worker has |
| `data` | `MutableMapping[Key, object]` | In-memory task results (shared w/ Worker) |

**Worker TaskState states** (`worker_state_machine.py:63–79`):

| State | Meaning |
|-------|---------|
| `released` | Known but not active |
| `waiting` | Waiting for dependencies |
| `ready` | All deps in memory; queued for execution |
| `constrained` | All deps ready but resource constraints block execution |
| `executing` | Running on a thread |
| `long-running` | Running after `secede()` was called |
| `fetch` | Dependency being fetched from a peer |
| `flight` | Data fetch in progress (GatherDep instruction issued) |
| `missing` | Dependency location unknown |
| `memory` | Result stored in `data` |
| `error` | Task failed |
| `rescheduled` | Worker called `raise Reschedule()` |
| `cancelled` | Scheduler said to cancel (async op still in flight) |
| `resumed` | Cancelled but the async op finished before cancel was processed |
| `forgotten` | Fully released and removed from `tasks` |

The full transition table is at `worker_state_machine.py:2491–2544`.

**`handle_stimulus()` flow** (`worker_state_machine.py:1318`):

```python
def handle_stimulus(self, *stims):
    instructions = []
    for stim in stims:
        self.stimulus_log.append(stim)
        recs, instr = self._handle_event(stim)
        instructions += instr
        instructions += self._transitions(recs, stimulus_id=stim.stimulus_id)
    return instructions
```

Each `StateMachineEvent` is dispatched by `_handle_event()` via `singledispatchmethod` (one handler per event class). Each handler returns `(Recs, Instructions)`. Instructions are returned to `BaseWorker.handle_stimulus()` which dispatches them to async tasks.

**Instruction types** (`worker_state_machine.py:343–560`):

| Instruction | Meaning |
|-------------|---------|
| `Execute(key, stimulus_id)` | Run this task in thread pool |
| `GatherDep(worker, to_gather, total_nbytes)` | Fetch keys from peer worker |
| `RetryBusyWorkerLater(worker)` | Back off from busy worker |
| `SendMessageToScheduler` | Subclass family; send async msg to scheduler |
| `TaskFinishedMsg` | Task succeeded |
| `TaskErredMsg` | Task failed |
| `ReleaseWorkerDataMsg` | Worker can release key |
| `RescheduleMsg` | Worker called `raise Reschedule()` |
| `LongRunningMsg` | Task called `secede()` |
| `AddKeysMsg` | Worker got new data not from a compute |
| `StealResponseMsg` | Response to steal-request |

**`cancelled` and `resumed` states:** These handle the race condition where the scheduler sends a `FreeKeysEvent` (cancel) while the worker is already mid-execution or mid-flight. `TaskState.previous` captures what state was interrupted, and `TaskState.next` captures where to go after the async op completes. If the cancel arrives before the async op completes, the task enters `cancelled(previous=executing/flight)`. If the async op then completes, it enters `resumed(previous→next)` and cleans up gracefully.

---

### 3.4 Futures

`Future` (`client.py:254`) is the client-side proxy to a remote computation.

- Each `Future` holds a `FutureState` (`client.py:645`) object which is shared among all `Future` instances with the same key (via `Client.futures` dict).
- `FutureState.status` mirrors the scheduler's TaskState: `"pending"`, `"finished"`, `"error"`, `"cancelled"`, `"lost"`.
- When the scheduler sends a `key-in-memory` event, `Client._handle_report()` updates `FutureState` and fires callbacks.
- Reference counting: `Client._inc_ref(key)` / `Client._dec_ref(key)` track how many `Future` objects reference a key. When ref count drops to zero, `client_releases_keys()` notifies the scheduler, which may eventually transition the task to `forgotten`.
- `future.result()` blocks (in a background thread for sync code, or awaits for async code) until the `FutureState` is done, then calls `gather()` to retrieve the result.

---

### 3.5 Work Stealing

**File:** `distributed/stealing.py`
**Class:** `WorkStealing` (`stealing.py:71`) — a `SchedulerPlugin`

**Purpose:** Redistribute tasks from overloaded workers to idle ones to reduce wall-clock time.

**Mechanism:**

1. A `PeriodicCallback` fires `balance()` every `distributed.scheduler.work-stealing-interval` (default 1s).
2. For each "processing" task, `put_key_in_stealable()` (`stealing.py:235`) classifies it into one of 15 "levels" (0–14) based on `steal_time_ratio()` (`stealing.py:267`): the ratio of communication cost to compute cost. Level 0 means pure root tasks (zero data deps). Level 14 means tasks so data-heavy that stealing is almost never worth it.
3. `balance()` iterates from cheapest to steal to most expensive, matching victim (overloaded) → thief (idle) pairs.
4. `move_task_request()` (`stealing.py:305`) sends a `steal-request` to the victim worker. This is a peer message via `Scheduler.stream_comms[victim]`.
5. The victim's worker state machine handles `StealRequestEvent` and responds with the task's current state in a `StealResponseMsg`.
6. `move_task_confirm()` (`stealing.py:356`) either reschedules the task (if it hasn't started yet) or rejects the steal (if already executing).

**Level computation:** `cost_multiplier = transfer_time / compute_time`, then `level = round(log2(cost_multiplier) + 6)` clamped to [1, 14]. Level 0 is used for root tasks with no dependencies.

**`LATENCY` constant** (`stealing.py:37`): 100ms conservative baseline added to transfer time, to suppress stealing of very small tasks.

**Guard against double-stealing:** `in_flight` dict (`stealing.py:84`) tracks tasks currently being stolen. A task in `in_flight` is skipped in future balance() calls until the steal is resolved.

---

### 3.6 Resilience and Retries

**Allowed failures:** `distributed.scheduler.allowed-failures` (default 3). Each time a worker dies with a task marked `processing`, `TaskState.suspicious` is incremented. Once it exceeds `allowed_failures`, the task transitions to `erred`.

**Explicit retries:** `client.submit(func, retries=5)` sets `TaskState.retries`. On failure, `_transition_processing_erred()` (`scheduler.py:2769`) checks `ts.retries > 0`, decrements it, and recommends `erred → released` (which then re-queues the task as `released → waiting → processing`).

**Worker death:** When a worker disconnects or times out (detected by `worker_ttl` heartbeat monitoring), `remove_worker()` is called. All tasks in `WorkerState.processing` are swept: they have `TaskState.suspicious` incremented and are sent to `stimulus_task_erred()`.

**Data loss:** If a task is in `memory` on a worker that dies, the scheduler may transition it back to `released → waiting` for recomputation. However, tasks with `run_spec = None` (scatter data) cannot be recomputed and become permanently lost.

**Error propagation:** An erred task's dependents transitioning through `_transition_waiting_released()` check `has_lost_dependencies`. If set, the task cascades to `forgotten`. Client `Future` objects receive a `task-erred` event with the serialized exception and traceback.

---

### 3.7 Memory Management

Memory management has three layers:

#### Layer 1: Worker local memory (worker_memory.py + spill.py)

`WorkerMemoryManager` (`worker_memory.py:74`) runs a `PeriodicCallback` every `distributed.worker.memory.monitor-interval` (default 100ms) to check four thresholds (all fractions of `memory_limit`):

| Threshold | Config key | Default | Action |
|-----------|-----------|---------|--------|
| `target` | `distributed.worker.memory.target` | 0.60 | Begin spilling managed data to disk |
| `spill` | `distributed.worker.memory.spill` | 0.70 | Aggressively spill (process memory based) |
| `pause` | `distributed.worker.memory.pause` | 0.80 | Stop executing new tasks |
| `terminate` | `distributed.worker.memory.terminate` | 0.95 | Kill the worker process |

`SpillBuffer` (`spill.py:69`) is a `zict.Buffer` subclass. It wraps two mappings: a fast in-memory dict and a slow disk-backed zict file. When the fast mapping exceeds the target byte count, data is serialized (using protocol serialize with compression) and moved to disk. When a key is accessed from the slow store, it is deserialized back. `SpilledSize` (`spill.py:24`) tracks both memory and disk sizes.

The `MemoryState` class on the scheduler side (`scheduler.py:268`) models a worker's memory as:
- `process`: Total OS-reported RSS
- `managed`: Sum of `sizeof()` for all dask keys in RAM
- `spilled`: Bytes of dask keys spilled to disk
- `unmanaged_old`: Non-dask memory held for > `recent-to-old-time` seconds
- `unmanaged_recent`: Non-dask memory delta (hopefully transient)
- `optimistic`: `managed + unmanaged_old` — the "safe" estimate

#### Layer 2: Active Memory Manager (active_memory_manager.py)

`ActiveMemoryManagerExtension` (`active_memory_manager.py:36`) is a scheduler extension that runs policies periodically (every 2s by default).

Built-in policies:
- **`ReduceReplicas`**: For tasks in `memory` on more than one worker, suggest dropping extra replicas. Enabled by default.
- **`RetireWorker`**: When `client.retire_workers()` is called, moves all data off a worker before removing it.

Policy interface: each policy is a generator that yields `("replicate", ts, None)` or `("drop", ts, worker)` suggestions. The AMM then applies them if they are safe (never drops the last replica).

#### Layer 3: Rebalance

`Scheduler.rebalance()` (`scheduler.py:6888`) is a manual or AMM-triggered operation that moves data from workers with high memory usage to workers with low usage. It uses `MemoryState` measures (configurable via `distributed.worker.memory.rebalance.measure`, default `optimistic`) with sender-min (0.30) and recipient-max (0.60) thresholds.

---

### 3.8 P2P Shuffle

**Files:** `distributed/shuffle/` (10+ files)
**Purpose:** Efficient repartitioning of large datasets (e.g., `DataFrame.shuffle()`, `merge()`) without routing all data through the scheduler.

**Architecture:**
- Orchestrated by `ShuffleSchedulerPlugin` (registers as a scheduler plugin).
- Each worker runs `ShuffleWorkerPlugin` which manages `ShuffleRun` objects.
- Data is partitioned locally, then sent peer-to-peer between workers using a `CommShardsBuffer` (network) and `DiskShardsBuffer` (spill).

**Phases:**
1. **Transfer phase:** Each worker calls `shuffle_transfer()` (`shuffle/_shuffle.py:50`) for each input partition. Data is split by destination worker using `split_by_worker()`, converted to Arrow tables, and buffered.
2. **Barrier:** The scheduler waits for all transfer tasks to complete before allowing unpack tasks to start. The `ShuffleSchedulerPlugin` enforces this.
3. **Unpack phase:** Each worker calls `shuffle_unpack()` (`shuffle/_shuffle.py:63`) to retrieve its assigned output partition from the buffers.

**`ShuffleId`** is a `NewType(str)` unique identifier per shuffle operation. A `run_id` integer disambiguates retries.

**Error handling:** `P2PConsistencyError` signals a state mismatch. `ShuffleClosedError` signals the shuffle was aborted (worker died, etc.). Workers retry transfers with exponential backoff (`RETRY_COUNT`, `RETRY_DELAY_MIN`, `RETRY_DELAY_MAX` on `ShuffleRun`).

---

### 3.9 Adaptive Scaling

**Files:** `deploy/adaptive.py`, `deploy/adaptive_core.py`
**Class:** `Adaptive` (`adaptive.py:37`)

Triggered by `cluster.adapt(minimum=2, maximum=10)`.

**Mechanism:**
1. A `PeriodicCallback` fires every `interval` ms (default 1000ms).
2. `Adaptive.recommendations()` queries `Scheduler.adaptive_target()` which returns a recommended number of workers based on:
   - Number of queued tasks (tasks in `waiting`, `no-worker`, `queued`, `processing`)
   - Desired throughput (`target_duration`)
3. If target > current workers: calls `cluster.scale(target)` to add workers.
4. If target < current: calls `Scheduler.workers_to_close()` which identifies idle workers. Workers are only suggested for removal `wait_count` consecutive times (default 3) before removal is confirmed.
5. Removal goes through `client.retire_workers()` → `AMM.RetireWorker` policy to safely drain data.

---

### 3.10 Actors

**File:** `distributed/actor.py`
**Purpose:** Stateful long-lived objects on workers with method-call semantics.

Created with `future = client.submit(MyClass, actor=True)`. The `future.result()` returns an `Actor` proxy object.

`Actor` (`actor.py:23`) proxies attribute access and method calls to the remote object via `worker.actor_execute()`. Calls go directly to the worker (not via the scheduler). Return values are `BaseActorFuture` objects that block or await to get results.

Unlike regular tasks, actors are never garbage-collected by the scheduler while the `Actor` proxy is alive. `TaskState.actor = True` marks the task; it stays in `memory` state indefinitely.

Actor methods run in the **event loop** of the worker if they are coroutines, or in the thread pool otherwise. This means non-coroutine actor methods must not do I/O without `await`/`run_in_executor`.

---

### 3.11 Publish Datasets

**File:** `distributed/publish.py`
**Extension:** `PublishExtension` (registered as `"publish"` in `DEFAULT_EXTENSIONS`)

`client.publish_dataset(x=future)` stores a reference to the future in the scheduler under a named key. Any other client can retrieve it with `client.get_dataset("x")`. This persists the future's data in cluster memory until explicitly unpublished.

---

### 3.12 Coordination Primitives

All coordination primitives are implemented as scheduler extensions. The scheduler is the authority; clients send RPCs to extensions.

| Primitive | File | Scheduler Extension | Client Class |
|-----------|------|--------------------|-----------| 
| `Lock` | `lock.py` | `SemaphoreExtension` | `Lock(Semaphore)` |
| `Semaphore` | `semaphore.py` | `SemaphoreExtension:22` | `Semaphore` |
| `Event` | `event.py` | `EventExtension:17` | `Event` |
| `Queue` | `queues.py` | `QueueExtension` | `Queue` |
| `Variable` | `variable.py` | `VariableExtension` | `Variable` |
| `MultiLock` | `multi_lock.py` | `MultiLockExtension` | `MultiLock` |

**`Semaphore`** uses lease-based locking: clients periodically refresh leases, and the scheduler invalidates expired leases. This prevents deadlocks if a client dies while holding the lock.

**`Event`** allows `event.wait()` (blocking) and `event.set()` / `event.clear()`. The scheduler keeps event state and notifies waiting clients.

**`Variable`** (`variable.py`) stores an arbitrary value (a Future or a literal). It is like a mutable shared future: setting it to a new future releases the old one from the scheduler's perspective.

---

### 3.13 Dashboard

Bokeh server lives in `distributed/dashboard/`. The main application is registered as a Tornado web application in the scheduler.

Key dashboard pages:
- `/status` — main task stream and worker status
- `/tasks` — full task stream history
- `/workers` — per-worker memory and CPU
- `/profile` — statistical profiler heat map
- `/graph` — task dependency graph (for small graphs)
- `/info/main/workers.html` — worker detail table

The dashboard uses server-side Bokeh (streaming data from scheduler state via periodic callbacks) rather than client-side reactive patterns.

---

### 3.14 Security / TLS

**File:** `distributed/security.py`
**Class:** `Security` (`security.py:56`)

Configured by:
```yaml
distributed:
  security:
    require-encryption: true
    tls:
      ca-file: /path/to/ca.pem
      scheduler:
        cert: /path/to/scheduler.crt
        key:  /path/to/scheduler.key
      worker:
        cert: /path/to/worker.crt
        key:  /path/to/worker.key
      client:
        cert: /path/to/client.crt
        key:  /path/to/client.key
```

`Security.get_connection_args("worker")` returns kwargs for TCP connections including the `ssl_context`. The TCP comm layer wraps the Tornado IOStream with `ssl` in TLS mode.

**`Security.temporary()`** generates self-signed certificates for dev/testing. Setting `security=True` in `LocalCluster` triggers this.

Allowed imports on scheduler: `distributed.yaml:scheduler.allowed-imports` controls which modules the scheduler will `import_term()` for extension loading, preventing arbitrary code execution via scheduler config.

---

### 3.15 Preloading

**File:** `distributed/preloading.py`
**Entry:** `PreloadManager` class

Configured via `distributed.scheduler.preload` / `distributed.worker.preload` / `distributed.nanny.preload-nanny` (lists of module paths or URLs).

Preload modules may define:
- `dask_setup(server)` — called at startup with the `Scheduler` or `Worker` instance
- `dask_teardown(server)` — called at shutdown
- If `dask_setup` is a `click.Command`, it can accept CLI args passed via `preload-argv`

This allows users to register custom scheduler plugins, add worker plugins, configure logging, or set up custom data stores without modifying distributed's source.

---

### 3.16 Spans

**File:** `distributed/spans.py`
**Purpose:** Group tasks into named "spans" for performance attribution and diagnostics.

```python
with span("data-loading") as span_id:
    result = client.compute(large_df)
```

Spans are propagated via `dask.annotate(span={"name": ..., "ids": ...})`. The scheduler's `SpansSchedulerExtension` collects timing data per span. Each `TaskGroup` has a `span_id`. The dashboard shows per-span timing.

The `Span` class (`spans.py:79`) is a tree node. Spans can be nested; the outermost span IDs form a path like `("data-loading", "preprocessing")`.

---

## 4. Nuances, Subtleties, and Gotchas

### 4.1 Tornado IOLoop + asyncio Bridging

The scheduler and worker both use Tornado's `IOLoop.current()` which, since Tornado 5, wraps asyncio's event loop. Code using `asyncio.get_event_loop()` and `IOLoop.current()` refer to the same loop. However:

- **Never block the event loop.** The scheduler is single-threaded. Any synchronous call that takes > a few ms will cause latency spikes visible cluster-wide. CPU-bound operations (like graph ordering) are explicitly offloaded with `offload()` (`utils.py`) which runs them in a thread pool via `asyncio.get_event_loop().run_in_executor()`.
- `sync(loop, coro)` (`utils.py`) is used to call async coroutines from synchronous code (the "sync bridge"). This submits the coroutine to the running event loop from a different thread and blocks until done.
- The `SyncMethodMixin` on `Client` uses `sync()` to make async methods appear synchronous to users. Setting `asynchronous=True` on `Client` skips this.

### 4.2 Scheduler Is Single-Threaded; Worker Has a Thread Pool

**Scheduler:** All state mutations happen in the single asyncio event loop. No locks needed for scheduler state. This is the entire reason for `SchedulerState.__slots__` — fast attribute access without `__dict__` overhead on a hot path called millions of times per second.

**Worker:** The `asyncio` event loop handles network I/O and state machine transitions. The thread pool (`Worker.executors`, a `ThreadPoolExecutor(nthreads)`) runs actual task functions. Results flow back: `execute()` coroutine awaits `loop.run_in_executor(executor, run_task, ...)`, gets the result, then resumes on the event loop to feed `ExecuteSuccessEvent` back into the state machine.

Critical invariant: **`WorkerState` is only ever mutated from the event loop thread.** The thread pool must not touch `WorkerState` attributes directly.

### 4.3 Why worker_state_machine.py Is Separate from worker.py

`worker_state_machine.py` contains:
- `TaskState` (worker side)
- `WorkerState` (the pure state machine)
- All `StateMachineEvent` and `Instruction` dataclasses
- `BaseWorker` (abstract class bridging state machine to async instructions)

This separation enables:
1. **Unit testing without a cluster.** `WorkerState` can be instantiated and fed events directly without network. Tests in `tests/test_worker_state_machine.py` construct `WorkerState` objects, call `handle_stimulus()`, and assert on returned instructions and state — all synchronously.
2. **Deterministic replay.** Given a `stimulus_log`, you can re-replay events into a fresh `WorkerState` and reproduce bugs exactly. `cluster_dump` captures `stimulus_log` for post-mortem.
3. **Clarity.** The split makes clear what is pure logic (state machine) vs. side-effecting I/O (Worker).

The `BaseWorker.handle_stimulus()` (`worker_state_machine.py:3701`) is the bridge: it calls `WorkerState.handle_stimulus()` to get instructions, then dispatches each instruction to async operations.

### 4.4 Serialization Pitfalls

- **Large objects in task arguments:** If you pass a 1 GB NumPy array as an argument to `client.submit()`, it is serialized and sent through the scheduler. Use `client.scatter()` first to put it on a worker, then pass the resulting `Future` as the argument.
- **Pickle of lambdas / closures:** `cloudpickle` (used via `distributed.protocol.pickle`) can serialize most lambdas and closures, but closures over large data structures will serialize that data. Use explicit `dask.delayed` with proper data dependencies instead.
- **dask_serialize dispatch:** If you add custom serialization via `dask_serialize.register(MyType)`, the function must return `(header_dict, [frame, ...])` where frames are bytes-like objects. The header is msgpacked; frames are sent as raw binary. Forgetting to register a type means `pickle` fallback, which may be slow or incorrect for GPU arrays.
- **`ToPickle` vs `Serialized`:** `ToPickle` wraps an object to signal "use pickle"; `Serialized` wraps already-serialized data. Do not confuse them. Passing a `Serialized` to a worker as a task argument when you intend the value (not its serialized form) is a silent bug.
- **Deserialization on the worker thread:** By default, task arguments are deserialized in the offload thread pool (`Comm.allow_offload = True`). If deserialization is slow (e.g., decompressing a large array), it does not block the event loop.

### 4.5 `Comm.read/write` Contract and `BatchedSend`

- `Comm.write(msg)` is a coroutine; it must be awaited. Messages must be Python objects serializable by the protocol layer (dicts of primitives, with `Serialized` wrappers for binary).
- `Comm.read()` is a coroutine; it returns one message at a time. The message is a Python object (usually a dict).
- `BatchedSend.send(msg)` is **synchronous** — it just appends to a buffer list. The actual send happens in the background coroutine. This means you can safely call `bstream.send()` from synchronous code running in the event loop.
- Do not call `await comm.write()` if you meant to use `bstream.send()`. The former bypasses batching and is per-message. The scheduler exclusively uses `BatchedSend` for `client_comms` and `stream_comms`.

### 4.6 Stimulus IDs and Deterministic Replay

Every state transition has a `stimulus_id` string (e.g., `"task-finished-abc123-1234567890"`). This serves two purposes:

1. **Correlation:** The scheduler matches steal-responses, task-finished reports, etc. to their originating actions. In `move_task_confirm()`, the scheduler verifies that the `stimulus_id` in the response matches the one sent, discarding stale responses.
2. **Replay:** The `stimulus_log` on `WorkerState` records every `StateMachineEvent` with its stimulus_id. `cluster_dump` captures this. A developer can replay events into a fresh `WorkerState` to reproduce the exact sequence leading to a bug.

`STIMULUS_ID_UNSET` (`scheduler.py:187`) is a sentinel that causes an assertion failure during validation if a transition happens without a proper stimulus_id — helps catch missing provenance in new code.

### 4.7 Cluster Dump Debugging Pattern

`client.dump_cluster_state(filename)` (`cluster_dump.py`) serializes the full cluster state to a msgpack or YAML file. This includes:
- All `TaskState` objects on the scheduler
- All `WorkerState` objects on each worker
- The `transition_log` and `stimulus_log` from each

To debug a deadlock or unexpected state, enable `distributed.admin.pdb-on-err: true` (drops into pdb on scheduler/worker errors) or use `distributed.validate: true` (enables expensive consistency checks after every transition). For post-mortem analysis:

```python
import msgpack, gzip
with gzip.open("dump.msgpack.gz") as f:
    state = msgpack.unpack(f)
# state["scheduler"]["tasks"]["<key>"] gives the task dict
```

The `_stories.py` module provides `scheduler_story(keys, transition_log)` and `worker_story(keys, log)` to filter the log to entries touching specific keys.

### 4.8 Known Performance Bottlenecks

1. **`update_graph` graph materialization:** Converting a Dask expression to a task dict is CPU-bound. It is offloaded, but for very large graphs (millions of tasks), this can take seconds during which no other `update_graph` calls can complete (they queue on the async semaphore).

2. **Task state transition overhead:** Each call to `_transition()` involves multiple dict lookups and set operations. At >100k transitions/second, the overhead accumulates. The `__slots__` optimization on `TaskState` (`scheduler.py:1431`) was specifically added to reduce attribute access overhead.

3. **`sizeof()` inaccuracy:** The `safe_sizeof()` call in `worker_state_machine.py` (via `distributed/sizeof.py`) can be slow or inaccurate for custom objects. Inaccurate sizes cause incorrect memory management decisions. Register accurate sizeof implementations via `dask.sizeof.register(MyType)`.

4. **BatchedSend interval:** The default interval (2ms for scheduler→worker) means task assignments are delayed by up to 2ms. For latency-sensitive workloads, this can be reduced.

5. **Scheduler-side `decide_worker()` iteration:** For tasks with many dependencies on many workers, `decide_worker()` (`scheduler.py:9044`) iterates over `{wws for dts in ts.dependencies for wws in dts.who_has}` which is O(deps × replicas). For highly replicated large graphs this can be slow.

---

## 5. Technical Reference and Glossary

### Domain Terms

| Term | Definition |
|------|-----------|
| **key** | A `dask.typing.Key` — unique identifier for a task or piece of data. Usually a string like `"inc-ab31c010"` or a tuple. |
| **dependency** | A task whose result must be in memory before another task can run. `TaskState.dependencies` on scheduler; `TaskState.dependencies` on worker. |
| **dependent** | The reverse of dependency. `TaskState.dependents`. |
| **who_has** | `dict[TaskState, set[WorkerState]]` on scheduler: which workers have a task's result. |
| **has_what** | `dict[WorkerState, dict[TaskState, None]]` on scheduler (and `defaultdict[str, set[Key]]` on worker): what keys a worker holds. |
| **priority** | A tuple used for ordering tasks. Lower tuple values execute first. First element is global order; second is client-assigned priority. |
| **resource restriction** | `TaskState.resource_restrictions` — named abstract resources (e.g., `{"GPU": 1}`) a task requires. Worker must have sufficient `available_resources`. |
| **annotation** | Arbitrary metadata attached to a task via `dask.annotate(...)`. Stored in `TaskState.annotations`. |
| **span** | A named group of tasks for performance attribution. Identified by a UUID string (`span_id`). |
| **stimulus** | A `StateMachineEvent` that drives the worker state machine. All external events are modeled as stimuli. |
| **transition** | A single state change for one task. Recorded in `Transition` NamedTuple (scheduler) or appended to `log` deque (worker). |
| **rootish task** | A task in a large group with few or no dependencies. Eligible for the queuing optimization. See `is_rootish()`. |
| **occupancy** | The total expected remaining compute time for all tasks assigned to a worker. Used by work stealing. |
| **stimulus_id** | A unique string identifying the cause of a state change. Used for correlation and deterministic replay. |
| **run_id** | Integer on `TaskState` (scheduler) uniquely identifying one assignment of a task to a worker. Stale task-finished messages from previous assignments are rejected. |
| **computation** | A `Computation` object grouping all tasks submitted in one `update_graph()` call. |

### Key Classes

| Class | File:Line | Role |
|-------|-----------|------|
| `Scheduler` | `scheduler.py:3640` | Main scheduler: I/O + SchedulerState |
| `SchedulerState` | `scheduler.py:1610` | Pure state: tasks, workers, clients |
| `TaskState` (scheduler) | `scheduler.py:1223` | Per-task state on scheduler |
| `WorkerState` (scheduler) | `scheduler.py:415` | Per-worker view from scheduler |
| `ClientState` | `scheduler.py:205` | Per-client tracking on scheduler |
| `MemoryState` | `scheduler.py:268` | Structured memory metrics for one worker |
| `TaskGroup` | `scheduler.py:1102` | All tasks with same key prefix+hash |
| `TaskPrefix` | `scheduler.py:1004` | All tasks with same function name |
| `Transition` | `scheduler.py:1599` | NamedTuple log entry for one transition |
| `Computation` | `scheduler.py:882` | Groups tasks from one update_graph call |
| `Worker` | `worker.py:279` | Worker process: async I/O + thread pool |
| `BaseWorker` | `worker_state_machine.py:3582` | Abstract bridge: state machine → async ops |
| `WorkerState` (worker) | `worker_state_machine.py:1048` | Pure state machine for worker |
| `TaskState` (worker) | `worker_state_machine.py:204` | Per-task state on worker |
| `StateMachineEvent` | `worker_state_machine.py:562` | Base class for all worker stimuli |
| `Instruction` | `worker_state_machine.py:343` | Command from state machine to BaseWorker |
| `Client` | `client.py:952` | User-facing cluster interface |
| `Future` | `client.py:254` | Proxy for a remote computation |
| `FutureState` | `client.py:645` | Shared state for all Futures of same key |
| `Nanny` | `nanny.py:69` | Supervisor process for Worker |
| `WorkerProcess` | `nanny.py:657` | Subprocess wrapper in Nanny |
| `Comm` | `comm/core.py:33` | Abstract message-oriented comm channel |
| `BatchedSend` | `batched.py:20` | Batched async message sender |
| `Status` | `core.py:78` | Enum: undefined/created/running/paused/stopping/stopped/closing/closed/failed |
| `WorkStealing` | `stealing.py:71` | Scheduler plugin for load balancing |
| `ActiveMemoryManagerExtension` | `active_memory_manager.py:36` | Scheduler extension for memory policies |
| `SpillBuffer` | `spill.py:69` | zict.Buffer with disk overflow |
| `WorkerMemoryManager` | `worker_memory.py:74` | Monitors and enforces memory thresholds |
| `Security` | `security.py:56` | TLS configuration container |
| `Adaptive` | `deploy/adaptive.py:37` | Auto-scaling logic |
| `SpecCluster` | `deploy/spec.py` | Base class for all cluster types |
| `LocalCluster` | `deploy/local.py:23` | Single-machine cluster |
| `ShuffleRun` | `shuffle/_core.py:73` | One P2P shuffle operation |
| `Actor` | `actor.py:23` | Client proxy for remote stateful object |
| `Span` | `spans.py:79` | Named group of tasks for tracing |

### Configuration Files

**`distributed/distributed.yaml`** — Default configuration. Keys under `distributed:`:

| Key | Default | Description |
|-----|---------|-------------|
| `scheduler.allowed-failures` | 3 | Retries before task is erred |
| `scheduler.bandwidth` | 100MB/s | Estimated worker-worker bandwidth for steal decisions |
| `scheduler.work-stealing` | True | Enable work stealing |
| `scheduler.work-stealing-interval` | 1s | How often to run balance() |
| `scheduler.worker-saturation` | 1.1 | Max ratio of tasks:threads before a worker is "saturated" |
| `scheduler.unknown-task-duration` | 500ms | Duration estimate for unseen task prefixes |
| `scheduler.validate` | False | Enable expensive consistency checks |
| `worker.memory.target` | 0.60 | Fraction at which to start spilling |
| `worker.memory.spill` | 0.70 | Fraction at which to spill aggressively |
| `worker.memory.pause` | 0.80 | Fraction at which to pause worker |
| `worker.memory.terminate` | 0.95 | Fraction at which to kill worker |
| `worker.memory.monitor-interval` | 100ms | How often to check memory |
| `worker.memory.recent-to-old-time` | 30s | Window for unmanaged memory smoothing |
| `worker.nthreads` | CPU count | Thread pool size per worker |
| `admin.low-level-log-length` | (check yaml) | Max entries in transition_log, stimulus_log |
| `comm.timeouts.connect` | 30s | Connection timeout |
| `comm.timeouts.tcp` | 30s | TCP read/write timeout |

**`distributed/distributed-schema.yaml`** — JSON Schema for config validation. Used by `dask.config.collect()`.

### Environment Variables

| Variable | Effect |
|----------|--------|
| `MALLOC_TRIM_THRESHOLD_` | (Linux) Controls glibc malloc trim threshold; set before process start |
| `OMP_NUM_THREADS` | Controls OpenMP thread count for numpy etc.; must be set before import |
| `DASK_DISTRIBUTED__SCHEDULER__WORK_STEALING` | Override config via env (dask config env convention) |
| `DASK_DISTRIBUTED__WORKER__MEMORY__PAUSE` | Override worker memory pause threshold |

All `distributed.yaml` config keys can be overridden via environment variables using `DASK_` prefix + `__` as separator + uppercase.

---

## 6. Cross-Cutting Concerns

### Logging

Loggers are created per-module with `logging.getLogger(__name__)`. Key loggers:
- `distributed.scheduler` — scheduler state transitions at DEBUG, important events at INFO
- `distributed.worker` — worker task events
- `distributed.worker.state_machine` — worker state machine transitions (very verbose at DEBUG)
- `distributed.worker.memory` — memory management events
- `distributed.stealing` — work stealing decisions
- `distributed.nanny` — worker process lifecycle

Rate-limited loggers: `worker_memory.py` uses `RateLimiterFilter` to suppress repeated "Unmanaged memory use is high" warnings (rate: 300s). This prevents log flooding under sustained high memory pressure.

`LOG_PDB = dask.config.get("distributed.admin.pdb-on-err")` — when True, drops into `pdb.set_trace()` on scheduler/worker exceptions instead of just logging. Useful for debugging in interactive sessions.

### Metrics (Prometheus)

Prometheus metrics are exposed at `GET /metrics` on the scheduler and worker HTTP servers. The routes are registered via `distributed.yaml:scheduler.http.routes` and `worker.http.routes` pointing to `distributed.http.scheduler.prometheus` and `distributed.http.worker.prometheus`.

`Scheduler.digest_metric(name, value)` / `Worker.digest_metric(name, value)` accumulate metrics internally. `context_meter` (`metrics.py`) provides a context manager for capturing timing of code blocks.

`Scheduler.cumulative_worker_metrics` is a `defaultdict[tuple|str, int]` that accumulates per-worker metrics reported via heartbeats.

### Testing (`utils_test.py`, `gen_cluster`)

The primary test fixture is `gen_cluster` (`utils_test.py`). Usage:

```python
from distributed.utils_test import gen_cluster

@gen_cluster(client=True)
async def test_something(c, s, a, b):
    # c: Client, s: Scheduler, a: Worker, b: Worker
    future = c.submit(add, 1, 2)
    result = await future
    assert result == 3
```

`gen_cluster` starts a real `LocalCluster` with a live scheduler and `n_workers` workers (default 2), runs the test coroutine, then tears everything down. It is the authoritative test pattern — do not mock `Scheduler` or `Worker` internals.

For pure state machine tests, use `WorkerState` directly without a cluster:

```python
ws = WorkerState(nthreads=1)
instructions = ws.handle_stimulus(ComputeTaskEvent(...))
assert instructions == [Execute.match(key="x")]
```

`_InstructionMatch` (`worker_state_machine.py:377`) supports partial matching of instructions for test assertions.

### CI Structure

- Tests live in `vendor/distributed/distributed/tests/` and per-package `tests/` subdirectories.
- `pytest` with `pytest-asyncio` for async tests.
- Slow tests are marked `@pytest.mark.slow`.
- Flaky tests (network timing sensitive) use `@pytest.mark.flaky`.
- CI configuration is in `vendor/distributed/continuous_integration/` (excluded from this analysis per requirements).

### Plugin API

**`SchedulerPlugin`** (`diagnostics/plugin.py`) — subclass and implement:
- `start(scheduler)` — called when scheduler starts
- `stop(scheduler)` — called on shutdown
- `add_worker(scheduler, worker)` — new worker connected
- `remove_worker(scheduler, worker, *, stimulus_id)` — worker disconnected
- `update_graph(scheduler, *, keys, ...)` — new tasks submitted
- `transition(key, start, finish, *, stimulus_id, **kwargs)` — task state changed

Register via `scheduler.add_plugin(plugin)` or in `Client` constructor. Built-in plugins: `WorkStealing`, `ShuffleSchedulerPlugin`, `SpansSchedulerExtension`.

**`WorkerPlugin`** — subclass and implement:
- `setup(worker)` — called when worker starts
- `teardown(worker)` — called on shutdown
- `transition(key, start, finish, **kwargs)` — task state changed on worker
- `release_key(key, state, cause, reason, report)` — key released

Register via `client.register_worker_plugin(plugin)`.

**`NannyPlugin`** — similar to WorkerPlugin but for Nanny processes.

---

## Appendix: File-to-Feature Quick Reference

| File | Primary Feature |
|------|----------------|
| `scheduler.py` | Scheduler, SchedulerState, TaskState (sched), WorkerState (sched), all _transition_* methods |
| `worker.py` | Worker class, execute(), gather_dep() implementations |
| `worker_state_machine.py` | WorkerState (pure SM), BaseWorker, all events/instructions |
| `worker_memory.py` | WorkerMemoryManager, spill/pause/terminate logic |
| `client.py` | Client, Future, FutureState, as_completed |
| `nanny.py` | Nanny, WorkerProcess (subprocess management) |
| `batched.py` | BatchedSend |
| `core.py` | Server, ServerNode, Status, rpc, Comm base, send_recv |
| `stealing.py` | WorkStealing plugin |
| `active_memory_manager.py` | AMM extension, ReduceReplicas, RetireWorker |
| `spill.py` | SpillBuffer (zict-based disk spill) |
| `spans.py` | span() context manager, Span class, SpansExtension |
| `actor.py` | Actor proxy, BaseActorFuture |
| `security.py` | Security (TLS config) |
| `preloading.py` | PreloadManager |
| `cluster_dump.py` | dump_cluster_state, write_state |
| `publish.py` | PublishExtension, client publish/get_dataset |
| `event.py` | EventExtension, Event |
| `lock.py` | Lock (thin Semaphore wrapper) |
| `semaphore.py` | SemaphoreExtension, Semaphore |
| `queues.py` | QueueExtension, Queue |
| `variable.py` | VariableExtension, Variable |
| `comm/core.py` | Comm ABC, CommClosedError |
| `comm/tcp.py` | TCP and TLS transports |
| `comm/ucx.py` | UCX/RDMA transport |
| `protocol/serialize.py` | serialize/deserialize, dask_serialize registry |
| `protocol/pickle.py` | cloudpickle wrapper |
| `deploy/local.py` | LocalCluster |
| `deploy/spec.py` | SpecCluster, ProcessInterface |
| `deploy/adaptive.py` | Adaptive (auto-scaling) |
| `shuffle/_core.py` | ShuffleRun, ShuffleSpec base classes |
| `shuffle/_shuffle.py` | DataFrame shuffle/merge P2P implementation |
| `utils_test.py` | gen_cluster, gen_test, various test fixtures |
| `utils.py` | offload, sync, log_errors, wait_for |
| `distributed.yaml` | All default configuration |
