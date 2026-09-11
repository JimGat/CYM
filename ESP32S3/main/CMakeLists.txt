idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_driver_gpio
        esp_driver_i2c
        esp_driver_ledc
        esp_driver_spi
        esp_driver_sdspi
        esp_driver_sdmmc
        esp_lcd
        esp_timer
        freertos
        log
        nvs_flash
        esp_wifi
        bt
        esp_lcd_st77922
        fatfs
        sdmmc
        lvgl
)
