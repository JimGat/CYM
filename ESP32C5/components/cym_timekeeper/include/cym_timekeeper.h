// CYM Timekeeper — GPS-disciplined UTC source with RTC holdover.
// Board-time service: source selection, step/slew discipline,
// RTC backup, immutable snapshot interface.
// No LVGL dependency.
#pragma once

#include "driver/i2c_master.h"
#include "esp_err.h"
#include <sys/time.h>
#include <time.h>
#include <stdbool.h>
#include <stdint.h>

typedef enum {
    CYM_TIME_UNSYNCED = 0,
    CYM_TIME_GPS_ACQUIRING,
    CYM_TIME_GPS_LOCKED,
    CYM_TIME_NETWORK_SYNC,
    CYM_TIME_RTC_HOLDOVER,
    CYM_TIME_RTOS_HOLDOVER,
} cym_time_source_t;

typedef enum {
    CYM_TIME_RELIABILITY_UNTRUSTED = 0,
    CYM_TIME_RELIABILITY_DEGRADED,
    CYM_TIME_RELIABILITY_HOLDOVER,
    CYM_TIME_RELIABILITY_GOOD,
    CYM_TIME_RELIABILITY_EXCELLENT,
} cym_time_reliability_t;

typedef struct {
    struct timeval utc;
    cym_time_source_t source;
    cym_time_reliability_t reliability;
    bool valid;
    bool has_rtc;
    bool has_gps_uart;
    bool estimate_characterized;
    bool rtc_valid;
    bool gps_present;
    bool gps_fix;
    bool pps_active;
    uint64_t source_age_ms;
    uint64_t last_gps_sync_epoch;
    uint32_t uncertainty_us;
    int32_t last_correction_us;
} cym_time_snapshot_t;

// Initialize the timekeeper with the board's I2C bus (for PCF85063A RTC).
// Reads the RTC; if valid and trusted, restores the system clock.
// Safe to call on boards without an RTC (returns ESP_OK, no RTC features).
esp_err_t cym_timekeeper_init(i2c_master_bus_handle_t bus);

// Feed a validated GPS RMC UTC sample. epoch is the parsed UTC epoch;
// rx_monotonic_us is esp_timer_get_time() at sentence completion.
// The timekeeper qualifies samples internally before accepting them.
esp_err_t cym_timekeeper_observe_gps_utc(time_t epoch, int64_t rx_monotonic_us);

// Accept a bounded public-NTP UTC update when GPS is not locked. The system
// clock is disciplined and the RTC is optionally repaired; qualified GPS wins.
esp_err_t cym_timekeeper_observe_network_utc(time_t epoch, int64_t rx_monotonic_us,
                                                  bool repair_rtc);

// Flush a pending RTC-trust record from an internal-RAM task such as main_task.
// GPS observation only marks persistence pending because its task stack is in
// PSRAM and cannot safely survive the cache-disabled interval of nvs_commit().
esp_err_t cym_timekeeper_flush_pending_persistence(void);

// Inform the timekeeper whether GPS UART traffic is present.
void cym_timekeeper_note_gps_present(bool present);

// Get an immutable snapshot of current time state.
// Returns true if the snapshot was populated; false on error.
bool cym_timekeeper_snapshot(cym_time_snapshot_t *out);

// Human-readable name for a time source state.
const char *cym_timekeeper_source_name(cym_time_source_t source);

// Human-readable reliability derived from source and current uncertainty.
const char *cym_timekeeper_reliability_name(cym_time_reliability_t reliability);
