#pragma once

#include <nanobind/nanobind.h>

#include <atomic>
#include <cstdint>
#include <string>

namespace hpyx::tracing {

struct TraceEvent {
    std::string name;
    std::int64_t worker_thread_id;
    std::int64_t start_ns;    // steady_clock nanoseconds since epoch
    std::int64_t duration_ns;
};

// Global enable flag — zero-cost when disabled (one atomic load).
extern std::atomic<bool> g_enabled;

inline bool is_enabled() { return g_enabled.load(std::memory_order_acquire); }

void record(TraceEvent event);

// Returns the current HPX worker thread id, or -1 if not on an HPX thread.
// Defined in tracing.cpp to avoid including heavy HPX headers in callers.
std::int64_t current_worker_thread_id();

void register_bindings(nanobind::module_& m);

}  // namespace hpyx::tracing
