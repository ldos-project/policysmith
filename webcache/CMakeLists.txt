cmake_minimum_required(VERSION 3.12)

# Set the project name
project(EvolveCacheSim)

# #######################################
# find dependency #
# #######################################
set(LIBCACHE_SIM_DIR "${CMAKE_SOURCE_DIR}/libCacheSim")
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

# Include libCacheSim headers
include_directories(libCacheSim)

# Add the subdirectory containing libCacheSim
add_subdirectory(libCacheSim)

# The main executable to run
add_executable(run_multiple_sizes.o run_multiple_sizes.cpp)
target_link_libraries(run_multiple_sizes.o libCacheSim m ${GLib_LIBRARY} ${ZSTD_LIBRARIES})

add_executable(run_multiple_algos.o run_multiple_algos.cpp)
target_link_libraries(run_multiple_algos.o libCacheSim m ${GLib_LIBRARY} ${ZSTD_LIBRARIES})

add_executable(eval_final_heuristic.o eval_final_heuristic.cpp)
target_link_libraries(eval_final_heuristic.o libCacheSim m ${GLib_LIBRARY} ${ZSTD_LIBRARIES})

add_executable(get_footprint.o get_footprint.cpp)
target_link_libraries(get_footprint.o libCacheSim m ${GLib_LIBRARY} ${ZSTD_LIBRARIES})

add_custom_target(run_install_libcachesim
    COMMAND ${CMAKE_COMMAND} -E echo "Running install_libcachesim.sh"
    COMMAND bash ${CMAKE_SOURCE_DIR}/libCacheSim/scripts/install_libcachesim.sh
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
)
add_dependencies(run_multiple_sizes.o run_install_libcachesim)