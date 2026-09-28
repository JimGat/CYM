// PCF85063A RTC register access — WS-C5-28 hardware component.
// Owns I2C register reads/writes, BCD conversion, calendar validation,
// and oscillator-stop detection. No LVGL, GPS, Wi-Fi, or NTP dependency.
#pragma once

#include "driver/i2c_master.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <time.h>
#include <stdbool.h>

// PCF85063A register addresses
#define PCF85063_REG_CONTROL1   0x00
#define PCF85063_REG_CONTROL2   0x01
#define PCF85063_REG_OFFSET     0x02
#define PCF85063_REG_SECONDS    0x04
#define PCF85063_REG_MINUTES    0x05
#define PCF85063_REG_HOURS      0x06
#define PCF85063_REG_DAYS       0x07
#define PCF85063_REG_WEEKDAYS   0x08
#define PCF85063_REG_MONTHS     0x09
#define PCF85063_REG_YEARS      0x0A

// Seconds register bit 7 = OS (Oscillator Stop) flag
#define PCF85063_OS_BIT         0x80

typedef struct {
    i2c_master_dev_handle_t dev;
    SemaphoreHandle_t       mutex;
} pcf85063_handle_t;

// BCD helpers (exposed for testing)
uint8_t bcd_to_dec(uint8_t bcd);
uint8_t dec_to_bcd(uint8_t dec);

// Initialize PCF85063A on the given I2C bus at the given address.
// Returns ESP_OK on success; handle is zeroed on failure.
esp_err_t pcf85063_init(pcf85063_handle_t *handle, i2c_master_bus_handle_t bus,
                        uint8_t i2c_addr);

// Read UTC calendar from the RTC. Returns ESP_OK and populates *out_time.
// Sets *os_flag to true if the oscillator-stop flag is set (time invalid).
esp_err_t pcf85063_read_time(pcf85063_handle_t *handle, struct tm *out_time,
                             bool *os_flag);

// Write UTC calendar to the RTC. Clears the oscillator-stop flag on success.
// Validates the calendar before writing; returns ESP_ERR_INVALID_ARG for
// invalid dates.
esp_err_t pcf85063_write_time(pcf85063_handle_t *handle, const struct tm *t);

// Read the offset register (calibration, -64..+63 steps).
esp_err_t pcf85063_read_offset(pcf85063_handle_t *handle, int8_t *offset);

// Write the offset register.
esp_err_t pcf85063_write_offset(pcf85063_handle_t *handle, int8_t offset);

// Validate a struct tm for PCF85063A range: year 2000-2099, month 1-12,
// day 1-28/29/30/31 (leap-year aware), hour 0-23, minute 0-59, second 0-59.
bool pcf85063_validate_calendar(const struct tm *t);
