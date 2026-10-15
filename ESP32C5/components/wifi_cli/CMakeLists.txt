idf_component_register(
    SRCS "wifi_common.c" "wifi_cli.c" "classic_rgb_led.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_wifi nvs_flash esp_event esp_netif console led_strip wifi_scanner wifi_sniffer wifi_attacks wifi_wardrive board_hal esp_driver_ledc esp_driver_gpio
)

