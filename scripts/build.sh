#!/usr/bin/env bash
# This file is based on the conda-forge build script for HPX.
# See https://github.com/conda-forge/hpx-feedstock/blob/main/recipe/build.sh
set -e

# Set default values
MALLOC="system"
BUILD_DIR="build"
HPX_VERSION=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --malloc)
      MALLOC="$2"
      shift 2
      ;;
    --build-dir)
      BUILD_DIR="$2"
      shift 2
      ;;
    --hpx-version)
      HPX_VERSION="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--malloc TYPE] [--build-dir DIR] --hpx-version VERSION"
      echo "  --malloc TYPE        Set malloc implementation (default: system)"
      echo "  --build-dir DIR      Set build directory (default: build)"
      echo "  --hpx-version VERSION Set HPX version to build from source (required)"
      echo "  -h, --help           Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option $1"
      echo "Usage: $0 [--malloc TYPE] [--build-dir DIR] --hpx-version VERSION"
      echo "Use --help for more information"
      exit 1
      ;;
  esac
done

# Check if HPX_VERSION is required and provided
if [ -z "$HPX_VERSION" ]; then
  echo "Error: HPX version must be specified with --hpx-version"
  echo "Usage: $0 [--malloc TYPE] [--build-dir DIR] --hpx-version VERSION"
  exit 1
fi

if [ -n "$HPX_VERSION" ]; then
  echo "Building HPX Version: $HPX_VERSION"
fi
echo "Building with memory allocator: $MALLOC"
echo "Using build directory: $BUILD_DIR"

git checkout "$HPX_VERSION" || {
  echo "Error: HPX version $HPX_VERSION not found in the repository."
  exit 1
}

if [ -d "$BUILD_DIR" ]; then
  echo "$BUILD_DIR exists."
  rm -rf "$BUILD_DIR"
fi

if [ ! -d "$BUILD_DIR" ]; then
  echo "$BUILD_DIR does not exist."
  mkdir "$BUILD_DIR"
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
    -D HPX_WITH_MALLOC="$MALLOC" \
    -D HPX_WITH_NETWORKING=FALSE \
    -D HPX_WITH_TESTS=FALSE \
    ..
cmake --build . --config Release --parallel ${CPU_COUNT}
cmake --install .
