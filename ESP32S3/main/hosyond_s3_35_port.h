#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"
#include "esp_lcd_panel_ops.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "lvgl.h"

typedef struct {
    esp_lcd_panel_handle_t panel;
    SemaphoreHandle_t flush_done;
} hosyond_s3_35_display_t;

esp_err_t hosyond_s3_35_display_init(hosyond_s3_35_display_t *display);
esp_err_t hosyond_s3_35_draw(hosyond_s3_35_display_t *display,
                             int x_start, int y_start,
                             int x_end, int y_end,
                             const void *pixels);
void hosyond_s3_35_round_area(lv_area_t *area);
esp_err_t hosyond_s3_35_touch_init(void);
bool hosyond_s3_35_touch_read(uint16_t *x, uint16_t *y, bool *pressed);
