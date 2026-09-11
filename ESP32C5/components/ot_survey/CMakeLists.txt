idf_component_register(
    SRCS "ot_survey.c" "ot_radio.c" "pcapng.c" "wh_detect.c"
    INCLUDE_DIRS "include"
    PRIV_REQUIRES esp_common esp_timer nvs_flash fatfs obs_store board_hal
)
