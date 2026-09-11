// board_hal.h — Board Hardware Abstraction Layer for CYM ESP32-S3 firmware.
//
// Selects the correct board header based on CONFIG_BOARD_* Kconfig choice,
// then re-exports all BOARD_* pin defines and capability flags.
//
// Usage in board-agnostic code:
//   #include "board_hal.h"
//   spi_bus_initialize(BOARD_LCD_HOST, &cfg, SPI_DMA_CH_AUTO);
//
// New board checklist:
//   1. Add include/boards/<name>.h with all BOARD_* defines.
//   2. Add a Kconfig choice entry in Kconfig.
//   3. Add an #elif dispatch below.
//   4. Update sdkconfig.defaults.<name> with CONFIG_BOARD_<NAME>=y.
//   No changes to main.c or any component source required.
#pragma once

#include "sdkconfig.h"

// ── Board header dispatch ────────────────────────────────────────────────────

#if defined(CONFIG_BOARD_HOSYOND_S3_35)
#  include "boards/hosyond_s3_35.h"
#elif defined(CONFIG_BOARD_HOSYOND_S3_28)
#  include "boards/hosyond_s3_28.h"
#elif defined(CONFIG_BOARD_HOSYOND_S3_40)
#  include "boards/hosyond_s3_40.h"
#else
// Fallback: Hosyond 3.5" if no board explicitly configured.
#  include "boards/hosyond_s3_35.h"
#endif

// ── API ───────────────────────────────────────────────────────────────────────
#ifdef __cplusplus
extern "C" {
#endif

// Log board identification and capability summary at startup.
void board_hal_log_info(void);

#ifdef __cplusplus
}
#endif
