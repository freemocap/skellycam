cmake_minimum_required(VERSION 3.16)
project(skellycam_multicam VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(OpenCV REQUIRED)
find_package(Threads REQUIRED)

add_executable(skellycam_multicam main.cpp)

target_link_libraries(skellycam_multicam PRIVATE ${OpenCV_LIBS} Threads::Threads)
target_include_directories(skellycam_multicam PRIVATE ${OpenCV_INCLUDE_DIRS})
