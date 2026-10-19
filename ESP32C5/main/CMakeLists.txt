idf_component_register(SRCS "debug_settings.c" "debug_console.c" "classic_usb_debug.c" "classic_usb_debug_uart.c" "fsd_console.c" "attack_handshake.c" "xpt2046.c" "pancake_c5_port.c" "pancake_ft6336.c" "ws_c5_35_port.c" "lvgl_memory.c" "main.c" "dexter_img.c" "lv_extra_symbols.c" "lab_bg.c" "deedee_img.c" "bt_lookout.c" "oui_lookup.c" "gatt_walker.c" "ble_honeypair.c" "ble_blueduck.c" "ble_whisperpair.c" "sd_error_handler.c" "chameleon_ble.c" "chameleon_t55xx.c" INCLUDE_DIRS . REQUIRES esp_driver_usb_serial_jtag mbedtls heap driver esp_event console bt esp_adc esp-tls esp_http_server esp_wifi ieee802154 board_hal esp_lcd_touch_cst3530 esp_lcd_touch_ft6336 custom_io_expander_ch32v003 esp_io_expander espressif__esp_lcd_ili9341 espressif__esp_lcd_st7796 PRIV_REQUIRES esp_netif wifi_attacks wifi_cli wifi_scanner wifi_sniffer wifi_wardrive sniffer frame_analyzer hccapx_serializer pcap_serializer esp_driver_ledc rf_hat rfid cc1101 nrf24 obs_store obs_detectors ot_survey cym_timekeeper EMBED_TXTFILES "gts_root_r4.pem")

# Disable format warning errors for ESP32-C5 (size_t is unsigned int, not long unsigned int)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-error=format)

# Private native game has no engine/UI source on other generated board configs.
if(CONFIG_BOARD_WS_C5_28 OR CONFIG_BOARD_WS_C5_35)
    idf_component_get_property(doom_lib cym_doom COMPONENT_LIB)
    target_link_libraries(${COMPONENT_LIB} PRIVATE ${doom_lib})
    target_include_directories(${COMPONENT_LIB} PRIVATE "${CMAKE_CURRENT_LIST_DIR}/../components/cym_doom/include")
endif()

# QR implementation and camera dependencies are WS35-only, not C5/PSRAM-wide.
if(CONFIG_BOARD_WS_C5_35)
    target_sources(${COMPONENT_LIB} PRIVATE "qr_decoder_ui.c")
    foreach(qr_component cym_camera cym_qr)
        idf_component_get_property(qr_lib ${qr_component} COMPONENT_LIB)
        target_link_libraries(${COMPONENT_LIB} PRIVATE ${qr_lib})
        target_include_directories(${COMPONENT_LIB} PRIVATE "${CMAKE_CURRENT_LIST_DIR}/../components/${qr_component}/include")
    endforeach()
endif()

# Narrow microphone analyzer: unsupported boards link no session/DSP/font object.
if(CONFIG_BOARD_WS_C5_35)
    target_sources(${COMPONENT_LIB} PRIVATE "audio_rta.c" "audio_rta_board.c" "audio_rta_dsp.c" "audio_rta_mic.c")
    idf_component_get_property(rta_codec_lib espressif__esp_codec_dev COMPONENT_LIB)
    target_link_libraries(${COMPONENT_LIB} PRIVATE ${rta_codec_lib})
endif()
