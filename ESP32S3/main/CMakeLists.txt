# ESP32-S3 main component — canonical CYM sources from ESP32C5/main/ plus the
# narrow ES3C35P display/touch transport adapter. No S3 application fork.
set(C5_MAIN "${CMAKE_CURRENT_SOURCE_DIR}/../../ESP32C5/main")

idf_component_register(
    SRCS
        "${C5_MAIN}/attack_handshake.c"
        "${C5_MAIN}/xpt2046.c"
        "${C5_MAIN}/lvgl_memory.c"
        "${C5_MAIN}/main.c"
        "${C5_MAIN}/dexter_img.c"
        "${C5_MAIN}/lv_extra_symbols.c"
        "${C5_MAIN}/lab_bg.c"
        "${C5_MAIN}/deedee_img.c"
        "${C5_MAIN}/bt_lookout.c"
        "${C5_MAIN}/oui_lookup.c"
        "${C5_MAIN}/gatt_walker.c"
        "${C5_MAIN}/ble_honeypair.c"
        "${C5_MAIN}/ble_blueduck.c"
        "${C5_MAIN}/ble_whisperpair.c"
        "${C5_MAIN}/sd_error_handler.c"
        "${C5_MAIN}/chameleon_ble.c"
        "hosyond_s3_35_port.c"
    INCLUDE_DIRS
        "${C5_MAIN}"
        "."
    REQUIRES
        heap driver esp_event console bt esp_adc esp-tls esp_http_server esp_wifi
        board_hal esp_lcd_st77922 esp_lcd esp_timer freertos log nvs_flash fatfs
        sdmmc lvgl led_strip
    PRIV_REQUIRES
        wifi_attacks wifi_cli wifi_scanner wifi_sniffer wifi_wardrive sniffer
        frame_analyzer hccapx_serializer pcap_serializer esp_driver_ledc
        esp_driver_gpio esp_driver_i2c esp_driver_spi esp_driver_sdspi
        esp_driver_sdmmc rf_hat rfid cc1101 nrf24 obs_store obs_detectors ot_survey
    EMBED_TXTFILES
        "${C5_MAIN}/gts_root_r4.pem"
)

# size_t format details differ across Xtensa and RISC-V targets.
target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-error=format)
