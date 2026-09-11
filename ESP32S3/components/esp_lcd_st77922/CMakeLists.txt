idf_component_register(
    SRCS
        "esp_lcd_st77922.c"
        "esp_lcd_touch.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_lcd
        esp_timer
        freertos
        log
)
