# Specify the minimum CMake version and compatibility range.
cmake_minimum_required(VERSION 3.15...3.29)

# Define the project using variables provided by SKBUILD.
project(
  ${SKBUILD_PROJECT_NAME}
  VERSION ${SKBUILD_PROJECT_VERSION}
  LANGUAGES C CXX
)

# Warn if the user invokes CMake directly
if (NOT SKBUILD)
  message(WARNING "\
  This CMake file is meant to be executed using 'scikit-build-core'.
  Running it directly will almost certainly not produce the desired
  result. If you are a user trying to install this package, use the
  command below, which will install all necessary build dependencies,
  compile the package in an isolated environment, and then install it.
  =====================================================================
   $ pip install .
  =====================================================================
  If you are a software developer, and this is your own package, then
  it is usually much more efficient to install the build dependencies
  in your environment once and use the following command that avoids
  a costly creation of a new virtual environment at every compilation:
  =====================================================================
   $ pip install nanobind scikit-build-core[pyproject]
   $ pip install --no-build-isolation -ve .
  =====================================================================
  You may optionally add -Ceditable.rebuild=true to auto-rebuild when
  the package is imported. Otherwise, you need to rerun the above
  after editing C++ files.")
endif()

if (CMAKE_VERSION VERSION_LESS 3.29)
  set(DEV_MODULE Development)
else()
  set(DEV_MODULE Development.Module)
endif()

###############################################################################
# Set C++17 as the required standard
###############################################################################
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

###############################################################################
# Locate Python and nanobind
###############################################################################
# Find Python interpreter, development headers, and library.
find_package(Python 3.13 COMPONENTS Interpreter ${DEV_MODULE} REQUIRED)

if (NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose the type of build." FORCE)
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "MinSizeRel" "RelWithDebInfo")
endif()

# Detect the installed nanobind package and import it into CMake
execute_process(
  COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
  OUTPUT_STRIP_TRAILING_WHITESPACE OUTPUT_VARIABLE nanobind_ROOT)
find_package(nanobind CONFIG REQUIRED)

# Find HPX
find_package(HPX REQUIRED)

###############################################################################
# Configure RPATH for non-Windows platforms
###############################################################################
if(NOT WIN32)
  # Set the install RPATH to the directory containing the executable/library.
  set(CMAKE_INSTALL_RPATH "$ORIGIN")
  set(CMAKE_BUILD_WITH_INSTALL_RPATH TRUE)
endif()

###############################################################################
# Build the Python module (_core) and other targets
###############################################################################
# Add dynamic lookup for macOS to resolve Python symbols at runtime.
if(APPLE)
  set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -undefined dynamic_lookup")
endif()

# Create the Python module from the source file
nanobind_add_module(
  _core
  FREE_THREADED
  src/bind.cpp
  src/init_hpx.cpp
  src/algorithms.cpp
  src/futures.cpp
)

# TODO: Add new modules here, maybe even HPX modules?
# # Define a list of targets to link against the required libraries.
# set(HPYX_TARGETS module1 module2 ...)

# foreach(TARGET ${HPYX_TARGETS})
#   # Create a library for each target.
#   file(GLOB SOURCES src/${TARGET}/*.cpp)
#   nanobind_add_module(${TARGET} FREE_THREADED ${SOURCES})
# endforeach()

# Loop through the targets and link them against the required libraries.
foreach(TARGET ${HPYX_TARGETS} _core)
  target_link_libraries(${TARGET} PRIVATE
    HPX::hpx
    HPX::wrap_main
    HPX::iostreams_component
  )
endforeach()

# Pass the project version as a preprocessor definition.
target_compile_definitions(_core PRIVATE VERSION_INFO=${PROJECT_VERSION})

###############################################################################
# Installation configuration
###############################################################################
message(STATUS "Project version: ${PROJECT_VERSION}")

# Install the _core module into the hpyx directory.
install(TARGETS _core LIBRARY DESTINATION ${SKBUILD_PROJECT_NAME})
