cmake_minimum_required(VERSION 3.15)
project(minecraft_core)

set(CMAKE_CXX_STANDARD 17)

find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(minecraft_core
    src/bindings.cpp
    src/subchunk.cpp
    src/chunk.cpp
    src/fluid_simulator.cpp
    src/world.cpp
)

target_include_directories(minecraft_core PRIVATE include)
target_compile_definitions(minecraft_core PRIVATE VERSION_INFO="1.0.0")