// PCF85063A RTC I2C register access for WS-C5-28.
// BCD encode/decode, calendar validation, OS flag handling.
// No LVGL, GPS, Wi-Fi, or NTP dependency.

#include "pcf85063.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <string.h>

static const char *TAG = "pcf85063";

// I2C timeout for register operations
#define I2C_TIMEOUT_MS 100

// ── BCD helpers ──────────────────────────────────────────────────────────────

uint8_t bcd_to_dec(uint8_t bcd)
{
    return ((bcd >> 4) & 0x0F) * 10 + (bcd & 0x0F);
}

uint8_t dec_to_bcd(uint8_t dec)
{
    return ((dec / 10) << 4) | (dec % 10);
}

// ── Calendar validation ──────────────────────────────────────────────────────

static bool is_leap_year(int year)
{
    return (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
}

static int days_in_month(int month, int year)
{
    static const int dm[] = { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
    if (month < 1 || month > 12) return 0;
    int d = dm[month - 1];
    if (month == 2 && is_leap_year(year)) d = 29;
    return d;
}

bool pcf85063_validate_calendar(const struct tm *t)
{
    if (!t) return false;
    int year = t->tm_year + 1900;
    int mon  = t->tm_mon + 1;
    // PCF85063A year register is 0-99, so we support 2000-2099
    if (year < 2000 || year > 2099) return false;
    if (mon < 1 || mon > 12) return false;
    if (t->tm_mday < 1 || t->tm_mday > days_in_month(mon, year)) return false;
    if (t->tm_hour < 0 || t->tm_hour > 23) return false;
    if (t->tm_min < 0 || t->tm_min > 59) return false;
    if (t->tm_sec < 0 || t->tm_sec > 59) return false;
    return true;
}

// ── I2C register access ─────────────────────────────────────────────────────

static esp_err_t pcf_read_reg(pcf85063_handle_t *h, uint8_t reg, uint8_t *buf, size_t len)
{
    return i2c_master_transmit_receive(h->dev, &reg, 1, buf, len, I2C_TIMEOUT_MS);
}

static esp_err_t pcf_write_reg(pcf85063_handle_t *h, uint8_t reg, const uint8_t *data, size_t len)
{
    // Build [reg, data...] buffer on stack (max 8 bytes: reg + 7 calendar regs)
    uint8_t buf[8];
    if (len + 1 > sizeof(buf)) return ESP_ERR_INVALID_SIZE;
    buf[0] = reg;
    memcpy(&buf[1], data, len);
    return i2c_master_transmit(h->dev, buf, len + 1, I2C_TIMEOUT_MS);
}

// ── Public API ──────────────────────────────────────────────────────────────

esp_err_t pcf85063_init(pcf85063_handle_t *handle, i2c_master_bus_handle_t bus,
                        uint8_t i2c_addr)
{
    if (!handle) return ESP_ERR_INVALID_ARG;
    memset(handle, 0, sizeof(*handle));

    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = i2c_addr,
        .scl_speed_hz = 100000,
    };
    esp_err_t ret = i2c_master_bus_add_device(bus, &dev_cfg, &handle->dev);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to add PCF85063A at 0x%02X: %s", i2c_addr, esp_err_to_name(ret));
        return ret;
    }

    handle->mutex = xSemaphoreCreateMutex();
    if (!handle->mutex) {
        ESP_LOGE(TAG, "Failed to create PCF85063A mutex");
        i2c_master_bus_rm_device(handle->dev);
        handle->dev = NULL;
        return ESP_ERR_NO_MEM;
    }

    // Probe: try reading Control1 register
    uint8_t ctrl1;
    ret = pcf_read_reg(handle, PCF85063_REG_CONTROL1, &ctrl1, 1);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "PCF85063A probe failed: %s", esp_err_to_name(ret));
        vSemaphoreDelete(handle->mutex);
        handle->mutex = NULL;
        i2c_master_bus_rm_device(handle->dev);
        handle->dev = NULL;
        return ret;
    }

    ESP_LOGI(TAG, "PCF85063A init OK (I2C 0x%02X, ctrl1=0x%02X)", i2c_addr, ctrl1);
    return ESP_OK;
}

esp_err_t pcf85063_read_time(pcf85063_handle_t *handle, struct tm *out_time,
                             bool *os_flag)
{
    if (!handle || !handle->dev || !out_time || !os_flag) return ESP_ERR_INVALID_ARG;

    if (xSemaphoreTake(handle->mutex, pdMS_TO_TICKS(200)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    // Read 7 calendar registers starting at Seconds (0x04)
    uint8_t regs[7];
    esp_err_t ret = pcf_read_reg(handle, PCF85063_REG_SECONDS, regs, 7);
    xSemaphoreGive(handle->mutex);
    if (ret != ESP_OK) return ret;

    // OS flag is bit 7 of seconds register
    *os_flag = (regs[0] & PCF85063_OS_BIT) != 0;

    out_time->tm_sec  = bcd_to_dec(regs[0] & 0x7F);
    out_time->tm_min  = bcd_to_dec(regs[1] & 0x7F);
    out_time->tm_hour = bcd_to_dec(regs[2] & 0x3F);
    out_time->tm_mday = bcd_to_dec(regs[3] & 0x3F);
    out_time->tm_wday = regs[4] & 0x07;
    out_time->tm_mon  = bcd_to_dec(regs[5] & 0x1F) - 1;  // struct tm: 0-11
    out_time->tm_year = bcd_to_dec(regs[6]) + 100;        // struct tm: years since 1900
    out_time->tm_isdst = 0;

    return ESP_OK;
}

esp_err_t pcf85063_write_time(pcf85063_handle_t *handle, const struct tm *t)
{
    if (!handle || !handle->dev || !t) return ESP_ERR_INVALID_ARG;
    if (!pcf85063_validate_calendar(t)) return ESP_ERR_INVALID_ARG;

    uint8_t regs[7];
    regs[0] = dec_to_bcd(t->tm_sec) & 0x7F;  // Clear OS flag on write
    regs[1] = dec_to_bcd(t->tm_min);
    regs[2] = dec_to_bcd(t->tm_hour);
    regs[3] = dec_to_bcd(t->tm_mday);
    regs[4] = t->tm_wday & 0x07;
    regs[5] = dec_to_bcd(t->tm_mon + 1);      // struct tm: 0-11 -> 1-12
    regs[6] = dec_to_bcd(t->tm_year - 100);   // struct tm: years since 1900 -> 0-99

    if (xSemaphoreTake(handle->mutex, pdMS_TO_TICKS(200)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    esp_err_t ret = pcf_write_reg(handle, PCF85063_REG_SECONDS, regs, 7);
    xSemaphoreGive(handle->mutex);

    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "RTC write: %04d-%02d-%02d %02d:%02d:%02d UTC",
                 t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
                 t->tm_hour, t->tm_min, t->tm_sec);
    }
    return ret;
}

esp_err_t pcf85063_read_offset(pcf85063_handle_t *handle, int8_t *offset)
{
    if (!handle || !handle->dev || !offset) return ESP_ERR_INVALID_ARG;
    uint8_t raw;
    if (xSemaphoreTake(handle->mutex, pdMS_TO_TICKS(200)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }
    esp_err_t ret = pcf_read_reg(handle, PCF85063_REG_OFFSET, &raw, 1);
    xSemaphoreGive(handle->mutex);
    if (ret != ESP_OK) return ret;
    *offset = (int8_t)raw;
    return ESP_OK;
}

esp_err_t pcf85063_write_offset(pcf85063_handle_t *handle, int8_t offset)
{
    if (!handle || !handle->dev) return ESP_ERR_INVALID_ARG;
    uint8_t raw = (uint8_t)offset;
    if (xSemaphoreTake(handle->mutex, pdMS_TO_TICKS(200)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }
    esp_err_t ret = pcf_write_reg(handle, PCF85063_REG_OFFSET, &raw, 1);
    xSemaphoreGive(handle->mutex);
    return ret;
}
