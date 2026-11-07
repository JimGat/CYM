// wifi_common.c - Common helper functions
#include "wifi_common.h"
#include "esp_wifi.h"
#include "esp_log.h"
#include <string.h>
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG_PWR = "power";

// Global variables (defined once, extern in header)
led_strip_handle_t g_led_strip = NULL;
volatile app_state_t g_app_state = APP_STATE_IDLE;
volatile bool g_operation_stop_requested = false;
bool g_max_power_mode = false;  // default Normal; persisted in NVS by main.c
uint8_t g_pwr_lvl = PWR_LVL_NORMAL;  // authoritative level; g_max_power_mode mirrors MAX

/* POWER_WIFI_STATE_BEGIN */
/* One retained internal allocation, no stack/SDK/display placement changes. The
 * operation gate is not a spinlock: only atomic admission uses it; driver owners
 * may yield while an already-admitted SDK call drains. The UI request never waits.
 * All maintained init/start/stop/deinit callers use the explicit adapters below. */
typedef struct {
    uint32_t generation;
    unsigned char gate, lifecycle_pending;
    bool active, captured;
    int8_t normal;
    uint8_t applied, status;
} wifi_power_state_t;
static wifi_power_state_t *s_wifi_power;
static bool wifi_power_state_init(void)
{
    if (__atomic_load_n(&s_wifi_power, __ATOMIC_ACQUIRE)) return true;
    wifi_power_state_t *created = heap_caps_calloc(1, sizeof(*created), MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!created) return false;
    wifi_power_state_t *expected = NULL;
    if (!__atomic_compare_exchange_n(&s_wifi_power, &expected, created, false, __ATOMIC_RELEASE, __ATOMIC_ACQUIRE))
        heap_caps_free(created);
    return true;
}
uint8_t wifi_power_applied_level(void)
{
    wifi_power_state_t *s = __atomic_load_n(&s_wifi_power, __ATOMIC_ACQUIRE);
    return s ? __atomic_load_n(&s->applied, __ATOMIC_ACQUIRE) : 0;
}
uint8_t wifi_power_status(void)
{
    wifi_power_state_t *s = __atomic_load_n(&s_wifi_power, __ATOMIC_ACQUIRE);
    return s ? __atomic_load_n(&s->status, __ATOMIC_ACQUIRE) : PWR_RADIO_OFF;
}
void wifi_power_new_generation(void)
{
    wifi_power_state_t *s = s_wifi_power;
    if (!s) return;
    __atomic_add_fetch(&s->generation, 1, __ATOMIC_ACQ_REL);
    s->captured = false;
    __atomic_store_n(&s->applied, 0, __ATOMIC_RELEASE);
}
/* Lifecycle owners retain the existing synchronous SDK contract. No additional
 * task/queue, no UI power-callback wait, no SDK calls under a critical section.
 * Pending owners close apply admission before waiting; unrelated utility/AP
 * ownership and configuration are deliberately not changed. */
static bool wifi_power_owner_enter(void)
{
    if (!wifi_power_state_init()) return false;
    wifi_power_state_t *s = s_wifi_power;
    __atomic_add_fetch(&s->lifecycle_pending, 1, __ATOMIC_ACQ_REL);
    for (unsigned n = 0; n < 100; ++n) {
        if (!__atomic_test_and_set(&s->gate, __ATOMIC_ACQUIRE)) return true;
        vTaskDelay(1);
    }
    __atomic_sub_fetch(&s->lifecycle_pending, 1, __ATOMIC_RELEASE);
    return false; /* no unsafe SDK fallback on an undrained operation */
}
static void wifi_power_owner_leave(void)
{
    __atomic_clear(&s_wifi_power->gate, __ATOMIC_RELEASE);
    __atomic_sub_fetch(&s_wifi_power->lifecycle_pending, 1, __ATOMIC_RELEASE);
    power_policy_notify();
}
esp_err_t cym_wifi_init(const wifi_init_config_t *config)
{
    if (!wifi_power_owner_enter()) return ESP_ERR_INVALID_STATE;
    esp_err_t rc = esp_wifi_init(config);
    if (rc == ESP_OK) {
        wifi_power_new_generation();
        __atomic_store_n(&s_wifi_power->active, false, __ATOMIC_RELEASE);
        __atomic_store_n(&s_wifi_power->status, PWR_RADIO_OFF, __ATOMIC_RELEASE);
    }
    wifi_power_owner_leave();
    return rc;
}
esp_err_t cym_wifi_start(void)
{
    if (!wifi_power_owner_enter()) return ESP_ERR_INVALID_STATE;
    esp_err_t rc = esp_wifi_start();
    if (rc == ESP_OK) __atomic_store_n(&s_wifi_power->active, true, __ATOMIC_RELEASE);
    wifi_power_owner_leave();
    return rc;
}
esp_err_t cym_wifi_stop(void)
{
    if (!wifi_power_owner_enter()) return ESP_ERR_INVALID_STATE;
    /* Invalidate BEFORE retirement. A plain stop retains the pre-Max baseline. */
    __atomic_add_fetch(&s_wifi_power->generation, 1, __ATOMIC_ACQ_REL);
    __atomic_store_n(&s_wifi_power->active, false, __ATOMIC_RELEASE);
    __atomic_store_n(&s_wifi_power->applied, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&s_wifi_power->status, PWR_RADIO_OFF, __ATOMIC_RELEASE);
    esp_err_t rc = esp_wifi_stop();
    if (rc != ESP_OK && rc != ESP_ERR_WIFI_NOT_INIT && rc != ESP_ERR_WIFI_NOT_STARTED)
        __atomic_store_n(&s_wifi_power->status, PWR_RADIO_FAILED, __ATOMIC_RELEASE);
    wifi_power_owner_leave();
    return rc;
}
esp_err_t cym_wifi_deinit(void)
{
    if (!wifi_power_owner_enter()) return ESP_ERR_INVALID_STATE;
    __atomic_store_n(&s_wifi_power->active, false, __ATOMIC_RELEASE);
    __atomic_add_fetch(&s_wifi_power->generation, 1, __ATOMIC_ACQ_REL);
    __atomic_store_n(&s_wifi_power->applied, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&s_wifi_power->status, PWR_RADIO_OFF, __ATOMIC_RELEASE);
    /* A failed deinit may retain an overridden driver. Preserve its baseline;
     * only a successful fresh init may reset capture validity. */
    esp_err_t rc = esp_wifi_deinit();
    if (rc != ESP_OK && rc != ESP_ERR_WIFI_NOT_INIT)
        __atomic_store_n(&s_wifi_power->status, PWR_RADIO_FAILED, __ATOMIC_RELEASE);
    wifi_power_owner_leave();
    return rc;
}
/* POWER_WIFI_STATE_END */

pwr_decode_t pwr_decode(pwr_key_rd_t lvl_rd, uint8_t lvl_raw,
                        pwr_key_rd_t leg_rd, uint8_t leg_raw, int ns_open_ok)
{
    pwr_decode_t out = { PWR_LVL_NORMAL, PWR_SRC_FRESH };
    // A settings namespace that will not open is an error, not a fresh install.
    if (!ns_open_ok) { out.src = PWR_SRC_ERROR; return out; }
    if (lvl_rd == PWR_KEY_OK) {
        if (lvl_raw == PWR_LVL_NORMAL || lvl_raw == PWR_LVL_MAX) {
            out.level = (pwr_lvl_t)lvl_raw; out.src = PWR_SRC_EXPLICIT; return out;
        }
        // Low persisted but unsupported in this build, or out-of-range: flag and
        // run Normal; never silently promote to Max.
        out.src = PWR_SRC_ERROR; return out;
    }
    // A bad-type or unreadable new key is NOT proof of a fresh install.
    if (lvl_rd != PWR_KEY_ABSENT) { out.src = PWR_SRC_ERROR; return out; }
    // New key genuinely absent: fall back to the legacy pwr_mode encoding.
    if (leg_rd == PWR_KEY_OK) {
        if (leg_raw == 0) { out.level = PWR_LVL_NORMAL; out.src = PWR_SRC_MIGRATED; return out; }
        if (leg_raw == 1) { out.level = PWR_LVL_MAX;    out.src = PWR_SRC_MIGRATED; return out; }
        // Legacy 2 / unknown: explicit error disposition, not a silent Max.
        out.src = PWR_SRC_ERROR; return out;
    }
    if (leg_rd != PWR_KEY_ABSENT) { out.src = PWR_SRC_ERROR; return out; }
    // Both keys genuinely absent in a readable namespace: documented fresh default.
    out.src = PWR_SRC_FRESH; return out;
}

static esp_err_t wifi_power_apply_level(uint8_t level)
{
    if (level != PWR_LVL_NORMAL && level != PWR_LVL_MAX) return ESP_ERR_INVALID_ARG;
    // Capture the driver's boot-default TX power ONCE, before this call can apply
    // any override, so Normal has a real value to restore to.
    uint32_t generation = __atomic_load_n(&s_wifi_power->generation, __ATOMIC_ACQUIRE);
    if (!s_wifi_power->captured) {
        int8_t cur = 0;
        esp_err_t acquired = esp_wifi_get_max_tx_power(&cur);
        if (acquired != ESP_OK) return acquired;
        if (cur < 8 || cur > 84) return ESP_ERR_INVALID_STATE;
        if (generation != __atomic_load_n(&s_wifi_power->generation, __ATOMIC_ACQUIRE)) return ESP_ERR_INVALID_STATE;
        s_wifi_power->normal = cur; s_wifi_power->captured = true;
    }
    esp_err_t e1, e2;
    if (level == PWR_LVL_MAX) {
        // Max retains the supported project request 82; this is not a target maximum claim.
        // Actual radiated EIRP is still bounded by PHY calibration, antenna design, and
        // country/regulatory settings loaded at runtime.
        e1 = esp_wifi_set_max_tx_power(82);
        e2 = esp_wifi_set_ps(WIFI_PS_NONE);   // disable modem sleep for continuous TX capability
        ESP_LOGI(TAG_PWR, "WiFi TX -> MAX: set_tx(82) rc=%d set_ps(NONE) rc=%d", e1, e2);
    } else {
        // Normal (Low clamps to Normal in this build): actively restore the captured
        // boot-default TX power — leaving a prior Max 82 in place was the v3.0.44 bug.
        e1 = esp_wifi_set_max_tx_power(s_wifi_power->normal);
        e2 = esp_wifi_set_ps(WIFI_PS_MIN_MODEM);  // restore default modem-sleep power save
        ESP_LOGI(TAG_PWR, "WiFi TX -> NORMAL: restore_tx(%d) rc=%d set_ps(MIN_MODEM) rc=%d",
                 (int)s_wifi_power->normal, e1, e2);
    }
    int8_t readback = 0;
    esp_err_t er = esp_wifi_get_max_tx_power(&readback);
    // Quantization is advisory, but a failed/invalid readback is not success.
    return (e1 == ESP_OK && e2 == ESP_OK && er == ESP_OK && readback >= 8 && readback <= 84) ? ESP_OK : ESP_FAIL;
}

esp_err_t wifi_power_apply_requested(uint8_t level)
{
    wifi_power_state_t *s = __atomic_load_n(&s_wifi_power, __ATOMIC_ACQUIRE);
    if (!s || !__atomic_load_n(&s->active, __ATOMIC_ACQUIRE)) return ESP_ERR_INVALID_STATE;
    if (__atomic_load_n(&s->lifecycle_pending, __ATOMIC_ACQUIRE) ||
        __atomic_test_and_set(&s->gate, __ATOMIC_ACQUIRE)) return ESP_ERR_TIMEOUT;
    if (!__atomic_load_n(&s->active, __ATOMIC_ACQUIRE)) {
        __atomic_clear(&s->gate, __ATOMIC_RELEASE);
        return ESP_ERR_INVALID_STATE;
    }
    uint32_t generation = __atomic_load_n(&s->generation, __ATOMIC_ACQUIRE);
    esp_err_t rc = wifi_power_apply_level(level);
    if (generation != __atomic_load_n(&s->generation, __ATOMIC_ACQUIRE)) rc = ESP_ERR_INVALID_STATE;
    __atomic_store_n(&s->applied, rc == ESP_OK ? level : 0, __ATOMIC_RELEASE);
    __atomic_store_n(&s->status, rc == ESP_OK ? PWR_RADIO_APPLIED : PWR_RADIO_FAILED, __ATOMIC_RELEASE);
    __atomic_clear(&s->gate, __ATOMIC_RELEASE);
    return rc == ESP_OK ? ESP_OK : ESP_FAIL;
}
esp_err_t apply_wifi_power_settings(void)
{
    /* Existing owner hooks now only signal the off-UI worker. */
    power_policy_notify();
    return ESP_ERR_TIMEOUT;
}

const char* authmode_to_string(wifi_auth_mode_t mode) {
    switch (mode) {
        case WIFI_AUTH_OPEN: return "Open";
        case WIFI_AUTH_WEP: return "WEP";
        case WIFI_AUTH_WPA_PSK: return "WPA_PSK";
        case WIFI_AUTH_WPA2_PSK: return "WPA2_PSK";
        case WIFI_AUTH_WPA_WPA2_PSK: return "WPA/WPA2_PSK";
        case WIFI_AUTH_WPA2_ENTERPRISE: return "WPA2_ENTERPRISE";
        case WIFI_AUTH_WPA3_PSK: return "WPA3_PSK";
        case WIFI_AUTH_WPA2_WPA3_PSK: return "WPA2/WPA3_PSK";
        case WIFI_AUTH_WAPI_PSK: return "WAPI_PSK";
        default: return "Unknown";
    }
}

void escape_csv_field(const char* input, char* output, size_t output_size) {
    size_t i = 0, j = 0;
    bool needs_quotes = false;

    if (!input || !output || output_size < 3) return;

    // Neutralize control chars (CR/LF/TAB/etc.) to a space: an unescaped CR or LF in
    // an SSID/name splits the CSV row across two physical lines, which silently drops
    // that network on WiGLE/WDGWars upload (observed on DE->TR wardrive: vehicle
    // "R-MDVR" DVR APs broadcast an SSID ending in a raw CR -> 47 networks lost).
    // WiGLE's own client replaces bad chars rather than preserving them, so match that.
    // Only ',' and '"' still require RFC 4180 quoting (control chars become spaces).
    for (i = 0; input[i] != '\0'; i++) {
        if (input[i] == ',' || input[i] == '"') {
            needs_quotes = true;
            break;
        }
    }

    if (needs_quotes) {
        output[j++] = '"';
        for (i = 0; input[i] != '\0' && j < output_size - 3; i++) {
            unsigned char c = (unsigned char)input[i];
            if (c < 0x20) c = ' ';
            if (c == '"') {
                output[j++] = '"';
                output[j++] = '"';
            } else {
                output[j++] = (char)c;
            }
        }
        output[j++] = '"';
        output[j] = '\0';
    } else {
        for (i = 0; input[i] != '\0' && j < output_size - 1; i++) {
            unsigned char c = (unsigned char)input[i];
            output[j++] = (c < 0x20) ? ' ' : (char)c;
        }
        output[j] = '\0';
    }
}

bool is_multicast_mac(const uint8_t *mac) {
    return (mac[0] & 0x01) != 0;
}

bool is_broadcast_bssid(const uint8_t *bssid) {
    return (bssid[0] == 0xFF && bssid[1] == 0xFF && bssid[2] == 0xFF &&
            bssid[3] == 0xFF && bssid[4] == 0xFF && bssid[5] == 0xFF);
}

bool is_own_device_mac(const uint8_t *mac) {
    uint8_t own_mac[6];
    esp_wifi_get_mac(WIFI_IF_STA, own_mac);
    return memcmp(mac, own_mac, 6) == 0;
}
