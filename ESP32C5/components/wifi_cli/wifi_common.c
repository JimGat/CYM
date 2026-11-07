// wifi_common.c - Common helper functions
#include "wifi_common.h"
#include "esp_wifi.h"
#include "esp_log.h"
#include <string.h>

static const char *TAG_PWR = "power";

// Global variables (defined once, extern in header)
led_strip_handle_t g_led_strip = NULL;
volatile app_state_t g_app_state = APP_STATE_IDLE;
volatile bool g_operation_stop_requested = false;
bool g_max_power_mode = false;  // default Normal; persisted in NVS by main.c
uint8_t g_pwr_lvl = PWR_LVL_NORMAL;  // authoritative level; g_max_power_mode mirrors MAX

// Boot-default Wi-Fi TX power, captured once before any override so Normal can
// restore it (a getter read after Max has been applied cannot recover it).
static bool   s_wifi_tx_captured = false;
static int8_t s_wifi_tx_default  = 0;

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

esp_err_t apply_wifi_power_settings(void)
{
    // Capture the driver's boot-default TX power ONCE, before this call can apply
    // any override, so Normal has a real value to restore to.
    if (!s_wifi_tx_captured) {
        int8_t cur = 0;
        if (esp_wifi_get_max_tx_power(&cur) == ESP_OK) { s_wifi_tx_default = cur; s_wifi_tx_captured = true; }
    }
    esp_err_t e1, e2;
    if (g_pwr_lvl == PWR_LVL_MAX) {
        // 82 is the highest TX power value accepted by the IDF API (~20.5 dBm nominal).
        // Actual radiated EIRP is still bounded by PHY calibration, antenna design, and
        // country/regulatory settings loaded at runtime.
        e1 = esp_wifi_set_max_tx_power(82);
        e2 = esp_wifi_set_ps(WIFI_PS_NONE);   // disable modem sleep for continuous TX capability
        ESP_LOGI(TAG_PWR, "WiFi TX -> MAX: set_tx(82) rc=%d set_ps(NONE) rc=%d", e1, e2);
    } else {
        // Normal (Low clamps to Normal in this build): actively restore the captured
        // boot-default TX power — leaving a prior Max 82 in place was the v3.0.44 bug.
        e1 = s_wifi_tx_captured ? esp_wifi_set_max_tx_power(s_wifi_tx_default) : ESP_OK;
        e2 = esp_wifi_set_ps(WIFI_PS_MIN_MODEM);  // restore default modem-sleep power save
        ESP_LOGI(TAG_PWR, "WiFi TX -> NORMAL: restore_tx(%d) rc=%d set_ps(MIN_MODEM) rc=%d",
                 (int)s_wifi_tx_default, e1, e2);
    }
    return (e1 == ESP_OK && e2 == ESP_OK) ? ESP_OK : ESP_FAIL;
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
