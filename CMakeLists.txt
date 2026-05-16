cmake_minimum_required(VERSION 3.20)
project(vexilloscope C)

set(CMAKE_C_STANDARD 11)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# ── otto-von-grad dependency ────────────────────────────────────────────────
# Local development: both repos checked out side-by-side under the same parent.
# To use a remote URL instead, replace the block below with FetchContent:
#
#   include(FetchContent)
#   FetchContent_Declare(ottovongrad
#       GIT_REPOSITORY https://github.com/YOU/otto-von-grad.git
#       GIT_TAG        main
#   )
#   FetchContent_MakeAvailable(ottovongrad)
#
if(NOT TARGET ottovongrad)
    add_subdirectory("${CMAKE_CURRENT_LIST_DIR}/../otto-von-grad"
                     "${CMAKE_CURRENT_BINARY_DIR}/otto-von-grad")
endif()

# ── vexilloscope executable ─────────────────────────────────────────────────
add_executable(vexilloscope
    src/main.c
    src/img.c
    src/dataset.c
    src/mlp_classifier.c
    src/patch_embedding.c
    src/vit.c
)

target_include_directories(vexilloscope PRIVATE
    src
    vendor
)

target_link_libraries(vexilloscope PRIVATE ottovongrad)

if(OVG_CUDA)
    add_executable(cuda_smoke src/cuda_smoke.c)
    target_include_directories(cuda_smoke PRIVATE src)
    target_link_libraries(cuda_smoke PRIVATE ottovongrad)
endif()
