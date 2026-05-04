#pragma once

#include <nanobind/nanobind.h>

#define HPYX_KERNEL_NOGIL \
    ::nanobind::gil_scoped_release _hpyx_gil_release_

#define HPYX_CALLBACK_GIL \
    ::nanobind::gil_scoped_acquire _hpyx_gil_acquire_
