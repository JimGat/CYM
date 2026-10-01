/*
 * SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

// FT6336 capacitive touch driver for esp_lcd_touch interface.
// Adapted from Waveshare ESP32-C5-Touch-LCD-3.5 BSP (commit
// 04e6134cf3e37309b2bec9915189efeace1161bc).

#pragma once

#include "esp_lcd_touch.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t esp_lcd_touch_new_i2c_ft6336(const esp_lcd_panel_io_handle_t io,
                                        const esp_lcd_touch_config_t *config,
                                        esp_lcd_touch_handle_t *out_touch);

#define ESP_LCD_TOUCH_IO_I2C_FT6336_ADDRESS (0x38)

#define ESP_LCD_TOUCH_IO_I2C_FT6336_CONFIG()           \
    {                                                   \
        .dev_addr = ESP_LCD_TOUCH_IO_I2C_FT6336_ADDRESS, \
        .control_phase_bytes = 1,                       \
        .dc_bit_offset = 0,                             \
        .lcd_cmd_bits = 8,                              \
        .flags =                                        \
        {                                               \
            .disable_control_phase = 1,                 \
        },                                              \
        .scl_speed_hz = 400 * 1000                      \
    }

#ifdef __cplusplus
}
#endif
