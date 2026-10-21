cmake_minimum_required(VERSION 3.16)
project(Project360 CXX)

# Path to the Nuke install, e.g. "C:/Program Files/Nuke15.1v3" or /usr/local/Nuke15.1v3.
# It must contain include/DDImage and DDImage.lib (Windows) / libDDImage.so (Linux) / libDDImage.dylib (macOS).
set(NUKE_ROOT "" CACHE PATH "Nuke install directory")
if(NOT NUKE_ROOT OR NOT EXISTS "${NUKE_ROOT}/include/DDImage/Iop.h")
  message(FATAL_ERROR "Set -DNUKE_ROOT=<Nuke install directory> (must contain include/DDImage/Iop.h)")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_library(DDIMAGE_LIBRARY NAMES DDImage PATHS "${NUKE_ROOT}" NO_DEFAULT_PATH REQUIRED)

add_library(Project360 MODULE Project360.cpp)
target_include_directories(Project360 PRIVATE "${NUKE_ROOT}/include" "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(Project360 PRIVATE "${DDIMAGE_LIBRARY}")
set_target_properties(Project360 PROPERTIES PREFIX "")

if(WIN32)
  target_compile_definitions(Project360 PRIVATE _USE_MATH_DEFINES NOMINMAX)
  set_target_properties(Project360 PROPERTIES SUFFIX ".dll")
elseif(APPLE)
  set_target_properties(Project360 PROPERTIES SUFFIX ".dylib")
else()
  # Nuke 14 and older are built with the old libstdc++ ABI; pass -DNUKE_OLD_ABI=OFF for Nuke 15+.
  option(NUKE_OLD_ABI "Build with _GLIBCXX_USE_CXX11_ABI=0 (Nuke 14 and older)" ON)
  if(NUKE_OLD_ABI)
    target_compile_definitions(Project360 PRIVATE _GLIBCXX_USE_CXX11_ABI=0)
  endif()
  target_compile_options(Project360 PRIVATE -fPIC)
endif()
