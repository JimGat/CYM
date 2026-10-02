idf_component_register(
    SRCS "ClassicCYDgpsTest.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_driver_uart esp_driver_gpio esp_driver_spi esp_timer esp_lcd espressif__esp_lcd_ili9341
)
