/**
 * board_hal_hosyond_s3_35.h
 *
 * GPIO and hardware constants for the Hosyond 3.5" ESP32-S3 display board.
 * SKU: ES3C35P / lcdwiki 3.5inch_ESP32-S3_Display
 * SoC: ESP32-S3R8 — dual-core LX7 240 MHz, 16 MB flash, 8 MB OPI PSRAM
 *
 * Confirmed from official data pack (Dropbox, July 2026).
 * All pin numbers are IDF GPIO numbers (same as ESP32-S3 physical GPIO).
 */

#pragma once

#include "driver/gpio.h"
#include "driver/spi_master.h"

/* ── Display: ST77922 QSPI ───────────────────────────────────────────────────
 *
 * Uses SPI2_HOST in quad-SPI mode (4 data lines).  No DC pin — command bytes
 * are embedded in the QSPI protocol.  RST is shared with the chip-level EN
 * pin so we leave it as GPIO_NUM_NC and let the hardware reset sequence handle
 * it.  TE (tear-effect) on IO42 can be used for frame sync; currently unused.
 */
#define H35S3_LCD_HOST          SPI2_HOST
#define H35S3_LCD_CS            GPIO_NUM_10
#define H35S3_LCD_SCLK          GPIO_NUM_12
#define H35S3_LCD_D0            GPIO_NUM_11
#define H35S3_LCD_D1            GPIO_NUM_13
#define H35S3_LCD_D2            GPIO_NUM_14
#define H35S3_LCD_D3            GPIO_NUM_9
#define H35S3_LCD_RST           GPIO_NUM_NC      /* shared with chip EN */
#define H35S3_LCD_BL            GPIO_NUM_41      /* active-high, LEDC ch 1 */
#define H35S3_LCD_TE            GPIO_NUM_42      /* tear-effect — reserved */
#define H35S3_LCD_PCLK_HZ       (80 * 1000 * 1000)
#define H35S3_LCD_H_RES         320
#define H35S3_LCD_V_RES         480
/* DMA buffer: 320 px wide × 50 lines; keep in internal SRAM for 80 MHz SPI */
#define H35S3_LCD_BUF_LINES     50
#define H35S3_LCD_BUF_SIZE      (H35S3_LCD_H_RES * H35S3_LCD_BUF_LINES * 2)

/* ── Touch: ST77922-companion I2C (custom IC, not FT6336) ───────────────────
 *
 * Touch and audio codec share the same I2C bus (IO38/IO39).
 * Touch address: 0x55.  Audio codec address: (unknown, currently unused).
 * No calibration required (capacitive).
 * INT fires low when a touch event is pending.
 * RST is active-low; pulled high after power-on for normal operation.
 */
#define H35S3_TOUCH_I2C_NUM     I2C_NUM_0
#define H35S3_TOUCH_SDA         GPIO_NUM_38
#define H35S3_TOUCH_SCL         GPIO_NUM_39
#define H35S3_TOUCH_RST         GPIO_NUM_48      /* active-low */
#define H35S3_TOUCH_INT         GPIO_NUM_47      /* active-low interrupt */
#define H35S3_TOUCH_I2C_ADDR    0x55
#define H35S3_TOUCH_I2C_HZ      400000

/* ── SD Card: SPI mode (wired for SDIO but driven as SPI) ───────────────────
 *
 * The board routes the SD card to SDIO-style pins.  We use them in SPI mode
 * which keeps our sd_spi_mutex code path identical to all other CYM boards.
 *
 * SDIO → SPI mapping:
 *   D3  (IO3)  → CS   (chip select)
 *   CLK (IO5)  → SCK
 *   CMD (IO4)  → MOSI
 *   D0  (IO6)  → MISO
 *
 * D1 (IO7) and D2 (IO2) are unused in SPI mode — internal pull-ups keep them
 * idle-high so the card stays in SPI mode after CMD0 (GO_IDLE_STATE).
 *
 * The SD SPI bus is separate from the display QSPI (SPI2).  We use SPI3 so
 * the two hosts never contend.  This also leaves SPI3 free to share with
 * RF-HAT peripherals (CC1101/nRF24) once a shim adapter is designed.
 */
#define H35S3_SD_HOST           SPI3_HOST
#define H35S3_SD_CS             GPIO_NUM_3
#define H35S3_SD_SCK            GPIO_NUM_5
#define H35S3_SD_MOSI           GPIO_NUM_4
#define H35S3_SD_MISO           GPIO_NUM_6
#define H35S3_SD_PULLUP_D1      GPIO_NUM_7       /* pull high — not driven */
#define H35S3_SD_PULLUP_D2      GPIO_NUM_2       /* pull high — not driven */
#define H35S3_SD_FREQ_KHZ       20000            /* 20 MHz; matches other boards */
#define H35S3_SD_MOUNT_POINT    "/sdcard"

/* ── RGB LED ─────────────────────────────────────────────────────────────────
 * IO40: addressable RGB LED (WS2812-compatible built-in control IC).
 */
#define H35S3_LED_GPIO          GPIO_NUM_40

/* ── Buttons ─────────────────────────────────────────────────────────────────
 * IO0: Boot/IO0 button — also used for Go Dark wake in CYM.
 */
#define H35S3_BTN_BOOT          GPIO_NUM_0

/* ── Serial / UART0 ──────────────────────────────────────────────────────────
 * Standard ESP32-S3 UART0 pins.
 */
#define H35S3_UART_TX           GPIO_NUM_44
#define H35S3_UART_RX           GPIO_NUM_43

/* ── Expansion (future RF-HAT shim) ─────────────────────────────────────────
 * 4-pin 1.25 mm JST on-board: IO45, IO46, GND, VCC.
 * I2C JST (shared with touch): IO38 (SDA), IO39 (SCL).
 *
 * RF-HAT pin mapping (when shim adapter is available):
 *   IO45 → RF-HAT GPIO8: GDO0 (CC1101) / CE (nRF24) / IR TX / RF433 TX
 *   IO46 → RF-HAT GPIO9: CSN (CC1101/nRF24) / IR RX / RF433 RX
 *   I2C  → RF-HAT PN532 (DIP3): PN532 I2C addr 0x24, no conflict w/ touch 0x55
 *   SPI3 → RF-HAT CC1101 / nRF24 SPI bus (requires hardware shim)
 */
#define H35S3_EXP_GPIO_A        GPIO_NUM_45
#define H35S3_EXP_GPIO_B        GPIO_NUM_46

/* ── Battery ADC ─────────────────────────────────────────────────────────────
 * IO8: voltage divider input — ADC1_CHANNEL_7 on ESP32-S3.
 * (currently unused — read via esp_adc when needed)
 */
#define H35S3_BATT_ADC_GPIO     GPIO_NUM_8
