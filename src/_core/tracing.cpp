#include "tracing.hpp"
#include "runtime.hpp"

#include <hpx/hpx.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <atomic>
#include <cstddef>
#include <mutex>
#include <vector>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::tracing {

std::atomic<bool> g_enabled{false};

namespace {
std::mutex g_mtx;
std::vector<TraceEvent> g_buffer;
}  // namespace

void record(TraceEvent event) {
    if (!is_enabled()) return;
    std::lock_guard<std::mutex> lk(g_mtx);
    g_buffer.push_back(std::move(event));
}

static void enable() {
    g_enabled.store(true, std::memory_order_release);
}

static void disable() {
    g_enabled.store(false, std::memory_order_release);
}

static std::vector<TraceEvent> drain() {
    std::vector<TraceEvent> out;
    std::lock_guard<std::mutex> lk(g_mtx);
    std::swap(out, g_buffer);
    return out;
}

std::int64_t current_worker_thread_id() {
    if (!hpyx::runtime::runtime_is_running()) return -1;
    auto id = hpx::get_worker_thread_num();
    if (id == std::size_t(-1)) return -1;
    return static_cast<std::int64_t>(id);
}

void register_bindings(nb::module_& m) {
    nb::class_<TraceEvent>(m, "TraceEvent")
        .def_ro("name", &TraceEvent::name)
        .def_ro("worker_thread_id", &TraceEvent::worker_thread_id)
        .def_ro("start_ns", &TraceEvent::start_ns)
        .def_ro("duration_ns", &TraceEvent::duration_ns);
    m.def("enable", &enable);
    m.def("disable", &disable);
    m.def("is_enabled", &is_enabled);
    m.def("drain", &drain);
}

}  // namespace hpyx::tracing
