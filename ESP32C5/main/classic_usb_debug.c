/* Runtime pin ownership controller. Never restore GPS into a partially torn-down
 * transport: after any acknowledged attempt, recovery is an explicit reboot. */
#include "sdkconfig.h"
#include "classic_usb_debug.h"
#include <stddef.h>
#if CYM_CLASSIC_USB_PERSISTENT
#include "nvs.h"
#endif
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
#if CYM_CLASSIC_USB_PERSISTENT
    default: return "Classic USB Debug: OFF (saved opt-in only)";
#else
    default: return "Classic USB Debug: OFF (default each boot)";
#endif
    }
}
#if CYM_CLASSIC_USB_PERSISTENT
/* Only owner transitions touch NVS, never the logger callback or timer. */
static esp_err_t save_opt_in(bool on)
{
    nvs_handle_t h;
    esp_err_t rc = nvs_open("cym_usb", NVS_READWRITE, &h);
    if (rc != ESP_OK) return rc;
    rc = nvs_set_u8(h, "enabled", on ? 1 : 0);
    if (rc == ESP_OK) rc = nvs_commit(h);
    nvs_close(h);
    return rc;
}
static esp_err_t boot_quiesce(void) { return ESP_OK; } /* GPS has not started. */
#endif
esp_err_t cym_classic_usb_restore(void)
{
#if CYM_CLASSIC_USB_PERSISTENT
    if (get_state() != USB_OFF) return ESP_ERR_INVALID_STATE;
    nvs_handle_t h;
    uint8_t value = 0;
    esp_err_t rc = nvs_open("cym_usb", NVS_READWRITE, &h);
    if (rc == ESP_OK) {
        rc = nvs_get_u8(h, "enabled", &value);
        nvs_close(h);
        if (rc == ESP_ERR_NVS_NOT_FOUND) rc = ESP_OK;
    }
    /* Unknown/corrupt ownership fails closed: no TX and no GPS this boot. */
    if (rc != ESP_OK || value > 1) {
        set_state(USB_REBOOT);
        return rc != ESP_OK ? rc : ESP_ERR_INVALID_STATE;
    }
    if (!value) return ESP_OK;
    return cym_classic_usb_enable(true, boot_quiesce);
#else
    return ESP_ERR_NOT_SUPPORTED;
#endif
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
#if CYM_CLASSIC_USB_PERSISTENT
    if (rc == ESP_OK) rc = save_opt_in(true);
#endif
    if (rc == ESP_OK) rc = cym_classic_usb_uart_start();
    if (rc != ESP_OK) {
        (void)cym_classic_usb_uart_stop();
#if CYM_CLASSIC_USB_PERSISTENT
        (void)save_opt_in(false); /* Best effort: an NVS fault is still reported. */
#endif
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
#if CYM_CLASSIC_USB_PERSISTENT
    /* Always clear, even when already OFF. Do not reboot on an uncommitted OFF.
     * Stop output even when persistence fails, but preserve the error to the UI. */
    esp_err_t saved = save_opt_in(false);
    if (get_state() == USB_OFF && saved == ESP_OK) return ESP_OK;
    set_state(USB_REBOOT);
    esp_err_t stopped = cym_classic_usb_uart_stop();
    return saved != ESP_OK ? saved : stopped;
#else
    if (get_state() == USB_OFF) return ESP_OK;
    set_state(USB_REBOOT); /* Inhibit GPS even when stop fails. No automatic retry. */
    return cym_classic_usb_uart_stop();
#endif
#else
    return ESP_ERR_NOT_SUPPORTED;
#endif
}
