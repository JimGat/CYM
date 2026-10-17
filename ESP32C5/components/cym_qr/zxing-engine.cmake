# Same reusable adapter/native/IDF engine. Scoped copied archives only.
include("${CMAKE_CURRENT_LIST_DIR}/zxing-options.cmake")
add_subdirectory("${CMAKE_CURRENT_LIST_DIR}/third_party/zxing-cpp/core" "${CMAKE_CURRENT_BINARY_DIR}/zxing")
set_target_properties(ZXing PROPERTIES POSITION_INDEPENDENT_CODE OFF CXX_STANDARD 20)
if(ESP_PLATFORM)
 # IDF injects common component links directory-wide. Engine is a private
 # archive, never installed/exported with IDF component dependencies.
 set_property(TARGET ZXing PROPERTY LINK_LIBRARIES "")
 set_property(TARGET ZXing PROPERTY INTERFACE_LINK_LIBRARIES "")
endif()
add_library(cym_zx_adapter_raw STATIC "${CMAKE_CURRENT_LIST_DIR}/cym_qr_zxing.cpp")
target_include_directories(cym_zx_adapter_raw PUBLIC "${CMAKE_CURRENT_LIST_DIR}/include")
target_link_libraries(cym_zx_adapter_raw PRIVATE ZXing)
foreach(t ZXing cym_zx_adapter_raw)
 target_compile_options(${t} PRIVATE "$<$<COMPILE_LANGUAGE:CXX>:-std=gnu++20;-fexceptions;-fno-rtti>" -ffunction-sections -fdata-sections -Wno-error=undef)
 set(bound "${CMAKE_CURRENT_BINARY_DIR}/lib${t}_bound.a")
 add_custom_command(OUTPUT "${bound}"
  COMMAND "${CMAKE_COMMAND}" -E copy "$<TARGET_FILE:${t}>" "${bound}"
  COMMAND python3 "${CMAKE_CURRENT_LIST_DIR}/rebind_archive.py" "${CMAKE_OBJCOPY}" "${CMAKE_NM}" "${CMAKE_CURRENT_LIST_DIR}/rebind-symbols.txt" "${bound}" "$<TARGET_FILE:ZXing>" "$<TARGET_FILE:cym_zx_adapter_raw>"
  DEPENDS ZXing cym_zx_adapter_raw "${CMAKE_CURRENT_LIST_DIR}/rebind-symbols.txt" "${CMAKE_CURRENT_LIST_DIR}/rebind_archive.py" VERBATIM)
 add_custom_target(${t}_rebind DEPENDS "${bound}")
 add_library(${t}_bound STATIC IMPORTED GLOBAL)
 set_target_properties(${t}_bound PROPERTIES IMPORTED_LOCATION "${bound}")
 add_dependencies(${t}_bound ${t}_rebind)
endforeach()
add_library(cym_zx_adapter INTERFACE)
target_include_directories(cym_zx_adapter INTERFACE "${CMAKE_CURRENT_LIST_DIR}/include")
target_link_libraries(cym_zx_adapter INTERFACE cym_zx_adapter_raw_bound ZXing_bound)
