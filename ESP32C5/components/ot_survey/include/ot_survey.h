/*
 * ot_survey.h — Passive OT Air Survey session management
 *
 * Provides a lifecycle API for structured, multi-radio passive survey sessions.
 * All capture is PASSIVE ONLY — no probes, deauthentication, spoofed advertisements,
 * or disruptive traffic are ever transmitted.
 *
 * Capability guards:
 *   #if CONFIG_IEEE802154_ENABLED  — Zigbee / WirelessHART / Thread sub-API
 *   #if CONFIG_BOARD_HAS_PSRAM    — large ring buffers; falls back to smaller DRAM bufs
 *
 * All three board variants (NM-CYD-C5, WS-C5-28, CYD2USB) compile this header.
 * 802.15.4 code paths compile only on capable boards.
 */

#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"
#include "obs_store.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ── UUID ────────────────────────────────────────────────────────────────── */

typedef struct {
    uint8_t bytes[16];
} ot_uuid_t;

/* ── Survey profiles — controls which radios participate and at what weight ─ */

typedef enum {
    OT_PROFILE_BALANCED       = 0, /* WiFi + BLE + ESP-NOW; 802.15.4 if capable */
    OT_PROFILE_WIFI_HEAVY     = 1, /* 70% WiFi, 20% BLE, 10% other */
    OT_PROFILE_BLE_HEAVY      = 2, /* 20% WiFi, 70% BLE, 10% other */
    OT_PROFILE_154_HEAVY      = 3, /* 20% WiFi, 10% BLE, 70% 802.15.4 (C5 only) */
    OT_PROFILE_ESPNOW_FOCUS   = 4, /* ESP-NOW discovery + decode focus */
    OT_PROFILE_DRONE_WATCH    = 5, /* BLE + WiFi weighted for drone-ID detection */
    OT_PROFILE_WIRELESSHART   = 6, /* 802.15.4 heavy, WirelessHART heuristic enabled (C5 only) */
    OT_PROFILE_THREAD_MATTER  = 7, /* 802.15.4 focused, Thread/Matter detection (C5 only) */
    OT_PROFILE_COUNT
} ot_survey_profile_t;

/* ── Survey session state machine ─────────────────────────────────────────── */

typedef enum {
    OT_STATE_IDLE    = 0,
    OT_STATE_ACTIVE  = 1,
    OT_STATE_PAUSED  = 2,
    OT_STATE_STOPPED = 3,
    OT_STATE_ERROR   = 4,
} ot_survey_state_t;

/* ── Session configuration ────────────────────────────────────────────────── */

#define OT_SURVEY_ORG_LEN      32
#define OT_SURVEY_SITE_LEN     32
#define OT_SURVEY_BUILDING_LEN 32
#define OT_SURVEY_ZONE_LEN     32
#define OT_SURVEY_OPERATOR_LEN 32
#define OT_SURVEY_DESC_LEN     64

typedef struct {
    char org[OT_SURVEY_ORG_LEN];           /* customer / organisation */
    char site[OT_SURVEY_SITE_LEN];         /* site name or address */
    char building[OT_SURVEY_BUILDING_LEN]; /* building or wing */
    char zone[OT_SURVEY_ZONE_LEN];         /* floor / zone / room */
    char operator_id[OT_SURVEY_OPERATOR_LEN]; /* surveyor callsign or badge */
    char description[OT_SURVEY_DESC_LEN];  /* free text note */
    ot_survey_profile_t profile;
    obs_privacy_flags_t privacy;           /* redaction flags applied to every record */
    uint32_t max_duration_s;               /* 0 = unlimited */
} ot_survey_config_t;

/* ── Session handle ──────────────────────────────────────────────────────── */

typedef struct {
    ot_uuid_t         uuid;
    ot_survey_config_t cfg;
    ot_survey_state_t state;
    uint32_t          start_time_s;
    uint32_t          stop_time_s;
    uint32_t          obs_count;
    char              dir_path[80];  /* /sdcard/lab/otsurvey/<uuid-hex>/ */
} ot_survey_session_t;

/* ── Active session pointer — set by ot_survey_start(), cleared by ot_survey_stop() ─ */
/*
 * g_active_survey is non-NULL while a survey is in OT_STATE_ACTIVE or OT_STATE_PAUSED.
 * Main loop adapters (WiFi / BLE / ESP-NOW) read this to increment obs_count and route
 * records to the survey.  Only ot_survey.c writes it.
 */
extern ot_survey_session_t *g_active_survey;

/* ── API ─────────────────────────────────────────────────────────────────── */

/*
 * ot_survey_init — must be called once at boot before any other API.
 * Ensures /sdcard/lab/otsurvey/ exists (called again on SD remount).
 */
esp_err_t ot_survey_init(void);

/*
 * ot_survey_start — allocate a session, generate UUID, create per-session
 * SD directory, write metadata.json.
 * Returns ESP_OK and fills *sess on success.
 * *sess must remain valid until ot_survey_stop().
 */
esp_err_t ot_survey_start(const ot_survey_config_t *cfg, ot_survey_session_t *sess);

/*
 * ot_survey_stop — finalise metadata.json (end timestamp, obs_count), set state
 * to OT_STATE_STOPPED.  Does not free any underlying store.
 */
esp_err_t ot_survey_stop(ot_survey_session_t *sess);

/*
 * ot_survey_pause / resume — freezes radio scheduler slice allocation but keeps
 * the session open.  Phase 3 will wire these to the radio ownership layer.
 */
esp_err_t ot_survey_pause(ot_survey_session_t *sess);
esp_err_t ot_survey_resume(ot_survey_session_t *sess);

/*
 * ot_survey_record_obs — add an observation to the session's obs_store and
 * increment sess->obs_count.  Applies session privacy policy before storing.
 */
esp_err_t ot_survey_record_obs(ot_survey_session_t *sess, obs_store_t *store,
                                const obs_record_t *rec);

/*
 * ot_survey_flush — write all records in store to /session_dir/obs.jsonl.
 * Truncates and rewrites the whole file (suitable for incremental flush calls
 * from a timer; Phase 5 will switch to append-mode PCAPNG).
 */
esp_err_t ot_survey_flush(ot_survey_session_t *sess, obs_store_t *store);

/*
 * ot_survey_uuid_str — render uuid as 32 lowercase hex chars into buf[33].
 */
void ot_survey_uuid_str(const ot_uuid_t *uuid, char buf[33]);

/*
 * ot_survey_profile_name — human-readable profile name for UI labels.
 */
const char *ot_survey_profile_name(ot_survey_profile_t profile);

#ifdef __cplusplus
}
#endif
