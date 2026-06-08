cmake_minimum_required(VERSION 3.24)
project(cx_vision_runtime LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(cx_vision_runtime
    src/main.cpp
    src/runtime_contracts.cpp
)

target_include_directories(cx_vision_runtime PRIVATE include)

# Static link to avoid runtime DLL dependencies (libunwind, libc++, etc.)
if(MINGW)
    target_link_options(cx_vision_runtime PRIVATE -static)
endif()
