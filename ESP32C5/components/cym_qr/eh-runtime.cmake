# Task-local copy of ONE libsupc++ member. Preserve exception/TLS/guard ABI.
# Never rewrite the installed toolchain and never wrap application malloc.
# The driver print-file-name lookup ignores the picolibc specs search order.
# Use CMake actual-link implicit directories, including target ABI/no-rtti.
find_library(cym_stdlib NAMES stdc++ PATHS ${CMAKE_CXX_IMPLICIT_LINK_DIRECTORIES}
 NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH REQUIRED)
set(cym_eh_obj "${CMAKE_CURRENT_BINARY_DIR}/eh_alloc_psram.o")
set(cym_eh_lib "${CMAKE_CURRENT_BINARY_DIR}/libcym_eh_psram.a")
add_custom_command(OUTPUT "${cym_eh_lib}"
 COMMAND python3 "${CMAKE_CURRENT_LIST_DIR}/copy_eh_runtime.py"
  "${CMAKE_AR}" "${CMAKE_OBJCOPY}" "${cym_stdlib}" "${cym_eh_obj}" "${cym_eh_lib}"
 DEPENDS "${CMAKE_CURRENT_LIST_DIR}/copy_eh_runtime.py" "${cym_stdlib}" VERBATIM)
add_custom_target(cym_eh_copy DEPENDS "${cym_eh_lib}")
add_library(cym_eh_psram STATIC IMPORTED GLOBAL)
set_target_properties(cym_eh_psram PROPERTIES IMPORTED_LOCATION "${cym_eh_lib}")
add_dependencies(cym_eh_psram cym_eh_copy)
target_link_libraries(${COMPONENT_LIB} PRIVATE cym_eh_psram)

# IDF supplies -lstdc++ before the rescan group; explicit whole-member placement
# must precede that search. Linking an ordinary archive in the group is too late.
target_link_options(${COMPONENT_LIB} INTERFACE "-Wl,--whole-archive,${cym_eh_lib},--no-whole-archive")
