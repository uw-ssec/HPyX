#include <hpx/hpx.hpp>
#include <hpx/hpx_start.hpp>

#include "init_hpx.hpp"
#include <nanobind/nanobind.h>

#include <cstddef>
#include <mutex>
#include <string>
#include <vector>

namespace nb = nanobind;

struct global_runtime_manager
{
    global_runtime_manager(std::vector<std::string> const &config)
        : running_(false), rts_(nullptr), cfg(config)
    {
        hpx::init_params params;
        params.cfg = cfg;

        hpx::function<int(int, char **)> start_function =
            hpx::bind_front(&global_runtime_manager::hpx_main, this);

        if (!hpx::start(start_function, 0, nullptr, params))
        {
            std::abort(); // Failed to initialize runtime
        }

        // Wait for the main HPX thread to start
        std::unique_lock<std::mutex> lk(startup_mtx_);
        while (!running_)
            startup_cond_.wait(lk);
    }

    ~global_runtime_manager()
    {
        {
            std::lock_guard<hpx::spinlock> lk(mtx_);
            rts_ = nullptr;
        }

        cond_.notify_one();
        hpx::stop(); // Stop the runtime
    }

    int hpx_main(int argc, char *argv[])
    {
        rts_ = hpx::get_runtime_ptr();

        {
            std::lock_guard<std::mutex> lk(startup_mtx_);
            running_ = true;
        }

        startup_cond_.notify_one();

        // Wait for the destructor to signal exit
        {
            std::unique_lock<hpx::spinlock> lk(mtx_);
            if (rts_ != nullptr)
                cond_.wait(lk);
        }

        return hpx::finalize(); // Allow runtime to exit
    }

private:
    hpx::spinlock mtx_;
    hpx::condition_variable_any cond_;

    std::mutex startup_mtx_;
    std::condition_variable startup_cond_;
    bool running_;

    hpx::runtime *rts_;
    std::vector<std::string> const cfg;
};

global_runtime_manager *rts = nullptr;

void init_hpx_runtime(std::vector<std::string> const &cfg)
{
    if (rts == nullptr)
    {
        nb::gil_scoped_acquire acquire;
        rts = new global_runtime_manager(cfg);
    }
}

void stop_hpx_runtime()
{
    global_runtime_manager *r = rts;
    rts = nullptr;
    if (r != nullptr)
    {
        // Release GIL during HPX runtime shutdown
        nb::gil_scoped_release release;
        delete r;
    }
}
