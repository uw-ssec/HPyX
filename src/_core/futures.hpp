#pragma once

#include <nanobind/nanobind.h>
#include <hpx/future.hpp>

#include <atomic>
#include <memory>
#include <optional>
#include <string>

// Forward-declare PyObject to avoid including Python.h here.
struct _object;
typedef struct _object PyObject;

namespace hpyx::futures {

// GIL-safe deleter for PyObject* — acquires the interpreter attach before
// Py_DECREF so shared_ptr destructors running on HPX worker threads are safe.
struct GILDecref {
    void operator()(PyObject* p) const noexcept;
};

// The future payload is a GIL-safe shared_ptr<PyObject> so that HPX can
// copy/move the value through its shared-state machinery without holding the
// Python GIL. The Python object is only unwrapped (ref-counted) when Python
// code calls result() / exception() with the GIL held.
//
// Storing nb::object directly in the future state is unsafe because nb::object's
// destructor calls Py_DECREF unconditionally; HPX can run that destructor on a
// worker thread that does not hold the GIL.
using PyPayload = std::shared_ptr<PyObject>;

// Wraps hpx::shared_future<PyPayload> so multiple consumers (then(),
// add_done_callback, __await__) share the same underlying future.
class HPXFuture {
  public:
    HPXFuture() = default;
    explicit HPXFuture(hpx::shared_future<PyPayload> fut);
    HPXFuture(const HPXFuture&) = default;
    HPXFuture(HPXFuture&&) = default;
    HPXFuture& operator=(const HPXFuture&) = default;
    HPXFuture& operator=(HPXFuture&&) = default;

    // concurrent.futures.Future-compatible methods
    nanobind::object result(std::optional<double> timeout = std::nullopt);
    nanobind::object exception(std::optional<double> timeout = std::nullopt);
    bool done() const;
    bool running() const;
    bool cancelled() const;
    bool cancel();
    void add_done_callback(nanobind::callable cb);

    // HPX-native extensions
    HPXFuture then(nanobind::callable cb);
    HPXFuture share() const;  // no-op; already shared

    // Internal use only
    hpx::shared_future<PyPayload> const& raw() const { return fut_; }

  private:
    hpx::shared_future<PyPayload> fut_;
    std::shared_ptr<std::atomic<bool>> cancelled_{
        std::make_shared<std::atomic<bool>>(false)};
    std::shared_ptr<std::atomic<bool>> running_{
        std::make_shared<std::atomic<bool>>(false)};
};

void register_bindings(nanobind::module_& m);

}  // namespace hpyx::futures
