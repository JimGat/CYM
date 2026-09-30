#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"

esp_err_t pancake_c5_display_init(esp_lcd_panel_handle_t *panel,
                                  esp_lcd_panel_io_handle_t *io);
esp_err_t pancake_c5_touch_init(void);
bool pancake_c5_touch_read(uint16_t *x, uint16_t *y, bool *touched);
