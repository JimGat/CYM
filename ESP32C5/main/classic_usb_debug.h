#pragma once
#include <stdbool.h>
#include "esp_err.h"
/* Main/LVGL owner only for transitions. Read-only predicates are task-safe.
 * This transport is volatile and separate from persisted debug verbosity. */
bool cym_classic_usb_active(void);
bool cym_classic_usb_gps_blocked(void);
const char *cym_classic_usb_status(void);
esp_err_t cym_classic_usb_enable(bool gps_disconnected_ack, esp_err_t (*quiesce_gps)(void));
/* Success means TX released. GPS stays inhibited until a normal reboot. */
esp_err_t cym_classic_usb_disable(void);
/* Internal transport seam: permits host fault injection without emulating GPS. */
esp_err_t cym_classic_usb_uart_start(void);
esp_err_t cym_classic_usb_uart_stop(void);
