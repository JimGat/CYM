/*
 * SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

// FT6336 capacitive touch driver for esp_lcd_touch interface.
// Adapted from Waveshare ESP32-C5-Touch-LCD-3.5 BSP.

#include <string.h>
#include "esp_lcd_touch_ft6336.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_check.h"
#include "driver/gpio.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_touch.h"

static const char *TAG = "ft6336";

#define FT6336_REG_TOUCH_POINTS 0x02
#define FT6336_REG_P1_XH       0x03

static esp_err_t ft6336_read_data(esp_lcd_touch_handle_t tp);
static bool ft6336_get_xy(esp_lcd_touch_handle_t tp, uint16_t *x, uint16_t *y,
                          uint16_t *strength, uint8_t *point_num, uint8_t max_point_num);
static esp_err_t ft6336_del(esp_lcd_touch_handle_t tp);

static esp_err_t ft6336_i2c_read(esp_lcd_touch_handle_t tp, uint8_t reg,
                                  uint8_t *data, uint8_t len)
{
    return esp_lcd_panel_io_rx_param(tp->io, reg, data, len);
}

esp_err_t esp_lcd_touch_new_i2c_ft6336(const esp_lcd_panel_io_handle_t io,
                                        const esp_lcd_touch_config_t *config,
                                        esp_lcd_touch_handle_t *out_touch)
{
    assert(config != NULL);
    assert(out_touch != NULL);
    esp_err_t ret = ESP_OK;

    esp_lcd_touch_handle_t tp = heap_caps_calloc(1, sizeof(esp_lcd_touch_t), MALLOC_CAP_DEFAULT);
    ESP_RETURN_ON_FALSE(tp, ESP_ERR_NO_MEM, TAG, "no mem for FT6336");

    tp->io = io;
    tp->read_data = ft6336_read_data;
    tp->get_xy = ft6336_get_xy;
    tp->del = ft6336_del;
    tp->data.lock.owner = portMUX_FREE_VAL;
    memcpy(&tp->config, config, sizeof(esp_lcd_touch_config_t));

    if (tp->config.int_gpio_num != GPIO_NUM_NC) {
        const gpio_config_t int_cfg = {
            .mode = GPIO_MODE_INPUT,
            .intr_type = tp->config.levels.interrupt ? GPIO_INTR_POSEDGE : GPIO_INTR_NEGEDGE,
            .pin_bit_mask = BIT64(tp->config.int_gpio_num),
        };
        ESP_GOTO_ON_ERROR(gpio_config(&int_cfg), err, TAG, "INT GPIO config");
        if (tp->config.interrupt_callback) {
            esp_lcd_touch_register_interrupt_callback(tp, tp->config.interrupt_callback);
        }
    }

    if (tp->config.rst_gpio_num != GPIO_NUM_NC) {
        const gpio_config_t rst_cfg = {
            .mode = GPIO_MODE_OUTPUT,
            .pin_bit_mask = BIT64(tp->config.rst_gpio_num),
        };
        ESP_GOTO_ON_ERROR(gpio_config(&rst_cfg), err, TAG, "RST GPIO config");
        gpio_set_level(tp->config.rst_gpio_num, tp->config.levels.reset);
        vTaskDelay(pdMS_TO_TICKS(10));
        gpio_set_level(tp->config.rst_gpio_num, !tp->config.levels.reset);
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    *out_touch = tp;
    return ESP_OK;

err:
    free(tp);
    *out_touch = NULL;
    return ESP_FAIL;
}

static esp_err_t ft6336_read_data(esp_lcd_touch_handle_t tp)
{
    uint8_t points = 0;
    esp_err_t err = ft6336_i2c_read(tp, FT6336_REG_TOUCH_POINTS, &points, 1);
    ESP_RETURN_ON_ERROR(err, TAG, "I2C read points");

    points &= 0x0F;
    if (points == 0) return ESP_OK;
    if (points > 2) points = 2;

    uint8_t data[12];
    err = ft6336_i2c_read(tp, FT6336_REG_P1_XH, data, 6 * points);
    ESP_RETURN_ON_ERROR(err, TAG, "I2C read coords");

    portENTER_CRITICAL(&tp->data.lock);
    tp->data.points = points;
    for (size_t i = 0; i < points; i++) {
        tp->data.coords[i].x = (((uint16_t)data[i * 6 + 0] & 0x0f) << 8) | data[i * 6 + 1];
        tp->data.coords[i].y = (((uint16_t)data[i * 6 + 2] & 0x0f) << 8) | data[i * 6 + 3];
    }
    portEXIT_CRITICAL(&tp->data.lock);
    return ESP_OK;
}

static bool ft6336_get_xy(esp_lcd_touch_handle_t tp, uint16_t *x, uint16_t *y,
                          uint16_t *strength, uint8_t *point_num, uint8_t max_point_num)
{
    portENTER_CRITICAL(&tp->data.lock);
    *point_num = (tp->data.points > max_point_num) ? max_point_num : tp->data.points;
    for (size_t i = 0; i < *point_num; i++) {
        x[i] = tp->data.coords[i].x;
        y[i] = tp->data.coords[i].y;
        if (strength) strength[i] = tp->data.coords[i].strength;
    }
    tp->data.points = 0;
    portEXIT_CRITICAL(&tp->data.lock);
    return (*point_num > 0);
}

static esp_err_t ft6336_del(esp_lcd_touch_handle_t tp)
{
    if (tp->config.int_gpio_num != GPIO_NUM_NC) gpio_reset_pin(tp->config.int_gpio_num);
    if (tp->config.rst_gpio_num != GPIO_NUM_NC) gpio_reset_pin(tp->config.rst_gpio_num);
    free(tp);
    return ESP_OK;
}
