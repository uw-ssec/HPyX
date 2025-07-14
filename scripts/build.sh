#!/usr/bin/env bash
# This file is based on the conda-forge build script for HPX.
# See https://github.com/conda-forge/hpx-feedstock/blob/main/recipe/build.sh
set -e

BUILD_DIR="build"

if [ -d "$BUILD_DIR" ]; then
  echo "$BUILD_DIR exists."
  rm -rf "$BUILD_DIR"
fi

if [ ! -d "$BUILD_DIR" ]; then
  echo "$BUILD_DIR does not exist."
  mkdir build
fi

pushd $BUILD_DIR

if [[ "$target_platform" == "osx-64" ]]; then
    # https://conda-forge.org/docs/maintainer/knowledge_base.html#newer-c-features-with-old-sdk
    export CXXFLAGS="${CXXFLAGS} -D_LIBCPP_DISABLE_AVAILABILITY"
fi

cmake \
    -G"Ninja" \
    ${CMAKE_ARGS} \
    -D CMAKE_INSTALL_PREFIX="$CONDA_PREFIX" \
    -D CMAKE_INSTALL_LIBDIR=lib \
    -D PYTHON_EXECUTABLE="$PYTHON" \
    -D HPX_WITH_EXAMPLES=FALSE \
    -D HPX_WITH_MALLOC="system" \
    -D HPX_WITH_NETWORKING=FALSE \
    -D HPX_WITH_TESTS=FALSE \
    ..
cmake --build . --config Release --parallel ${CPU_COUNT}
cmake --install .
