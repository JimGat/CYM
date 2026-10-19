/* Runtime pin ownership controller. Never restore GPS into a partially torn-down
 * transport: after any acknowledged attempt, recovery is an explicit reboot. */
#include "sdkconfig.h"
#include "classic_usb_debug.h"
#include <stddef.h>
enum { USB_OFF, USB_STARTING, USB_ACTIVE, USB_REBOOT };
static unsigned state;
static unsigned get_state(void) { return __atomic_load_n(&state, __ATOMIC_ACQUIRE); }
#if CONFIG_BOARD_CYD2USB
static void set_state(unsigned value) { __atomic_store_n(&state, value, __ATOMIC_RELEASE); }
#endif
bool cym_classic_usb_active(void) { return get_state() == USB_ACTIVE; }
bool cym_classic_usb_gps_blocked(void) { return get_state() != USB_OFF; }
const char *cym_classic_usb_status(void)
{
    switch (get_state()) {
    case USB_STARTING: return "Classic USB Debug: starting; GPS unavailable";
    case USB_ACTIVE: return "Classic USB Debug: ON (115200); GPS unavailable";
    case USB_REBOOT: return "Classic USB Debug: recovery; GPS unavailable; reboot required";
    default: return "Classic USB Debug: OFF (default each boot)";
    }
}
esp_err_t cym_classic_usb_enable(bool ack, esp_err_t (*quiesce)(void))
{
#if CONFIG_BOARD_CYD2USB
    if (!ack || !quiesce) return ESP_ERR_INVALID_ARG;
    if (get_state() == USB_ACTIVE) return ESP_OK;
    if (get_state() != USB_OFF) return ESP_ERR_INVALID_STATE;
    /* Publish inhibition BEFORE any UART0 operation. Classic GPS is a bounded
     * main-loop reader, so the owner transition cannot race that reader. */
    set_state(USB_STARTING);
    esp_err_t rc = quiesce();
    if (rc == ESP_OK) rc = cym_classic_usb_uart_start();
    if (rc != ESP_OK) {
        (void)cym_classic_usb_uart_stop();
        set_state(USB_REBOOT);
        return rc;
    }
    set_state(USB_ACTIVE);
    return ESP_OK;
#else
    (void)ack; (void)quiesce;
    return ESP_ERR_NOT_SUPPORTED;
#endif
}
esp_err_t cym_classic_usb_disable(void)
{
#if CONFIG_BOARD_CYD2USB
    if (get_state() == USB_OFF) return ESP_OK;
    set_state(USB_REBOOT); /* Inhibit GPS even when stop fails. No automatic retry. */
    return cym_classic_usb_uart_stop();
#else
    return ESP_ERR_NOT_SUPPORTED;
#endif
}
