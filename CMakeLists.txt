cmake_minimum_required(VERSION 3.12)

# Set the project name
project(EvolveCacheSim)

# #######################################
# find dependency #
# #######################################
set(LIBCACHE_SIM_DIR "${CMAKE_SOURCE_DIR}/libcachesim")
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${LIBCACHE_SIM_DIR}/cmake/Modules/")

set(CMAKE_BUILD_TYPE Debug)

# Find GLib using pkg-config
find_package(GLib "2.40" REQUIRED)
include_directories(${GLib_INCLUDE_DIRS})
message(STATUS "glib found? ${GLib_FOUND}, lib = ${GLib_LIBRARY}, header = ${GLib_INCLUDE_DIRS}")

find_package(ZSTD)
# https://stackoverflow.com/questions/61377055/cannot-find-gflags-gflags-h-while-building-library-osx/61379123#61379123
include_directories(${ZSTD_INCLUDE_DIR})
if ("${ZSTD_LIBRARIES}" STREQUAL "") 
    message(FATAL_ERROR "zstd not found")
endif()

# Include libcachesim headers
include_directories(libcachesim)

# Add the subdirectory containing libcachesim
add_subdirectory(libcachesim)

# The main executable to run

add_executable(run_algos.o run_algos.cpp)
target_link_libraries(run_algos.o libCacheSim m ${GLib_LIBRARY} ${ZSTD_LIBRARIES})

add_custom_target(run_install_libcachesim
    COMMAND ${CMAKE_COMMAND} -E echo "Running install_libcachesim.sh"
    COMMAND bash ${CMAKE_SOURCE_DIR}/libcachesim/scripts/install_libcachesim.sh
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
)