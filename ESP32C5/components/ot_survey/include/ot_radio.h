/*
 * ot_radio.h — OT Air Survey radio scheduler (Phase 3)
 *
 * Profile-weighted time-slicer that multiplexes the ESP32-C5's shared RF
 * hardware across WiFi, BLE, ESP-NOW, and IEEE 802.15.4 during a passive
 * survey session.
 *
 * Architecture:
 *   - FreeRTOS task at priority 2 (same as RF-HAT scan tasks)
 *   - 10-second cycle; each slot dwell = weight × 100 ms (min 500 ms)
 *   - Radio switches via function pointers injected by main.c at boot
 *
 * Board capability:
 *   CYD2USB : WiFi + BLE + ESP-NOW; 154 hook must be NULL
 *   NM-CYD-C5 / WS-C5-28 : all four slots available
 *
 * Survey lock:
 *   g_ot_survey_active is set true by ot_radio_scheduler_start() and cleared
 *   by ot_radio_scheduler_stop().  main.c reads this flag at attack screen
 *   entry points to show a "Stop OT Survey first" notice.
 *
 * PASSIVE ONLY — this scheduler never transmits.
 */

#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "ot_survey.h"   /* ot_survey_profile_t */

#ifdef __cplusplus
extern "C" {
#endif

/* ── Radio slots ─────────────────────────────────────────────────────────── */

typedef enum {
    OT_SLOT_WIFI   = 0,  /* WiFi scan — 2.4 GHz + 5 GHz promiscuous */
    OT_SLOT_BLE    = 1,  /* BLE observer — adv + ext adv */
    OT_SLOT_154    = 2,  /* IEEE 802.15.4 — Zigbee / WirelessHART (C5 only) */
    OT_SLOT_ESPNOW = 3,  /* ESP-NOW scout (on WiFi radio) */
    OT_SLOT_COUNT  = 4,
} ot_radio_slot_t;

/* ── Profile weight table ─────────────────────────────────────────────────── */
/*
 * Weights per slot, in units of 100 ms dwell within a 10-second cycle.
 * Each row must sum to 100.  A weight of 0 means the slot is skipped.
 */
extern const uint8_t OT_PROFILE_WEIGHTS[OT_PROFILE_COUNT][OT_SLOT_COUNT];

/* ── Survey lock flag ────────────────────────────────────────────────────── */
/*
 * Set true when the scheduler is running.  main.c checks this at attack
 * screen entry points to prevent radio conflicts.
 */
extern volatile bool g_ot_survey_active;

/* ── Function pointer hooks (injected from main.c) ───────────────────────── */

typedef bool (*ot_radio_switch_fn_t)(void);  /* returns true on success */
typedef void (*ot_radio_idle_fn_t)(void);    /* puts radio in idle state */

typedef struct {
    ot_radio_switch_fn_t switch_to_wifi;    /* ensure_wifi_mode() wrapper */
    ot_radio_switch_fn_t switch_to_ble;     /* ensure_ble_mode() wrapper */
    ot_radio_switch_fn_t switch_to_154;     /* esp_ieee802154_enable() wrapper; NULL = not available */
    ot_radio_idle_fn_t   switch_to_idle;    /* radio_reset_to_idle() wrapper */
} ot_radio_hooks_t;

/* ── Scheduler state (read-only from callers) ────────────────────────────── */

typedef enum {
    OT_SCHED_IDLE    = 0,
    OT_SCHED_RUNNING = 1,
    OT_SCHED_STOP_REQUESTED = 2,
} ot_sched_state_t;

/* ── API ─────────────────────────────────────────────────────────────────── */

/*
 * ot_radio_init — called once at boot from main.c after WiFi/BLE
 * infrastructure is initialised.  Injects the radio switch hooks.
 */
void ot_radio_init(const ot_radio_hooks_t *hooks);

/*
 * ot_radio_scheduler_start — launch the scheduler task for the given
 * survey profile.  Sets g_ot_survey_active = true.
 * Returns ESP_ERR_INVALID_STATE if already running.
 */
esp_err_t ot_radio_scheduler_start(ot_survey_profile_t profile);

/*
 * ot_radio_scheduler_stop — request task to stop and wait up to 3 s for it
 * to exit cleanly.  Clears g_ot_survey_active.
 */
esp_err_t ot_radio_scheduler_stop(void);

/*
 * ot_radio_current_slot — returns the slot currently being serviced, or
 * OT_SLOT_WIFI if the scheduler is idle.
 */
ot_radio_slot_t ot_radio_current_slot(void);

/*
 * ot_radio_slot_name — human-readable slot name for logging / UI.
 */
const char *ot_radio_slot_name(ot_radio_slot_t slot);

#ifdef __cplusplus
}
#endif
