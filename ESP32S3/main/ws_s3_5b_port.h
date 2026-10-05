#pragma once
#include "sdkconfig.h"
#if defined(CONFIG_BOARD_WS_S3_5B)
#include "driver/i2c_master.h"
#include "esp_lcd_panel_ops.h"
#include "esp_err.h"
#include "lvgl.h"
esp_err_t ws_s3_5b_bus_init(i2c_master_bus_handle_t bus);
esp_err_t ws_s3_5b_display_init(esp_lcd_panel_handle_t *panel);
esp_err_t ws_s3_5b_touch_init(void);
bool ws_s3_5b_touch_read(uint16_t *x, uint16_t *y, bool *pressed);
esp_err_t ws_s3_5b_backlight(bool on);
void ws_s3_5b_flush(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *pixels);
#endif
