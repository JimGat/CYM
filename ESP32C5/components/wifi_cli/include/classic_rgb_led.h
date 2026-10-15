#pragma once
#include "led_strip.h"
// Static, allocation-free Classic/HackerBox active-low RGB backend.
esp_err_t classic_rgb_led_init(led_strip_handle_t *out);
