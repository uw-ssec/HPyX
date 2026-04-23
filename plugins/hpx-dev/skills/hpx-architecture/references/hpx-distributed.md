# HPX Distributed Computing Guide

Detailed guide to HPX's distributed computing features for future HPyX binding development.

## Overview

HPX's distributed computing model is built on three pillars:
1. **AGAS (Active Global Address Space)** — Global naming and object location
2. **Actions** — Remote procedure calls
3. **Components** — Distributed objects with remote interfaces

These features require the TCP or MPI parcelport to be enabled (`tcp_enable=True` in HPXRuntime).

## AGAS — Active Global Address Space

AGAS provides transparent object location and migration across localities (nodes).

### Key Concepts
- **Locality**: A single process (node) in the HPX runtime
- **GID (Global ID)**: Unique identifier for any object across all localities
- **id_type**: HPX's global reference type, wraps a GID

### Core APIs
```cpp
// Get current locality
hpx::id_type here = hpx::find_here();

// Get all localities
std::vector<hpx::id_type> localities = hpx::find_all_localities();

// Get number of localities
std::size_t n = hpx::get_num_localities().get();

// Get locality of an object
hpx::id_type loc = hpx::get_colocation_id(object_id).get();
```

### Binding Strategy for Python
Expose locality discovery first:
```python
# Proposed Python API
from hpyx.distributed import get_locality, get_all_localities, get_num_localities

with HPXRuntime(tcp_enable=True):
    here = get_locality()          # Current node
    all_locs = get_all_localities() # All nodes
    n = get_num_localities()        # Count
```

## Actions — Remote Procedure Calls

Actions wrap functions for remote invocation. HPX automatically serializes arguments, sends them to the target locality, executes the function, and returns the result as a future.

### Types of Actions
1. **Plain actions**: Wrap free functions
2. **Component actions**: Wrap member functions of components

### Definition Pattern (C++)
```cpp
// Define a plain action
int compute(int x) { return x * x; }
HPX_PLAIN_ACTION(compute, compute_action);

// Invoke remotely
hpx::id_type target_locality = ...;
hpx::future<int> result = hpx::async(compute_action{}, target_locality, 42);
```

### Binding Challenges
- Actions require HPX macros (`HPX_PLAIN_ACTION`) at compile time
- Python callables cannot be directly converted to HPX actions
- Serialization of Python objects across nodes is non-trivial

### Proposed Binding Strategy
Create pre-defined C++ actions that accept serializable data types (arrays, scalars, strings) and wrap common parallel patterns:
```python
# Proposed: Pre-built distributed algorithms
from hpyx.distributed import distributed_reduce, distributed_map

with HPXRuntime(tcp_enable=True):
    # Scatter data across localities, reduce results
    result = distributed_reduce(data, operation="sum")

    # Map a pre-registered function across localities
    results = distributed_map("compute_function_name", chunks)
```

## Components — Distributed Objects

Components are C++ objects with a globally unique identity that can be accessed from any locality.

### Key Concepts
- Components are managed by AGAS
- They have actions (remote-callable methods)
- They can migrate between localities
- Lifecycle managed through shared ownership (like `shared_ptr`)

### Definition Pattern (C++)
```cpp
// Server side (where component lives)
struct my_component : hpx::components::component_base<my_component>
{
    int compute(int x) { return x * x; }
    HPX_DEFINE_COMPONENT_ACTION(my_component, compute, compute_action);
};

// Client side (remote access)
struct my_client : hpx::components::client_base<my_client, my_component>
{
    hpx::future<int> compute(int x) {
        return hpx::async(my_component::compute_action{}, this->get_id(), x);
    }
};
```

### Binding Strategy
Create a Python wrapper that abstracts the component pattern:
```python
# Proposed: Distributed object pattern
from hpyx.distributed import DistributedArray

with HPXRuntime(tcp_enable=True):
    # Create array distributed across localities
    darr = DistributedArray(data, num_partitions=4)

    # Operations automatically distributed
    result = darr.reduce(operation="sum")
    transformed = darr.map(lambda x: x * 2)  # Requires serialization strategy
```

## Parcelports — Network Transport

Parcelports handle network communication between localities.

### Available Transports
- **TCP**: Default, works everywhere
- **MPI**: High-performance, requires MPI installation
- **LCI**: Lightweight Communication Interface (experimental)

### Configuration
```python
# TCP (default distributed transport)
with HPXRuntime(tcp_enable=True):
    pass

# MPI (via HPX config)
cfg = ["hpx.parcel.mpi.enable!=1"]
hpyx._core.init_hpx_runtime(cfg)
```

### Multi-Node Execution
```bash
# TCP transport
mpirun -np 4 python my_script.py --hpx:threads=4

# With explicit localities
python my_script.py --hpx:localities=4 --hpx:threads=4
```

## Implementation Roadmap for HPyX

### Phase 1: Locality Discovery (Low complexity)
- `hpx::find_here()` → `hpyx.distributed.get_locality()`
- `hpx::find_all_localities()` → `hpyx.distributed.get_all_localities()`
- `hpx::get_num_localities()` → `hpyx.distributed.get_num_localities()`

### Phase 2: Remote Execution (Medium complexity)
- Pre-built C++ actions for common operations (reduce, map, scatter, gather)
- Python API for invoking pre-built distributed algorithms
- Data serialization via NumPy arrays (binary-compatible)

### Phase 3: Distributed Data Structures (High complexity)
- Distributed arrays with partitioned storage
- Automatic data distribution across localities
- Collective operations on distributed data

### Phase 4: Custom Actions (Very high complexity)
- Runtime action registration from Python
- Python callable serialization strategy
- Hybrid approach: C++ actions with Python configuration

## Key HPX Source Locations

```
vendor/hpx/libs/full/actions/         — Action framework
vendor/hpx/libs/full/actions_base/    — Action base classes
vendor/hpx/libs/full/agas/            — AGAS implementation
vendor/hpx/libs/full/collectives/     — Collective operations
vendor/hpx/libs/full/components/      — Component framework
vendor/hpx/libs/full/distribution_policies/ — Data distribution
vendor/hpx/libs/full/parcelports/     — Network transports
```
