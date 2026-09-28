// CYM Timekeeper — GPS-disciplined UTC with RTC holdover.
// State machine: UNSYNCED -> GPS_ACQUIRING -> GPS_LOCKED -> RTC_HOLDOVER.
// Uses monotonic time for intervals, wall clock for calendar/NTP.

#include "cym_timekeeper.h"
#include "pcf85063.h"
#include "board_hal.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <string.h>
#include <math.h>
#include <stdlib.h>

static const char *TAG = "timekeeper";

// ── Tuning constants ────────────────────────────────────────────────────────

// Number of consecutive valid 1-second GPS samples required for lock
#define GPS_LOCK_SAMPLES        3

// Initial GPS UART uncertainty (microseconds) — conservative before
// physical characterization. 500ms covers UART latency, sentence jitter,
// scheduling delay, and parse overhead.
#define GPS_UART_UNCERTAINTY_US 500000
#define NETWORK_UNCERTAINTY_US  250000
#define MIN_REASONABLE_EPOCH    1704067200LL  // 2024-01-01 UTC
#define MAX_REASONABLE_EPOCH    4102444800LL  // 2100-01-01 UTC

// Holdover uncertainty grows at 50 ppm (conservative uncalibrated quartz)
#define HOLDOVER_DRIFT_PPM      50

// RTC write rate limit: no more often than every 10 minutes (600 seconds)
#define RTC_WRITE_INTERVAL_S    600

// Maximum time correction (us) before stepping instead of slewing
#define STEP_THRESHOLD_US       2000000  // 2 seconds

// NVS keys for RTC trust persistence
#define NVS_NAMESPACE           "cym_time"
#define NVS_KEY_RTC_TRUSTED     "rtc_trust"
#define NVS_KEY_LAST_GPS_EPOCH  "last_gps"

// GPS loss timeout: if no valid sample for this long, transition to holdover
#define GPS_LOSS_TIMEOUT_US     (10 * 1000000LL)  // 10 seconds

// Maximum samples between GPS observations before reacquisition
#define MAX_DISCONTINUITY_S     5

// ── Internal state ──────────────────────────────────────────────────────────

static SemaphoreHandle_t s_tk_mutex = NULL;

// Source state machine
static cym_time_source_t s_source = CYM_TIME_UNSYNCED;
static bool s_gps_present = false;
static bool s_gps_fix = false;
static bool s_rtc_valid = false;
static bool s_rtc_trusted = false;

// GPS qualification
static int s_consec_count = 0;
static time_t s_prev_gps_epoch = 0;
static int64_t s_prev_gps_mono_us = 0;

// Discipline tracking
static int64_t s_last_lock_mono_us = 0;
static time_t s_last_gps_sync_epoch = 0;
static int32_t s_last_correction_us = 0;
static uint32_t s_uncertainty_us = 0;
static uint32_t s_holdover_base_uncertainty_us = GPS_UART_UNCERTAINTY_US;
static uint64_t s_holdover_base_age_ms = 0;

// RTC write rate limit
static int64_t s_last_rtc_write_mono_us = 0;
static bool s_rtc_ever_written = false;

// PCF85063A handle (NULL if no RTC on this board)
static pcf85063_handle_t s_rtc = {0};
static bool s_has_rtc = false;

// ── NVS helpers ─────────────────────────────────────────────────────────────

static void persist_trust(void)
{
    nvs_handle_t h;
    if (nvs_open(NVS_NAMESPACE, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_u8(h, NVS_KEY_RTC_TRUSTED, s_rtc_trusted ? 1 : 0);
        nvs_set_i64(h, NVS_KEY_LAST_GPS_EPOCH, (int64_t)s_last_gps_sync_epoch);
        nvs_commit(h);
        nvs_close(h);
    }
}

static void load_trust(void)
{
    nvs_handle_t h;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &h) == ESP_OK) {
        uint8_t trusted = 0;
        nvs_get_u8(h, NVS_KEY_RTC_TRUSTED, &trusted);
        s_rtc_trusted = (trusted != 0);
        int64_t epoch = 0;
        nvs_get_i64(h, NVS_KEY_LAST_GPS_EPOCH, &epoch);
        s_last_gps_sync_epoch = (time_t)epoch;
        nvs_close(h);
    }
}

// ── Discipline helpers ──────────────────────────────────────────────────────

static void step_clock(time_t epoch)
{
    struct timeval tv = { .tv_sec = epoch, .tv_usec = 0 };
    settimeofday(&tv, NULL);
    ESP_LOGI(TAG, "Clock stepped to epoch %ld", (long)epoch);
}

static void slew_clock(int32_t correction_us)
{
    struct timeval delta = {
        .tv_sec = correction_us / 1000000,
        .tv_usec = correction_us % 1000000,
    };
    adjtime(&delta, NULL);
    ESP_LOGI(TAG, "Clock slewed by %d us", (int)correction_us);
}

static void write_rtc_if_due(time_t epoch, int64_t now_mono_us)
{
    if (!s_has_rtc) return;

    // Rate limit: first write always goes through, then no more than every 10 min
    if (s_rtc_ever_written &&
        (now_mono_us - s_last_rtc_write_mono_us) < (int64_t)RTC_WRITE_INTERVAL_S * 1000000LL) {
        return;
    }

    struct tm t;
    gmtime_r(&epoch, &t);
    if (pcf85063_write_time(&s_rtc, &t) == ESP_OK) {
        s_last_rtc_write_mono_us = now_mono_us;
        s_rtc_ever_written = true;
        s_rtc_trusted = true;
        s_last_gps_sync_epoch = epoch;
        s_rtc_valid = true;
        persist_trust();
        ESP_LOGI(TAG, "RTC updated from disciplined UTC source");
    }
}

// ── Public API ──────────────────────────────────────────────────────────────

esp_err_t cym_timekeeper_init(i2c_master_bus_handle_t bus)
{
    s_tk_mutex = xSemaphoreCreateMutex();
    if (!s_tk_mutex) return ESP_ERR_NO_MEM;

    s_source = CYM_TIME_UNSYNCED;
    s_consec_count = 0;
    s_uncertainty_us = 0;
    s_has_rtc = false;

#if defined(BOARD_RTC_I2C_ADDR)
    // Initialize PCF85063A RTC
    if (bus) {
        esp_err_t ret = pcf85063_init(&s_rtc, bus, BOARD_RTC_I2C_ADDR);
        if (ret == ESP_OK) {
            s_has_rtc = true;
            ESP_LOGI(TAG, "PCF85063A RTC available");

            // Load persisted trust state
            load_trust();

            // Try to restore system clock from RTC at boot
            struct tm rtc_time;
            bool os_flag = false;
            ret = pcf85063_read_time(&s_rtc, &rtc_time, &os_flag);
            if (ret == ESP_OK && !os_flag && pcf85063_validate_calendar(&rtc_time)) {
                s_rtc_valid = true;

                if (s_rtc_trusted) {
                    // RTC was previously GPS-disciplined — restore clock
                    time_t rtc_epoch = timegm(&rtc_time);
                    if (rtc_epoch != (time_t)-1) {
                        // Check if system clock is clearly wrong
                        time_t now = time(NULL);
                        struct tm now_tm;
                        gmtime_r(&now, &now_tm);
                        if (now_tm.tm_year + 1900 < 2024 || llabs((long long)now - (long long)rtc_epoch) > 2) {
                            step_clock(rtc_epoch);
                        }
                        s_source = CYM_TIME_RTC_HOLDOVER;
                        s_last_lock_mono_us = esp_timer_get_time();
                        uint64_t elapsed_s = 0;
                        if (s_last_gps_sync_epoch > 0 && rtc_epoch > s_last_gps_sync_epoch) {
                            elapsed_s = (uint64_t)(rtc_epoch - s_last_gps_sync_epoch);
                        }
                        s_holdover_base_age_ms = elapsed_s * 1000ULL;
                        uint64_t base_uncertainty = GPS_UART_UNCERTAINTY_US + elapsed_s * HOLDOVER_DRIFT_PPM;
                        s_holdover_base_uncertainty_us = base_uncertainty > UINT32_MAX ? UINT32_MAX : (uint32_t)base_uncertainty;
                        s_uncertainty_us = s_holdover_base_uncertainty_us;
                        ESP_LOGI(TAG, "Clock restored from trusted RTC (holdover %llu s)",
                                 (unsigned long long)elapsed_s);
                    }
                } else {
                    ESP_LOGI(TAG, "RTC valid but not GPS-trusted — staying UNSYNCED");
                }
            } else {
                s_rtc_valid = false;
                if (os_flag) {
                    ESP_LOGW(TAG, "RTC oscillator stopped — time invalid");
                } else if (ret != ESP_OK) {
                    ESP_LOGW(TAG, "RTC read failed: %s", esp_err_to_name(ret));
                } else {
                    ESP_LOGW(TAG, "RTC calendar invalid");
                }
            }
        } else {
            ESP_LOGW(TAG, "PCF85063A not available (non-fatal)");
        }
    }
#endif

    ESP_LOGI(TAG, "Timekeeper initialized (source=%s, rtc=%s)",
             cym_timekeeper_source_name(s_source),
             s_has_rtc ? (s_rtc_trusted ? "trusted" : "valid") : "none");
    return ESP_OK;
}

esp_err_t cym_timekeeper_observe_gps_utc(time_t epoch, int64_t rx_monotonic_us)
{
    if (!s_tk_mutex) return ESP_ERR_INVALID_STATE;
    if (xSemaphoreTake(s_tk_mutex, pdMS_TO_TICKS(50)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    s_gps_fix = true;

    // Check for discontinuity: if the sample jumps more than MAX_DISCONTINUITY_S
    // from the previous one (accounting for elapsed monotonic time), reject
    if (s_consec_count > 0 && s_prev_gps_epoch > 0) {
        int64_t elapsed_mono_s = (rx_monotonic_us - s_prev_gps_mono_us) / 1000000LL;
        int64_t expected_epoch = s_prev_gps_epoch + elapsed_mono_s;
        int64_t diff = (int64_t)epoch - expected_epoch;
        if (diff < -MAX_DISCONTINUITY_S || diff > MAX_DISCONTINUITY_S) {
            ESP_LOGW(TAG, "GPS discontinuity: expected ~%ld, got %ld (diff=%lld s)",
                     (long)expected_epoch, (long)epoch, (long long)diff);
            s_consec_count = 0;
            s_prev_gps_epoch = epoch;
            s_prev_gps_mono_us = rx_monotonic_us;
            xSemaphoreGive(s_tk_mutex);
            return ESP_OK;
        }
    }

    s_prev_gps_epoch = epoch;
    s_prev_gps_mono_us = rx_monotonic_us;
    s_consec_count++;

    // Need GPS_LOCK_SAMPLES consecutive valid samples for lock
    if (s_source != CYM_TIME_GPS_LOCKED && s_consec_count >= GPS_LOCK_SAMPLES) {
        // Transition to GPS_LOCKED
        s_source = CYM_TIME_GPS_LOCKED;
        s_last_lock_mono_us = rx_monotonic_us;
        s_uncertainty_us = GPS_UART_UNCERTAINTY_US;
        s_last_gps_sync_epoch = epoch;

        // Discipline the system clock
        time_t now = time(NULL);
        int64_t diff_us = ((int64_t)epoch - (int64_t)now) * 1000000LL;
        if (diff_us < -STEP_THRESHOLD_US || diff_us > STEP_THRESHOLD_US ||
            now < 1704067200) {  // year < 2024
            step_clock(epoch);
            s_last_correction_us = (int32_t)(diff_us > INT32_MAX ? INT32_MAX :
                                   diff_us < INT32_MIN ? INT32_MIN : diff_us);
        } else {
            s_last_correction_us = (int32_t)diff_us;
            slew_clock(s_last_correction_us);
        }

        // Write RTC on initial lock
        write_rtc_if_due(epoch, rx_monotonic_us);

        ESP_LOGI(TAG, "GPS LOCKED (correction=%d us)", (int)s_last_correction_us);
    } else if (s_source == CYM_TIME_GPS_LOCKED) {
        // Already locked — apply small corrections via slew
        time_t now = time(NULL);
        int64_t diff_us = ((int64_t)epoch - (int64_t)now) * 1000000LL;
        if (diff_us >= -STEP_THRESHOLD_US && diff_us <= STEP_THRESHOLD_US) {
            s_last_correction_us = (int32_t)diff_us;
            if (diff_us != 0) {
                slew_clock(s_last_correction_us);
            }
        }
        s_last_lock_mono_us = rx_monotonic_us;
        s_last_gps_sync_epoch = epoch;
        s_uncertainty_us = GPS_UART_UNCERTAINTY_US;

        // Periodic RTC update
        write_rtc_if_due(epoch, rx_monotonic_us);
    } else {
        // A trusted RTC remains authoritative while GPS samples qualify.
        if (s_source == CYM_TIME_UNSYNCED) {
            s_source = CYM_TIME_GPS_ACQUIRING;
        }
    }

    xSemaphoreGive(s_tk_mutex);
    return ESP_OK;
}

esp_err_t cym_timekeeper_observe_network_utc(time_t epoch, int64_t rx_monotonic_us,
                                                  bool repair_rtc)
{
    if (!s_tk_mutex) return ESP_ERR_INVALID_STATE;
    if ((int64_t)epoch < MIN_REASONABLE_EPOCH || (int64_t)epoch >= MAX_REASONABLE_EPOCH) {
        return ESP_ERR_INVALID_ARG;
    }
    if (xSemaphoreTake(s_tk_mutex, pdMS_TO_TICKS(50)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    // Never let a public network source displace a qualified GPS lock.
    if (s_source == CYM_TIME_GPS_LOCKED) {
        xSemaphoreGive(s_tk_mutex);
        return ESP_ERR_INVALID_STATE;
    }

    time_t now = time(NULL);
    int64_t diff_us = ((int64_t)epoch - (int64_t)now) * 1000000LL;
    if (diff_us < -STEP_THRESHOLD_US || diff_us > STEP_THRESHOLD_US ||
        (int64_t)now < MIN_REASONABLE_EPOCH) {
        step_clock(epoch);
    } else if (diff_us != 0) {
        slew_clock((int32_t)diff_us);
    }
    s_last_correction_us = (int32_t)(diff_us > INT32_MAX ? INT32_MAX :
                           diff_us < INT32_MIN ? INT32_MIN : diff_us);
    s_source = CYM_TIME_NETWORK_SYNC;
    s_last_lock_mono_us = rx_monotonic_us;
    s_last_gps_sync_epoch = epoch;
    s_uncertainty_us = NETWORK_UNCERTAINTY_US;
    s_holdover_base_age_ms = 0;
    s_holdover_base_uncertainty_us = NETWORK_UNCERTAINTY_US;

    if (repair_rtc) {
        write_rtc_if_due(epoch, rx_monotonic_us);
    }
    ESP_LOGI(TAG, "Clock disciplined from public NTP%s",
             repair_rtc ? "; RTC repair requested" : "");

    xSemaphoreGive(s_tk_mutex);
    return ESP_OK;
}

void cym_timekeeper_note_gps_present(bool present)
{
    if (!s_tk_mutex) return;
    if (xSemaphoreTake(s_tk_mutex, pdMS_TO_TICKS(50)) != pdTRUE) return;
    s_gps_present = present;
    if (!present) s_gps_fix = false;
    xSemaphoreGive(s_tk_mutex);
}

bool cym_timekeeper_snapshot(cym_time_snapshot_t *out)
{
    if (!out || !s_tk_mutex) return false;
    if (xSemaphoreTake(s_tk_mutex, pdMS_TO_TICKS(50)) != pdTRUE) {
        return false;
    }

    gettimeofday(&out->utc, NULL);
    out->source = s_source;
    out->rtc_valid = s_rtc_valid;
    out->gps_present = s_gps_present;
    out->gps_fix = s_gps_fix;
    out->pps_active = false;  // Version one: no PPS
    out->last_gps_sync_epoch = (uint64_t)s_last_gps_sync_epoch;
    out->last_correction_us = s_last_correction_us;

    int64_t now_mono = esp_timer_get_time();

    // Check for GPS loss while locked
    if (s_source == CYM_TIME_GPS_LOCKED) {
        int64_t since_last = now_mono - s_last_lock_mono_us;
        if (since_last > GPS_LOSS_TIMEOUT_US) {
            // Transition to holdover
            if (s_rtc_trusted && s_rtc_valid) {
                s_source = CYM_TIME_RTC_HOLDOVER;
                s_gps_fix = false;
                s_holdover_base_age_ms = 0;
                s_holdover_base_uncertainty_us = GPS_UART_UNCERTAINTY_US;
                s_last_lock_mono_us = now_mono;
                ESP_LOGW(TAG, "GPS lost — entering RTC holdover");
            } else {
                s_source = CYM_TIME_UNSYNCED;
                ESP_LOGW(TAG, "GPS lost — no trusted RTC, UNSYNCED");
            }
        }
    }

    // Compute source age and uncertainty
    switch (s_source) {
    case CYM_TIME_GPS_LOCKED:
        out->source_age_ms = (uint64_t)((now_mono - s_last_lock_mono_us) / 1000);
        out->uncertainty_us = GPS_UART_UNCERTAINTY_US;
        out->valid = true;
        break;
    case CYM_TIME_NETWORK_SYNC: {
        uint64_t elapsed_us = (uint64_t)(now_mono - s_last_lock_mono_us);
        out->source_age_ms = elapsed_us / 1000;
        uint64_t drift_us = (elapsed_us / 1000000ULL) * HOLDOVER_DRIFT_PPM;
        uint64_t uncertainty = NETWORK_UNCERTAINTY_US + drift_us;
        out->uncertainty_us = uncertainty > UINT32_MAX ? UINT32_MAX : (uint32_t)uncertainty;
        out->valid = true;
        break;
    }
    case CYM_TIME_RTC_HOLDOVER: {
        uint64_t holdover_us = (uint64_t)(now_mono - s_last_lock_mono_us);
        out->source_age_ms = s_holdover_base_age_ms + holdover_us / 1000;
        uint64_t drift_us = (holdover_us / 1000000ULL) * HOLDOVER_DRIFT_PPM;
        uint64_t uncertainty = (uint64_t)s_holdover_base_uncertainty_us + drift_us;
        out->uncertainty_us = uncertainty > UINT32_MAX ? UINT32_MAX : (uint32_t)uncertainty;
        out->valid = true;
        break;
    }
    case CYM_TIME_GPS_ACQUIRING:
        out->source_age_ms = 0;
        out->uncertainty_us = 0;
        out->valid = (s_rtc_trusted && s_rtc_valid);
        break;
    case CYM_TIME_UNSYNCED:
    default:
        out->source_age_ms = 0;
        out->uncertainty_us = 0;
        out->valid = false;
        break;
    }

    // Re-read source after potential transition above
    out->source = s_source;

    xSemaphoreGive(s_tk_mutex);
    return true;
}

const char *cym_timekeeper_source_name(cym_time_source_t source)
{
    switch (source) {
    case CYM_TIME_UNSYNCED:       return "UNSYNCED";
    case CYM_TIME_GPS_ACQUIRING:  return "GPS ACQUIRING";
    case CYM_TIME_GPS_LOCKED:     return "GPS LOCK";
    case CYM_TIME_RTC_HOLDOVER:   return "RTC HOLDOVER";
    case CYM_TIME_NETWORK_SYNC:   return "PUBLIC NTP";
    default:                      return "UNKNOWN";
    }
}
