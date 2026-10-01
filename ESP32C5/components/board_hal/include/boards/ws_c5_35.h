// Waveshare ESP32-C5-Touch-LCD-3.5 pin definitions.
//
// Board: Waveshare ESP32-C5-Touch-LCD-3.5 (SKU 35419)
// SoC:   ESP32-C5-WROOM-1U, RISC-V 240 MHz
// Flash: 32 MB | PSRAM: 8 MB | WiFi 6 (2.4 + 5 GHz) | BT 5
// Ref:   https://github.com/waveshareteam/ESP32-C5-Touch-LCD-3.5
//        BSP header: bsp/esp32_c5_touch_lcd_3_5.h
//        Vendor commit: 04e6134cf3e37309b2bec9915189efeace1161bc
//
// EXPERIMENTAL — hardware validation pending.
// Display, touch, and PMIC settings use vendor BSP defaults and have NOT
// been verified on CYM hardware. Do not treat any transform, inversion,
// or color-order setting as confirmed until Jim's SKU 35419 unit boots.
#pragma once

// ── SPI bus ───────────────────────────────────────────────────────────────────
// SPI2_HOST shared by ST7796 (LCD) and SD card.
// MISO is GPIO2 (SD only; ST7796 is write-only).
#define BOARD_SPI_HOST       SPI2_HOST
#define BOARD_SPI_SCK        6
#define BOARD_SPI_MOSI       7
#define BOARD_SPI_MISO       2

// ── ST7796 display (320x480 SPI) ─────────────────────────────────────────────
#define BOARD_LCD_CS         8
#define BOARD_LCD_DC         5
#define BOARD_LCD_RST        -1   // Via CH32V006 EXIO1 — not a direct GPIO
#define BOARD_LCD_WIDTH      320
#define BOARD_LCD_HEIGHT     480
#define BOARD_LCD_PCLK_HZ    60000000
// Backlight: CH32V006 PWM via I2C 0x24. Not a direct GPIO.
#define BOARD_BACKLIGHT_GPIO -1

// ── FT6336 capacitive touch ──────────────────────────────────────────────────
// I2C touch controller at 0x38. Interrupt on GPIO3.
// RST driven via CH32V006 EXIO0 (not a direct GPIO).
#define BOARD_TOUCH_CS       -1
#define BOARD_TOUCH_INT      3
#define BOARD_TOUCH_RST      -1
#define BOARD_TOUCH_I2C_ADDR 0x38

// ── SD card ──────────────────────────────────────────────────────────────────
// SD shares SPI2_HOST with LCD (same bus, different CS).
#define BOARD_SD_SPI_HOST    SPI2_HOST
#define BOARD_SD_SCK         BOARD_SPI_SCK
#define BOARD_SD_MOSI        BOARD_SPI_MOSI
#define BOARD_SD_MISO        BOARD_SPI_MISO
#define BOARD_SD_CS          9

// ── I2C bus (shared: FT6336, CH32V006, AXP2101, QMI8658, SHTC3, PCF85063A) ─
#define BOARD_I2C_SDA        27
#define BOARD_I2C_SCL        26

// ── CH32V006 IO Expander (I2C 0x24) ──────────────────────────────────────────
// 16-pin expander controlling: touch RST (EXIO0), LCD RST (EXIO1),
// power enable (EXIO5), LCD backlight PWM. 16-bit little-endian register
// protocol — NOT the same command set as WS-C5-28's CH32V003.
#define BOARD_IO_EXPANDER_I2C_ADDR  0x24
#define BOARD_LCD_RESET_EXIO        1   // EXIO pin index for LCD RST
#define BOARD_TOUCH_RESET_EXIO      0   // EXIO pin index for touch RST
#define BOARD_POWER_ENABLE_EXIO      5   // Vendor BSP holds EXIO5 high during operation

// ── AXP2101 PMIC (I2C 0x34) ─────────────────────────────────────────────────
// Power management, battery charging, backlight rail. Probed at init but
// not fully programmed until hardware-validated.
#define BOARD_PMIC_I2C_ADDR  0x34

// ── GPS - disabled (UART exposed but not wired) ─────────────────────────
// BOARD_GPS_UART_NUM is required by wifi_common.h unconditionally.
// TX/RX pins are not defined - board_hal.h defaults them to -1.
#define BOARD_GPS_UART_NUM   1

// ── Boot button ──────────────────────────────────────────────────────────────
#define BOARD_BOOT_BTN_GPIO  28

// ── Capability flags (experimental — conservative) ───────────────────────────
// Capabilities present on the board but NOT yet enabled in CYM firmware
// (GPS, RTC, audio, sensors, battery, camera) are explicitly set to 0.
// They must not be enabled until hardware-validated on Jim's SKU 35419.
#define BOARD_HAS_PSRAM      1
#define BOARD_HAS_SD         1
#define BOARD_HAS_GPS        0
#define BOARD_HAS_BATTERY_ADC 0
#define BOARD_HAS_AUDIO      0
#define BOARD_HAS_RGB_LED    0

// ── No vibrator or WS2812 on this board ──────────────────────────────────────
#define BOARD_VIBRATOR_GPIO  -1
#define BOARD_RGB_LED_GPIO   -1
#define BOARD_RGB_LED_COUNT  0

// ── Timing profile (uncharacterized — all sources disabled) ──────────────────
#define BOARD_TIME_HAS_RTC                    0
#define BOARD_TIME_HAS_GPS_UART               0
#define BOARD_TIME_HAS_MDNS                   1
#define BOARD_TIME_RTOS_DRIFT_PPM             100
#define BOARD_TIME_NTP_UNCERTAINTY_US          250000
#define BOARD_TIME_ESTIMATE_CHARACTERIZED     0

// ── Board identifier string ──────────────────────────────────────────────────
#define BOARD_NAME           "WS-C5-35"
#define BOARD_DISPLAY_DRIVER "ST7796"
#define BOARD_TOUCH_DRIVER   "FT6336"
