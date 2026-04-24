#pragma once

#include <nanobind/nanobind.h>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace hpyx::runtime {

// Thread-safe, idempotent. Returns true if this call started the runtime,
// false if it was already running. Throws std::runtime_error if the runtime
// was previously started and then stopped (HPX cannot restart in-process).
bool runtime_start(std::vector<std::string> const& cfg);

// Blocks until HPX drains. Idempotent — safe to call after a prior stop
// (no-op in that case). Does NOT re-enable starting.
void runtime_stop();

bool runtime_is_running();

std::size_t num_worker_threads();
std::int64_t get_worker_thread_id();  // -1 if called from a non-HPX OS thread
std::string hpx_version_string();

// Called by _core's NB_MODULE macro to register all bindings in this file
// on the `runtime` submodule.
void register_bindings(nanobind::module_& m);

}  // namespace hpyx::runtime
