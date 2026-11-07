#ifndef WIFI_COMMON_H
#define WIFI_COMMON_H

#include <stdint.h>
#include <stdbool.h>
#include "esp_wifi.h"
#include "esp_wifi_types.h"
#include "led_strip.h"
#include "board_hal.h"

#ifdef __cplusplus
extern "C" {
#endif

// Version — defined by CMakeLists.txt (PROJECT_VER) and injected as a compile
// definition.  Edit the version in CMakeLists.txt only; do not hardcode here.
#ifndef FW_VERSION
#define FW_VERSION "unknown"
#endif

// Maximum limits — reduced on no-PSRAM boards to fit in internal DRAM
#if defined(CONFIG_BOARD_HAS_PSRAM)
#define MAX_AP_CNT       128
#define MAX_SCAN_RESULTS 128
#else
#define MAX_AP_CNT        16
#define MAX_SCAN_RESULTS  16
#endif
#define MAX_PROBES 200
#if CONFIG_BOARD_HAS_PSRAM
#define MAX_CLIENTS_PER_AP 50
#define MAX_SNIFFER_APS 100
#define MAX_PROBE_REQUESTS 200
#else
// Bounded Classic observer working set; buffers + task fit without PSRAM.
#define MAX_CLIENTS_PER_AP 8
#define MAX_SNIFFER_APS 8
#define MAX_PROBE_REQUESTS 16
#endif
#define MAX_TARGET_BSSIDS 50
#define MAX_WHITELIST_ENTRIES 150
#define DNS_PORT 53
#define DNS_MAX_PACKET_SIZE 512
#define MAX_HTML_FILES 20
#define MAX_HTML_FILENAME 64

// GPIO pins — all board-variant values come from board_hal.h
#define NEOPIXEL_GPIO BOARD_RGB_LED_GPIO   // WS2812 data pin (-1 = not present)
#define LED_COUNT     BOARD_RGB_LED_COUNT  // number of LEDs in the strip
#define RMT_RES_HZ    (10 * 1000 * 1000)

// GPS UART pins — board-variant. Guard: BOARD_GPS_TX_GPIO == -1 means no GPS.
#define GPS_UART_NUM BOARD_GPS_UART_NUM
#define GPS_TX_PIN   BOARD_GPS_TX
#define GPS_RX_PIN   BOARD_GPS_RX
#define GPS_BUF_SIZE 1024

// SD Card SPI pins — board-variant via board_hal.h BOARD_SD_* defines.
// On shared-bus boards (NM-CYD-C5, WS-C5-28) BOARD_SD_SCK/MOSI/MISO alias
// the main SPI bus pins. On CYD2USB the SD has its own HSPI bus.
#include "sdkconfig.h"
#define SD_MISO_PIN  BOARD_SD_MISO
#define SD_MOSI_PIN  BOARD_SD_MOSI
#define SD_CLK_PIN   BOARD_SD_SCK
#define SD_CS_PIN    BOARD_SD_CS

// Application states
typedef enum {
    APP_STATE_IDLE = 0,
    APP_STATE_DEAUTH,
    APP_STATE_DEAUTH_EVIL_TWIN,
    APP_STATE_EVIL_TWIN_PASS_CHECK,
    APP_STATE_DRAGON_DRAIN,
    APP_STATE_SAE_OVERFLOW,
    APP_STATE_BLACKOUT,
    APP_STATE_KARMA,
    APP_STATE_PORTAL,
    APP_STATE_SNIFFER,
    APP_STATE_SNIFFER_DOG,
    APP_STATE_WARDRIVE
} app_state_t;

// Scan result structure
typedef struct {
    uint8_t bssid[6];
    char ssid[33];
    uint8_t channel;
    wifi_auth_mode_t authmode;
    int rssi;
    bool selected;
} scan_result_t;

// Probe request structure
typedef struct {
    uint8_t mac[6];
    char ssid[33];
    int rssi;
    uint32_t last_seen;
} probe_request_t;

// Sniffer client structure
typedef struct {
    uint8_t mac[6];
    int rssi;
    uint32_t last_seen;
} sniffer_client_t;

// Client info structure (alias for compatibility)
typedef sniffer_client_t client_info_t;

// Sniffer AP structure
typedef struct {
    uint8_t bssid[6];
    char ssid[33];
    uint8_t channel;
    wifi_auth_mode_t authmode;
    int rssi;
    sniffer_client_t clients[MAX_CLIENTS_PER_AP];
    int client_count;
    uint32_t last_seen;
} sniffer_ap_t;

// GPS data structure
typedef struct {
    float latitude;
    float longitude;
    float altitude;
    float accuracy;
    int satellites;
    bool valid;
    char time_utc[10];  /* "HH:MM:SS" from GGA field 1, empty if no fix */
    float speed;        /* ground speed in m/s from RMC field 7 (SOG, knots->m/s); 0 when no fix */
} gps_data_t;

// Target BSSID structure
typedef struct {
    uint8_t bssid[6];
    char ssid[33];
    uint8_t channel;
    uint32_t last_seen;
    bool active;
} target_bssid_t;

// Global LED strip handle (shared across components)
extern led_strip_handle_t g_led_strip;

// Global application state (shared across components)
extern volatile app_state_t g_app_state;

// Global stop flag (shared across components)
extern volatile bool g_operation_stop_requested;

// Global TX power mode flag (shared across all WiFi/BLE components)
// Mirrors (g_pwr_lvl == PWR_LVL_MAX); kept for existing Max-only readers.
extern bool g_max_power_mode;

// ── Package D: TX power level (Low reserved, Normal/Max active this build) ────
/* >>> CYM_PWR_DECODE_TYPES_BEGIN  (extracted verbatim by tests/run_pwr_decode_host.py) */
typedef enum { PWR_LVL_LOW = 0, PWR_LVL_NORMAL = 1, PWR_LVL_MAX = 2 } pwr_lvl_t;
/* Per-key NVS read outcome, mapped by the caller from the raw esp_err_t. */
typedef enum { PWR_KEY_OK = 0, PWR_KEY_ABSENT = 1, PWR_KEY_BADTYPE = 2, PWR_KEY_READERR = 3 } pwr_key_rd_t;
/* Provenance of the decoded level (drives truthful logging / error surfacing). */
typedef enum { PWR_SRC_FRESH = 0, PWR_SRC_EXPLICIT = 1, PWR_SRC_MIGRATED = 2, PWR_SRC_ERROR = 3 } pwr_src_t;
typedef struct { pwr_lvl_t level; pwr_src_t src; } pwr_decode_t;
/* <<< CYM_PWR_DECODE_TYPES_END */

// Authoritative tri-state TX power level (PWR_LVL_*). g_max_power_mode mirrors MAX.
extern uint8_t g_pwr_lvl;

// Pure migration/decode of the persisted level — NO I/O. The caller maps each
// key's esp_err_t to a pwr_key_rd_t and reports whether the settings namespace
// opened. Fresh (both keys genuinely absent) -> Normal; a bad-type / unreadable
// key or a legacy 2/unknown value is flagged PWR_SRC_ERROR and defaults to Normal
// (never a silent promotion to Max); Low persisted but unsupported is likewise
// flagged and run as Normal.
pwr_decode_t pwr_decode(pwr_key_rd_t lvl_rd, uint8_t lvl_raw,
                        pwr_key_rd_t leg_rd, uint8_t leg_raw, int ns_open_ok);

// Legacy initialization hook: notify the off-UI policy worker, returning deferred.
// No getters/setters here. Explicit lifecycle adapters below share operation
// admission with wifi_power_apply_requested; plain restart retains the Normal
// baseline, while successful full init starts a new capture generation.
esp_err_t apply_wifi_power_settings(void);
void wifi_power_new_generation(void);
enum { PWR_RADIO_OFF = 0, PWR_RADIO_BUSY = 1, PWR_RADIO_FAILED = 2, PWR_RADIO_APPLIED = 3 };
uint8_t wifi_power_status(void);
esp_err_t wifi_power_apply_requested(uint8_t level);
void power_policy_notify(void);
esp_err_t cym_wifi_init(const wifi_init_config_t *config);
esp_err_t cym_wifi_start(void);
esp_err_t cym_wifi_stop(void);
esp_err_t cym_wifi_deinit(void);
uint8_t wifi_power_applied_level(void); // 0 means unknown/failed/deferred

// Shared scan results (from wifi_scanner, used by attacks/sniffer)
extern wifi_ap_record_t g_shared_scan_results[MAX_SCAN_RESULTS];
extern uint16_t g_shared_scan_count;
extern int g_shared_selected_indices[MAX_SCAN_RESULTS];
extern int g_shared_selected_count;

// Helper macros
#include "esp_log.h"
#define MY_LOG_INFO(tag, fmt, ...) ESP_LOGI(tag, fmt, ##__VA_ARGS__)

// Common helper functions
const char* authmode_to_string(wifi_auth_mode_t mode);
void escape_csv_field(const char* input, char* output, size_t output_size);
bool is_multicast_mac(const uint8_t *mac);
bool is_broadcast_bssid(const uint8_t *bssid);
bool is_own_device_mac(const uint8_t *mac);

#ifdef __cplusplus
}
#endif

#endif // WIFI_COMMON_H

