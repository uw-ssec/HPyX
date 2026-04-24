#include "runtime.hpp"

#include <hpx/hpx.hpp>
#include <hpx/hpx_start.hpp>
#include <hpx/version.hpp>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::runtime {

namespace {

struct global_runtime_manager {
    global_runtime_manager(std::vector<std::string> const& config)
        : running_(false), rts_(nullptr), cfg(config) {
        hpx::init_params params;
        params.cfg = cfg;

        hpx::function<int(int, char**)> start_function =
            hpx::bind_front(&global_runtime_manager::hpx_main, this);

        if (!hpx::start(start_function, 0, nullptr, params)) {
            std::abort();
        }

        std::unique_lock<std::mutex> lk(startup_mtx_);
        while (!running_) startup_cond_.wait(lk);
    }

    ~global_runtime_manager() {
        {
            std::lock_guard<hpx::spinlock> lk(mtx_);
            rts_ = nullptr;
        }
        cond_.notify_one();
        hpx::stop();
    }

    int hpx_main(int /*argc*/, char** /*argv*/) {
        rts_ = hpx::get_runtime_ptr();
        {
            std::lock_guard<std::mutex> lk(startup_mtx_);
            running_ = true;
        }
        startup_cond_.notify_one();
        {
            std::unique_lock<hpx::spinlock> lk(mtx_);
            if (rts_ != nullptr) cond_.wait(lk);
        }
        return hpx::finalize();
    }

  private:
    hpx::spinlock mtx_;
    hpx::condition_variable_any cond_;
    std::mutex startup_mtx_;
    std::condition_variable startup_cond_;
    bool running_;
    hpx::runtime* rts_;
    std::vector<std::string> const cfg;
};

std::mutex g_state_mtx;
global_runtime_manager* g_mgr = nullptr;
std::atomic<bool> g_stopped{false};

}  // namespace

bool runtime_start(std::vector<std::string> const& cfg) {
    if (g_stopped.load()) {
        throw std::runtime_error(
            "HPyX runtime has been stopped and cannot restart within this process");
    }
    std::lock_guard<std::mutex> lk(g_state_mtx);
    if (g_mgr != nullptr) return false;

    nb::gil_scoped_release release;
    g_mgr = new global_runtime_manager(cfg);
    return true;
}

void runtime_stop() {
    global_runtime_manager* to_delete = nullptr;
    {
        std::lock_guard<std::mutex> lk(g_state_mtx);
        to_delete = g_mgr;
        g_mgr = nullptr;
    }
    if (to_delete != nullptr) {
        g_stopped.store(true);
        nb::gil_scoped_release release;
        delete to_delete;
    }
}

bool runtime_is_running() {
    std::lock_guard<std::mutex> lk(g_state_mtx);
    return g_mgr != nullptr;
}

std::size_t num_worker_threads() {
    if (!runtime_is_running()) return 0;
    return hpx::get_num_worker_threads();
}

std::int64_t get_worker_thread_id() {
    if (!runtime_is_running()) return -1;
    auto id = hpx::get_worker_thread_num();
    if (id == std::size_t(-1)) return -1;
    return static_cast<std::int64_t>(id);
}

std::string hpx_version_string() {
    return hpx::complete_version();
}

void register_bindings(nb::module_& m) {
    m.def("runtime_start", &runtime_start, "cfg"_a,
          "Start the HPX runtime. Idempotent; returns True if this call started it.");
    m.def("runtime_stop", &runtime_stop,
          "Stop the HPX runtime. Irreversible within this process.");
    m.def("runtime_is_running", &runtime_is_running);
    m.def("num_worker_threads", &num_worker_threads);
    m.def("get_worker_thread_id", &get_worker_thread_id);
    m.def("hpx_version_string", &hpx_version_string);
}

}  // namespace hpyx::runtime
