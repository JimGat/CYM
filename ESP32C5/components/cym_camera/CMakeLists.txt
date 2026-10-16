set(camera_sources)
if(CONFIG_BOARD_WS_C5_35)
    set(camera_sources "cym_camera.c" "camera_packet.c" "camera_ws_c5_35.c")
endif()
idf_component_register(SRCS ${camera_sources} INCLUDE_DIRS "include"
    PRIV_INCLUDE_DIRS "." "vendor" REQUIRES heap)
if(CONFIG_BOARD_WS_C5_35)
    # REQUIRES is expanded before board Kconfig is loaded. Link SDK targets
    # here, after registration, so includes/dependencies are WS35-scoped.
    target_link_libraries(${COMPONENT_LIB} PRIVATE idf::esp_driver_i2c
        idf::esp_driver_parlio idf::esp_driver_gpio idf::esp_timer idf::esp_mm)
    target_link_options(${COMPONENT_LIB} INTERFACE "LINKER:--wrap=parlio_new_tx_unit" "LINKER:--wrap=parlio_del_tx_unit")
endif()
