// Hosyond 3.5" ES3C35P — ESP32-S3 display board pin definitions.
//
// Board: Hosyond 3.5" ES3C35P / lcdwiki 3.5inch_ESP32-S3_Display
// SoC:   ESP32-S3R8 — dual-core Xtensa LX7 240 MHz, 16 MB flash, 8 MB OPI PSRAM
// ASIN:  B0H28X8SQ4 (lcdwiki listing)
// Ref:   Official data pack (Dropbox, July 2026)
//
// All GPIO numbers are ESP32-S3 IDF GPIO numbers.
#pragma once

// ── ST77922 QSPI display (SPI2_HOST, quad-data-line mode) ───────────────────
// No DC pin — command bytes are embedded in the QSPI protocol.
// RST is shared with the chip-level EN; leave as GPIO_NUM_NC.
// TE (tear-effect) on IO42 reserved for future frame-sync use.
#define BOARD_LCD_HOST       SPI2_HOST
#define BOARD_LCD_CS         10          // IO10
#define BOARD_LCD_SCK        12          // IO12 (QSPI clock)
#define BOARD_LCD_D0         11          // IO11 (QSPI data line 0)
#define BOARD_LCD_D1         13          // IO13 (QSPI data line 1)
#define BOARD_LCD_D2         14          // IO14 (QSPI data line 2)
#define BOARD_LCD_D3          9          // IO9  (QSPI data line 3)
#define BOARD_LCD_DC         -1          // QSPI: no DC pin
#define BOARD_LCD_RST        -1          // shared with chip EN — not a GPIO
#define BOARD_LCD_TE_GPIO    42          // tear effect — reserved
#define BOARD_LCD_WIDTH      320
#define BOARD_LCD_HEIGHT     480
#define BOARD_BACKLIGHT_GPIO 41          // IO41, active-high, LEDC ch 1
#define BOARD_LCD_PCLK_HZ    (80 * 1000 * 1000)
// DMA buffer: 320 px wide × 50 lines; MUST stay in internal SRAM (not PSRAM)
// at 80 MHz QSPI to prevent DMA underruns and display tearing.
#define BOARD_LCD_BUF_LINES  50
#define BOARD_LCD_BUF_SIZE   (BOARD_LCD_WIDTH * BOARD_LCD_BUF_LINES * 2)

// ── Touch: custom I2C controller (addr 0x55) ─────────────────────────────────
// Shares I2C bus with audio codec. Capacitive — no calibration needed.
// INT fires low on touch event; RST is active-low (held high for normal op).
#define BOARD_TOUCH_CS       -1          // I2C — no SPI CS
#define BOARD_TOUCH_INT      47          // IO47, active-low
#define BOARD_TOUCH_RST      48          // IO48, active-low
#define BOARD_TOUCH_I2C_ADDR 0x55
#define BOARD_TOUCH_I2C_HZ   400000

// ── I2C bus (shared: touch 0x55, audio codec) ────────────────────────────────
// Also accessible via the I2C JST connector on the board edge.
#define BOARD_I2C_NUM        I2C_NUM_0
#define BOARD_I2C_SDA        38          // IO38 (also I2C JST)
#define BOARD_I2C_SCL        39          // IO39 (also I2C JST)

// ── SD card (SPI mode on SPI3_HOST, separate from display SPI2) ──────────────
// Board routes SD to SDIO-style pins; driven in SPI mode for sd_spi_mutex
// compatibility with all other CYM boards.
// SDIO → SPI: D3(IO3)=CS, CLK(IO5)=SCK, CMD(IO4)=MOSI, D0(IO6)=MISO.
// D1(IO7) and D2(IO2) unused in SPI mode — pulled high via BOARD_SD_PULLUP_D*.
#define BOARD_SD_SPI_HOST    SPI3_HOST
#define BOARD_SD_CS           3          // IO3 (SDIO D3)
#define BOARD_SD_SCK          5          // IO5 (SDIO CLK)
#define BOARD_SD_MOSI         4          // IO4 (SDIO CMD)
#define BOARD_SD_MISO         6          // IO6 (SDIO D0)
#define BOARD_SD_PULLUP_D1    7          // IO7 (SDIO D1) — pull high, not driven
#define BOARD_SD_PULLUP_D2    2          // IO2 (SDIO D2) — pull high, not driven
#define BOARD_SD_FREQ_KHZ     20000      // 20 MHz; matches NM-CYD-C5
#define BOARD_SD_MOUNT_POINT  "/sdcard"

// ── WS2812-compatible RGB LED ─────────────────────────────────────────────────
// Addressable single LED with built-in control IC on IO40.
#define BOARD_RGB_LED_GPIO   40          // IO40
#define BOARD_RGB_LED_COUNT   1

// ── Boot button ───────────────────────────────────────────────────────────────
// Standard ESP32-S3 BOOT/IO0 button. Active-low. Used as Go Dark wake button.
#define BOARD_BOOT_BTN_GPIO   0          // IO0

// ── No vibrator motor ────────────────────────────────────────────────────────
#define BOARD_VIBRATOR_GPIO  -1

// ── No GPS on this board ─────────────────────────────────────────────────────
// GPS_TX/RX = -1 gates GPS init in wifi_common.h.
#define BOARD_GPS_UART_NUM   UART_NUM_1  // unused — gated by BOARD_GPS_TX_GPIO
#define BOARD_GPS_TX_GPIO    -1
#define BOARD_GPS_RX_GPIO    -1

// ── Battery ADC ───────────────────────────────────────────────────────────────
// IO8 = voltage divider input, ADC1_CHANNEL_7 on ESP32-S3.
#define BOARD_BATT_ADC_GPIO   8

// ── Expansion JST connector (4-pin, 1.25 mm) ─────────────────────────────────
// IO45/IO46 plus GND and VCC. Future: RF-HAT shim adapter.
//   IO45 → RFHAT_PIN_A: GDO0 (CC1101) / CE (nRF24) / IR TX / RF433 TX
//   IO46 → RFHAT_PIN_B: CSN (CC1101/nRF24) / IR RX / RF433 RX
//   I2C (IO38/IO39) → PN532 I2C (addr 0x24; no conflict with touch 0x55)
//   SPI3 → CC1101/nRF24 SPI bus (requires hardware shim)
#define BOARD_EXP_GPIO_A     45
#define BOARD_EXP_GPIO_B     46
#define BOARD_RFHAT_PIN_A    45          // mirrors NM-CYD-C5 GPIO8 (IO22) function
#define BOARD_RFHAT_PIN_B    46          // mirrors NM-CYD-C5 GPIO9 (IO27) function

// ── UART0 (USB serial / console) ─────────────────────────────────────────────
#define BOARD_UART_TX        44          // IO44 (standard ESP32-S3 UART0)
#define BOARD_UART_RX        43          // IO43

// ── Board identifier strings ──────────────────────────────────────────────────
#define BOARD_NAME           "hosyond-s3-35"
#define BOARD_DISPLAY_DRIVER "ST77922"
#define BOARD_TOUCH_DRIVER   "custom-0x55"
