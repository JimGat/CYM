#include <stdatomic.h>
// wifi_scanner.c - WiFi Network Scanner
#include "wifi_scanner.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_timer.h"
#include "esp_attr.h"
#include <string.h>

// Application diagnostic hook: debug-gated, no payload/address logging.
extern void cym_debug_memory_snapshot(const char *where);

static const char *TAG = "wifi_scanner";

// Scanner state (local)
static _Atomic bool g_scan_in_progress = false;
static _Atomic bool g_scan_done = false;
// Monotonic scan tickets distinguish a completed scan from a new UI session.
// The event loop invokes scanner then UI callbacks serially; retain the completed
// ticket even if the UI starts another scan between those callbacks.
static _Atomic uint32_t g_scan_generation;
static _Atomic uint32_t g_scan_completed_generation;
static _Atomic int g_scan_result_status;
esp_err_t wifi_scanner_result_status(void){return atomic_load(&g_scan_result_status);}
uint32_t wifi_scanner_scan_generation(void){return atomic_load(&g_scan_generation);}
uint32_t wifi_scanner_completed_generation(void){return atomic_load(&g_scan_completed_generation);}


// Shared scan results (defined in wifi_common.c, used by other components)
EXT_RAM_BSS_ATTR wifi_ap_record_t g_shared_scan_results[MAX_SCAN_RESULTS];
uint16_t g_shared_scan_count = 0;
EXT_RAM_BSS_ATTR int g_shared_selected_indices[MAX_SCAN_RESULTS];
int g_shared_selected_count = 0;

// Target BSSID monitoring (for deauth attacks)
static target_bssid_t target_bssids[MAX_TARGET_BSSIDS];
static int target_bssid_count = 0;

// Configurable active scan time per channel (set via wifi_scanner_set_scan_time)
static uint16_t g_scan_time_min = 100;  // default
static uint16_t g_scan_time_max = 300;  // default

// WiFi event handler (for scan completion)
static void wifi_scanner_event_handler(void *arg, esp_event_base_t event_base,
                                      int32_t event_id, void *event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_SCAN_DONE) {
        if (!g_scan_in_progress) return; // duplicate/unowned SDK completion
        const wifi_event_sta_scan_done_t *done = event_data;
        esp_err_t status = done && done->status ? ESP_FAIL : ESP_OK;
        uint16_t number = 0;
        if (status == ESP_OK) status = esp_wifi_scan_get_ap_num(&number);
        g_shared_scan_count = (number > MAX_SCAN_RESULTS) ? MAX_SCAN_RESULTS : number;
        if (status == ESP_OK && g_shared_scan_count > 0)
            status = esp_wifi_scan_get_ap_records(&g_shared_scan_count, g_shared_scan_results);
        if (status != ESP_OK) {
            g_shared_scan_count = 0;
            esp_wifi_clear_ap_list();
        }
        atomic_store(&g_scan_result_status, status);
        // Release publication follows all record reads; UI must match its ticket.
        atomic_store(&g_scan_completed_generation, atomic_load(&g_scan_generation));
        g_scan_done = true;
        cym_debug_memory_snapshot("wifi-scan-complete");
        unsigned band2 = 0, band5 = 0;
        for (unsigned i = 0; i < g_shared_scan_count; ++i) {
            if (g_shared_scan_results[i].primary <= 14) ++band2;
            else ++band5;
        }
        ESP_LOGI(TAG, "Scan done: generation=%lu status=%d driver_records=%u retained=%u 2g=%u 5g=%u",
                 (unsigned long)atomic_load(&g_scan_completed_generation), status,
                 number, g_shared_scan_count, band2, band5);
        g_scan_in_progress = false;
    }
}

esp_err_t wifi_scanner_init(void) {
    // Guard: only register once regardless of how many times this is called.
    // wifi_cli_init() and main.c both call this; duplicate registrations each
    // consume ~60 B of internal heap permanently and cause double result reads.
    static bool s_handler_registered = false;
    if (!s_handler_registered) {
        esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_SCAN_DONE,
                                   &wifi_scanner_event_handler, NULL);
        s_handler_registered = true;
    }
    return ESP_OK;
}

static void wifi_scanner_log_acquisition(void) {
    wifi_country_t country = {0};
    esp_err_t rc = esp_wifi_get_country(&country);
#if CONFIG_SOC_WIFI_SUPPORT_5G
    wifi_band_mode_t mode = WIFI_BAND_MODE_AUTO;
    esp_err_t band_rc = esp_wifi_get_band_mode(&mode);
    ESP_LOGI(TAG, "acquisition country_rc=%d cc=%.2s policy=%d 2g=%u+%u mask5=0x%lx band_rc=%d mode=%d bitmap=default-regulatory",
             rc, country.cc, country.policy, country.schan, country.nchan,
             (unsigned long)country.wifi_5g_channel_mask, band_rc, mode);
#else
    ESP_LOGI(TAG, "acquisition country_rc=%d cc=%.2s policy=%d 2g=%u+%u 5g=unsupported",
             rc, country.cc, country.policy, country.schan, country.nchan);
#endif
}

esp_err_t wifi_scanner_start_scan(void) {
    if (atomic_exchange(&g_scan_in_progress, true)) {
        ESP_LOGW(TAG, "Scan already in progress");
        return ESP_ERR_INVALID_STATE;
    }
    
#if CONFIG_SOC_WIFI_SUPPORT_5G
    // Prior connection features may leave 2G_ONLY selected. These APIs request
    // all permitted bands; AUTO changes capability, not country/channel permission.
    esp_err_t band_rc = esp_wifi_set_band_mode(WIFI_BAND_MODE_AUTO);
    if (band_rc != ESP_OK) { g_scan_in_progress = false; return band_rc; }
#endif
    wifi_scan_config_t scan_cfg = {
        .ssid = NULL,
        .bssid = NULL,
        .channel = 0,
        .show_hidden = true,
        .scan_type = WIFI_SCAN_TYPE_ACTIVE,
        .scan_time.active.min = g_scan_time_min,
        .scan_time.active.max = g_scan_time_max,
        // DFS 5GHz channels (52-144, most of the 5GHz band) can't be actively probed - the
        // driver forces them to passive listen-only regardless of scan_type ACTIVE here, per
        // regulatory radar-avoidance rules (same constraint cym_rf_tx.h documents for TX).
        // Leaving scan_time.passive unset (implicit 0 from this designated initializer) put
        // those channels' dwell time in the hands of whatever "0 means" a closed-source driver
        // blob decides, instead of IDF's own documented default (WIFI_PASSIVE_SCAN_DEFAULT_TIME,
        // esp_wifi_types_generic.h) - asserting it explicitly removes that ambiguity. Field
        // report 2026-09-23: "WiFi Scan and Attack barely picked up my 5G AP's".
        .scan_time.passive = WIFI_PASSIVE_SCAN_DEFAULT_TIME,
    };
    
    atomic_fetch_add(&g_scan_generation,1);
    g_scan_in_progress = true;
    g_scan_done = false;
    g_shared_scan_count = 0;
    
    ESP_LOGI(TAG, "Starting WiFi scan...");
    wifi_scanner_log_acquisition();
    cym_debug_memory_snapshot("wifi-scan-start");
    esp_err_t ret = esp_wifi_scan_start(&scan_cfg, false);
    if (ret == ESP_ERR_TIMEOUT) {
        // P5: esp_wifi_scan_start() can return ESP_ERR_TIMEOUT transiently, notably a dual-band
        // scan while the BT controller is active (IDF #16059). Retry once before giving up so a
        // one-off coex hiccup doesn't leave the user staring at an empty AP list. Harmless if
        // the running IDF already fixed #16059 (the retry simply never triggers).
        ESP_LOGW(TAG, "scan_start ESP_ERR_TIMEOUT - retrying once");
        vTaskDelay(pdMS_TO_TICKS(60));
        ret = esp_wifi_scan_start(&scan_cfg, false);
    }

    cym_debug_memory_snapshot("wifi-scan-start-return");
    if (ret != ESP_OK) {
        g_scan_in_progress = false;
        ESP_LOGE(TAG, "Failed to start scan: %s", esp_err_to_name(ret));
        return ret;
    }
    
    return ESP_OK;
}

esp_err_t wifi_scanner_start_passive_scan(uint32_t per_channel_ms) {
    if (atomic_exchange(&g_scan_in_progress, true)) {
        ESP_LOGW(TAG, "Scan already in progress");
        return ESP_ERR_INVALID_STATE;
    }

    if (per_channel_ms > 1500) per_channel_ms = 1500;

#if CONFIG_SOC_WIFI_SUPPORT_5G
    // Prior connection features may leave 2G_ONLY selected. These APIs request
    // all permitted bands; AUTO changes capability, not country/channel permission.
    esp_err_t band_rc = esp_wifi_set_band_mode(WIFI_BAND_MODE_AUTO);
    if (band_rc != ESP_OK) { g_scan_in_progress = false; return band_rc; }
#endif
    wifi_scan_config_t scan_cfg = {
        .ssid = NULL,
        .bssid = NULL,
        .channel = 0,
        .show_hidden = true,
        .scan_type = WIFI_SCAN_TYPE_PASSIVE,
        .scan_time.passive = per_channel_ms,
    };

    atomic_fetch_add(&g_scan_generation,1);
    g_scan_in_progress = true;
    g_scan_done = false;
    g_shared_scan_count = 0;

    ESP_LOGI(TAG, "Starting passive WiFi scan (%lu ms/channel)...", (unsigned long)per_channel_ms);
    wifi_scanner_log_acquisition();
    cym_debug_memory_snapshot("wifi-scan-start");
    esp_err_t ret = esp_wifi_scan_start(&scan_cfg, false);
    if (ret == ESP_ERR_TIMEOUT) {
        // P5: retry once on a transient coex ESP_ERR_TIMEOUT (IDF #16059). See the active-scan
        // path above for the rationale; harmless if the running IDF already fixed it.
        ESP_LOGW(TAG, "passive scan_start ESP_ERR_TIMEOUT - retrying once");
        vTaskDelay(pdMS_TO_TICKS(60));
        ret = esp_wifi_scan_start(&scan_cfg, false);
    }

    cym_debug_memory_snapshot("wifi-scan-start-return");
    if (ret != ESP_OK) {
        g_scan_in_progress = false;
        ESP_LOGE(TAG, "Failed to start passive scan: %s", esp_err_to_name(ret));
        return ret;
    }

    return ESP_OK;
}

// One bounded task-context copy; a new scan cannot clear/replace this ticket's data.
esp_err_t wifi_scanner_copy_completed(uint32_t ticket, wifi_ap_record_t *results,
                                      uint16_t capacity, uint16_t *count, bool *busy) {
    if (!busy) return ESP_ERR_INVALID_ARG;
    *busy = false;
    if (!results || !count) return ESP_ERR_INVALID_ARG;
    *count = 0;
    if (atomic_exchange(&g_scan_in_progress, true)) {
        *busy = true;
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t rc = ESP_ERR_INVALID_STATE;
    if (g_scan_done && ticket == atomic_load(&g_scan_completed_generation)) {
        rc = atomic_load(&g_scan_result_status);
        if (rc == ESP_OK) {
            *count = g_shared_scan_count < capacity ? g_shared_scan_count : capacity;
            memcpy(results, g_shared_scan_results, *count * sizeof(*results));
        }
    }
    g_scan_in_progress = false;
    return rc;
}

int wifi_scanner_get_results(wifi_ap_record_t *results, uint16_t max_results) {
    if (!results) return 0;
    
    uint16_t count = (g_shared_scan_count > max_results) ? max_results : g_shared_scan_count;
    memcpy(results, g_shared_scan_results, count * sizeof(wifi_ap_record_t));
    
    return count;
}

uint16_t wifi_scanner_get_count(void) {
    return g_shared_scan_count;
}

bool wifi_scanner_is_scanning(void) {
    return g_scan_in_progress;
}

bool wifi_scanner_is_done(void) {
    return g_scan_done;
}

void wifi_scanner_abort(void) {
    if (g_scan_in_progress) {
        /* ESP-IDF posts SCAN_DONE for a stopped asynchronous scan. Keep
         * admission closed until that event has consumed A's result and ticket;
         * otherwise a start B can relabel the queued completion of A as B.
         * Do not wait here: abort can be called with the UI lock held. A caller
         * may retry after the event loop retires the in-flight scan. */
        esp_wifi_scan_stop();
    }
    g_scan_done = false;
}

esp_err_t wifi_scanner_select_network(int index, bool selected) {
    if (index < 0 || index >= g_shared_scan_count) {
        return ESP_ERR_INVALID_ARG;
    }
    
    if (selected) {
        // Add to selection
        bool already_selected = false;
        for (int i = 0; i < g_shared_selected_count; i++) {
            if (g_shared_selected_indices[i] == index) {
                already_selected = true;
                break;
            }
        }
        
        if (!already_selected && g_shared_selected_count < 20) {
            g_shared_selected_indices[g_shared_selected_count++] = index;
        }
    } else {
        // Remove from selection
        for (int i = 0; i < g_shared_selected_count; i++) {
            if (g_shared_selected_indices[i] == index) {
                for (int j = i; j < g_shared_selected_count - 1; j++) {
                    g_shared_selected_indices[j] = g_shared_selected_indices[j + 1];
                }
                g_shared_selected_count--;
                break;
            }
        }
    }
    
    return ESP_OK;
}

int wifi_scanner_get_selected(int *indices, int max_indices) {
    if (!indices) return 0;
    
    int count = (g_shared_selected_count > max_indices) ? max_indices : g_shared_selected_count;
    memcpy(indices, g_shared_selected_indices, count * sizeof(int));
    
    return count;
}

int wifi_scanner_get_selected_count(void) {
    return g_shared_selected_count;
}

void wifi_scanner_print_results(void) {
    if (g_shared_scan_count == 0) {
        MY_LOG_INFO(TAG, "No networks found");
        return;
    }
    
    MY_LOG_INFO(TAG, "");
    MY_LOG_INFO(TAG, "Index,BSSID,SSID,Auth,Channel,RSSI");
    
    for (int i = 0; i < g_shared_scan_count; i++) {
        wifi_ap_record_t *ap = &g_shared_scan_results[i];
        
        char ssid_escaped[128];
        escape_csv_field((const char*)ap->ssid, ssid_escaped, sizeof(ssid_escaped));
        
        ESP_LOGI("scanner", "%d,%02X:%02X:%02X:%02X:%02X:%02X,%s,%s,%d,%d",
               i,
               ap->bssid[0], ap->bssid[1], ap->bssid[2],
               ap->bssid[3], ap->bssid[4], ap->bssid[5],
               ssid_escaped,
               authmode_to_string(ap->authmode),
               ap->primary,
               ap->rssi);
    }
    
    MY_LOG_INFO(TAG, "Total networks: %d", g_shared_scan_count);
}

// Save selected network BSSIDs to target list
void wifi_scanner_save_target_bssids(void) {
    target_bssid_count = 0;
    
    for (int i = 0; i < g_shared_selected_count && target_bssid_count < MAX_TARGET_BSSIDS; i++) {
        int idx = g_shared_selected_indices[i];
        if (idx >= 0 && idx < g_shared_scan_count) {
            memcpy(target_bssids[target_bssid_count].bssid, 
                   g_shared_scan_results[idx].bssid, 6);
            // Copy SSID
            strncpy(target_bssids[target_bssid_count].ssid, 
                   (const char *)g_shared_scan_results[idx].ssid, 32);
            target_bssids[target_bssid_count].ssid[32] = '\0';
            target_bssids[target_bssid_count].channel = g_shared_scan_results[idx].primary;
            target_bssids[target_bssid_count].last_seen = esp_timer_get_time() / 1000;
            target_bssids[target_bssid_count].active = true;
            target_bssid_count++;
        }
    }
    
    ESP_LOGI(TAG, "Saved %d target BSSIDs", target_bssid_count);
}

// Get target BSSID list
int wifi_scanner_get_targets(target_bssid_t *targets, int max_targets) {
    if (!targets) return 0;
    
    int count = (target_bssid_count > max_targets) ? max_targets : target_bssid_count;
    memcpy(targets, target_bssids, count * sizeof(target_bssid_t));
    
    return count;
}

int wifi_scanner_get_target_count(void) {
    return target_bssid_count;
}

// Quick channel scan for specific targets
void wifi_scanner_quick_channel_scan(void) {
    if (target_bssid_count == 0) {
        ESP_LOGW(TAG, "No targets to scan");
        return;
    }
    
    // Check channels where targets were last seen
    for (int i = 0; i < target_bssid_count; i++) {
        if (!target_bssids[i].active) continue;
        
        uint8_t channel = target_bssids[i].channel;
        esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE);
        vTaskDelay(pdMS_TO_TICKS(100));
        
        // Mark as seen (timestamp updated by sniffer callback)
        target_bssids[i].last_seen = esp_timer_get_time() / 1000;
    }
}

// Check if target is still active
bool wifi_scanner_is_target_active(const uint8_t *bssid) {
    for (int i = 0; i < target_bssid_count; i++) {
        if (memcmp(target_bssids[i].bssid, bssid, 6) == 0) {
            return target_bssids[i].active;
        }
    }
    return false;
}

// Update target last seen time
void wifi_scanner_update_target_seen(const uint8_t *bssid) {
    for (int i = 0; i < target_bssid_count; i++) {
        if (memcmp(target_bssids[i].bssid, bssid, 6) == 0) {
            target_bssids[i].last_seen = esp_timer_get_time() / 1000;
            target_bssids[i].active = true;
            break;
        }
    }
}

// Clear all targets
void wifi_scanner_clear_targets(void) {
    target_bssid_count = 0;
    ESP_LOGI(TAG, "Cleared all targets");
}

// Clear all network selections
void wifi_scanner_clear_selections(void) {
    g_shared_selected_count = 0;
    memset(g_shared_selected_indices, 0, sizeof(g_shared_selected_indices));
    ESP_LOGI(TAG, "Cleared all network selections");
}

const wifi_ap_record_t *wifi_scanner_get_results_ptr(void)
{
    return g_shared_scan_results;
}

const uint16_t *wifi_scanner_get_count_ptr(void)
{
    return &g_shared_scan_count;
}

void wifi_scanner_set_scan_time(uint16_t min_ms, uint16_t max_ms)
{
    if (min_ms < 50)  min_ms = 50;
    if (max_ms > 1000) max_ms = 1000;
    if (min_ms > max_ms) min_ms = max_ms;
    g_scan_time_min = min_ms;
    g_scan_time_max = max_ms;
    ESP_LOGI(TAG, "Scan time set: min=%u max=%u ms", min_ms, max_ms);
}

