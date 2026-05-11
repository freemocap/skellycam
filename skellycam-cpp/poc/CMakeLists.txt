cmake_minimum_required(VERSION 3.16)
project(skellycam_poc VERSION 0.1.0 LANGUAGES CXX)

# C++17 — the broadly-supported modern standard.
# Not C++20/23 because OpenCV pre-built binaries often target C++17.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Find OpenCV — REQUIRED means the build will fail with a clear message
# if OpenCV is not installed, instead of a cryptic linker error later.
find_package(OpenCV REQUIRED)

add_executable(skellycam_poc main.cpp)
target_link_libraries(skellycam_poc PRIVATE ${OpenCV_LIBS})
target_include_directories(skellycam_poc PRIVATE ${OpenCV_INCLUDE_DIRS})

add_executable(fourcc_diag fourcc_diag.cpp)
target_link_libraries(fourcc_diag PRIVATE ${OpenCV_LIBS})
target_include_directories(fourcc_diag PRIVATE ${OpenCV_INCLUDE_DIRS})
