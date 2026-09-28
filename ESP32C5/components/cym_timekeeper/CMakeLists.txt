idf_component_register(
    SRCS "cym_timekeeper.c" "pcf85063.c" "cym_ntp_server.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_driver_i2c esp_timer nvs_flash board_hal
    PRIV_REQUIRES lwip esp_netif
)
