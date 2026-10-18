# Generate a pinned replacement TU; the component's original headers/config stay intact.
idf_component_get_property(cym_mdns_lib espressif__mdns COMPONENT_LIB)
idf_component_get_property(cym_mdns_dir espressif__mdns COMPONENT_DIR)
set(cym_mdns_overlay "${CMAKE_BINARY_DIR}/cym-mdns")
execute_process(COMMAND python "${CMAKE_CURRENT_LIST_DIR}/mdns-overlay.py"
    "${cym_mdns_dir}" "${cym_mdns_overlay}" RESULT_VARIABLE cym_mdns_result)
if(NOT cym_mdns_result EQUAL 0)
    message(FATAL_ERROR "Pinned mDNS lifecycle overlay failed")
endif()
get_target_property(cym_mdns_sources ${cym_mdns_lib} SOURCES)
list(FILTER cym_mdns_sources EXCLUDE REGEX "(^|/)(mdns_service|mdns_responder|mdns_mem_caps)\.c$")
list(APPEND cym_mdns_sources "${cym_mdns_overlay}/mdns_service.c" "${cym_mdns_overlay}/mdns_responder.c" "${cym_mdns_overlay}/mdns_mem_caps.c")
set_property(TARGET ${cym_mdns_lib} PROPERTY SOURCES "${cym_mdns_sources}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_LIST_DIR}/../patches/mdns/service-lifecycle.patch"
    "${CMAKE_CURRENT_LIST_DIR}/../patches/mdns/upstream.json"
    "${CMAKE_CURRENT_LIST_DIR}/../patches/mdns/responder-safety.patch"
    "${CMAKE_CURRENT_LIST_DIR}/../patches/mdns/memory-boundaries.patch"
    "${CMAKE_CURRENT_LIST_DIR}/../patches/mdns/cym_mdns_diag.h"
    "${CMAKE_CURRENT_LIST_DIR}/mdns-overlay.py")
