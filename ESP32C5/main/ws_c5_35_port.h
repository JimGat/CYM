#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"

// Waveshare ESP32-C5-Touch-LCD-3.5 board adapter.
// Owns: I2C bus, CH32V006 IO expander, ST7796 display, FT6336 touch, backlight.
// Called from main.c under CONFIG_BOARD_WS_C5_35 guards.

esp_err_t ws_c5_35_display_init(esp_lcd_panel_handle_t *panel,
                                esp_lcd_panel_io_handle_t *io);
esp_err_t ws_c5_35_touch_init(void);
bool ws_c5_35_touch_read(uint16_t *x, uint16_t *y, bool *touched);
void ws_c5_35_backlight_set(uint8_t level);
bool ws_c5_35_audio_amp(bool on);

#include "driver/i2c_master.h"
// Existing adapter-owned bus; no second I2C port/bus is created.
i2c_master_bus_handle_t ws_c5_35_i2c_bus(void);
esp_err_t ws_c5_35_battery_read(bool *present, uint16_t *millivolts);

/* Isolated owner reads at most two points in one driver snapshot. */
bool ws_c5_35_touch_read_points(uint16_t *,uint16_t *,uint8_t *,uint8_t);
