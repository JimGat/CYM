#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "sdkconfig.h"
#define CYM_CLASSIC_USB_PERSISTENT (CONFIG_BOARD_CYD2USB && !CONFIG_BOARD_HACKERBOX_CYD && !CONFIG_BOARD_HAS_PSRAM && !CONFIG_SPIRAM)
#include "esp_err.h"
/* Main/LVGL owner only for transitions. Read-only predicates are task-safe.
 * Classic no-PSRAM opt-in persists; other boards retain their prior behavior. */
bool cym_classic_usb_active(void);
bool cym_classic_usb_gps_blocked(void);
const char *cym_classic_usb_status(void);
esp_err_t cym_classic_usb_enable(bool gps_disconnected_ack, esp_err_t (*quiesce_gps)(void));
/* Success means TX released. GPS stays inhibited until a normal reboot. */
esp_err_t cym_classic_usb_disable(void);
/* Internal transport seam: permits host fault injection without emulating GPS. */
esp_err_t cym_classic_usb_uart_start(void);
esp_err_t cym_classic_usb_uart_stop(void);

/* Bounded transport counters; no logging while collecting these. */
typedef struct {
    uint32_t accepted_records, dropped_records, busy_calls, retry_writes;
} cym_classic_usb_uart_stats_t;
void cym_classic_usb_uart_stats(cym_classic_usb_uart_stats_t *out);

/* Call once after successful NVS initialization, before ANY GPS UART access.
 * Previously persisted acknowledgement is the only early-boot authorization. */
esp_err_t cym_classic_usb_restore(void);
