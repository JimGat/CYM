idf_component_register(SRCS "WS28AudioDiag.c" "diag_core.c" INCLUDE_DIRS "."
 REQUIRES esp_driver_i2c esp_driver_i2s esp_driver_gpio esp_timer freertos esp_codec_dev vfs esp_driver_usb_serial_jtag)
