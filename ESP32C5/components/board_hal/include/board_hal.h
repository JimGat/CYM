// board_hal.h — Board Hardware Abstraction Layer for CYM multi-board firmware.
//
// Selects the correct board header based on CONFIG_BOARD_* Kconfig choice,
// then re-exports all BOARD_* pin defines and capability flags.
//
// Usage in board-agnostic code:
//   #include "board_hal.h"
//   gpio_set_level(BOARD_LCD_CS, 1);
//
// Phase 2 complete: main.c and wifi_common.h now use BOARD_* defines exclusively.
// This header is the single source of truth for all board-variant GPIO assignments.
// New boards: add a header under include/boards/, add a Kconfig choice, dispatch here.
#pragma once

#include "sdkconfig.h"

// ── Board header dispatch ────────────────────────────────────────────────────

#if defined(CONFIG_BOARD_NM_CYD_C5)
#  include "boards/nm_cyd_c5.h"
#elif defined(CONFIG_BOARD_WS_C5_28)
#  include "boards/ws_c5_28.h"
#elif defined(CONFIG_BOARD_CYD2USB)
#  include "boards/cyd2usb.h"
#elif defined(CONFIG_BOARD_HOSYOND_S3_35)
#  include "boards/hosyond_s3_35.h"
#elif defined(CONFIG_BOARD_HOSYOND_S3_28)
#  include "boards/hosyond_s3_28.h"
#elif defined(CONFIG_BOARD_HOSYOND_S3_40)
#  include "boards/hosyond_s3_40.h"
#else
// Fallback: default to NM-CYD-C5 if no board is explicitly configured.
// This ensures the existing build (which predates Kconfig board selection)
// continues to compile without changes to sdkconfig.
#  include "boards/nm_cyd_c5.h"
#endif

// ── Capability and pin fallbacks ─────────────────────────────────────────────
// Board headers define only physically present features. Shared code consumes
// these normalized names without inventing cross-board GPIO assumptions.
#ifndef BOARD_GPS_TX_GPIO
#define BOARD_GPS_TX_GPIO -1
#endif
#ifndef BOARD_GPS_RX_GPIO
#define BOARD_GPS_RX_GPIO -1
#endif
#ifndef BOARD_GPS_TX
#define BOARD_GPS_TX BOARD_GPS_TX_GPIO
#endif
#ifndef BOARD_GPS_RX
#define BOARD_GPS_RX BOARD_GPS_RX_GPIO
#endif
#ifndef BOARD_HAS_GPS
#if BOARD_GPS_TX >= 0 && BOARD_GPS_RX >= 0
#define BOARD_HAS_GPS 1
#else
#define BOARD_HAS_GPS 0
#endif
#endif
#ifndef BOARD_HAS_SD
#define BOARD_HAS_SD 1
#endif
#ifndef BOARD_SD_SPI_FREQ_HZ
#define BOARD_SD_SPI_FREQ_HZ 20000000
#endif
#ifndef BOARD_HAS_BATTERY_ADC
#define BOARD_HAS_BATTERY_ADC 0
#endif
#ifndef BOARD_BATTERY_ADC_GPIO
#define BOARD_BATTERY_ADC_GPIO -1
#endif
#ifndef BOARD_BATTERY_DIVIDER_NUM
#define BOARD_BATTERY_DIVIDER_NUM 1
#endif
#ifndef BOARD_BATTERY_DIVIDER_DEN
#define BOARD_BATTERY_DIVIDER_DEN 1
#endif
#ifndef BOARD_RGB_PIN
#ifdef BOARD_RGB_LED_GPIO
#define BOARD_RGB_PIN BOARD_RGB_LED_GPIO
#else
#define BOARD_RGB_PIN -1
#endif
#endif
#ifndef BOARD_HAS_RGB_LED
#ifdef CONFIG_BOARD_HAS_RGB_LED
#define BOARD_HAS_RGB_LED 1
#else
#define BOARD_HAS_RGB_LED 0
#endif
#endif

// ── Sanity checks — catch impossible combinations at compile time ─────────────

#if defined(CONFIG_BOARD_HAS_BACKLIGHT_EXPANDER) && defined(CONFIG_BOARD_TOUCH_XPT2046)
#  error "Board config error: backlight expander boards use capacitive touch, not XPT2046"
#endif

// ── API ───────────────────────────────────────────────────────────────────────
#ifdef __cplusplus
extern "C" {
#endif

// Log board identification and capability summary to ESP_LOGI at startup.
void board_hal_log_info(void);

#ifdef __cplusplus
}
#endif
