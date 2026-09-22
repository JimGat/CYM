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

/* ── Geo stamp ────────────────────────────────────────────────────────────── */
/*
 * Single GPS fix, captured by the caller (main.c owns the GPS driver; this
 * component has no GPS access of its own) and handed to ot_survey_start() /
 * ot_survey_stop() so metadata.json can record where the survey began and
 * ended. valid=false (the zero value) means no fix was available at that
 * moment — every field is then written as 0 in metadata.json rather than
 * omitted, so parsers don't need to treat the key as optional.
 */
typedef struct {
    float latitude;
    float longitude;
    float altitude_m;
    float accuracy_m;
    bool  valid;
} ot_survey_geo_t;

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
    uint32_t          obs_count;           /* total unique observations recorded */
    uint32_t          obs_by_type[10];     /* per-type counters indexed by obs_type_t */
    uint32_t          obs_export_dropped;  /* records dropped from obs.jsonl export — see
                                             * ot_survey_queue_export()'s doc comment */
    ot_survey_geo_t   geo_start;           /* GPS fix at ot_survey_start(), if any */
    ot_survey_geo_t   geo_end;             /* GPS fix at ot_survey_stop(), if any */
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
/* No init function — nothing needs calling before ot_survey_start(). Removed in
 * v2.13.99: ot_survey_init() used to eagerly create /sdcard/lab/otsurvey/ at
 * boot, before SD was mounted, so it always failed and logged spurious errors
 * every boot. ot_survey_start() below now creates both directory levels itself,
 * lazily, when a survey actually starts (its caller ensures SD is mounted first
 * — see main.c's s_ots_start_cb()). */

/*
 * ot_survey_start — allocate a session, generate UUID, create per-session
 * SD directory, write metadata.json.
 * start_geo: GPS fix at survey start, or NULL if unavailable (recorded in
 * metadata.json as geo_start; valid=false if NULL or *start_geo.valid==false).
 * Returns ESP_OK and fills *sess on success.
 * *sess must remain valid until ot_survey_stop().
 */
esp_err_t ot_survey_start(const ot_survey_config_t *cfg, ot_survey_session_t *sess,
                           const ot_survey_geo_t *start_geo);

/*
 * ot_survey_stop — finalise metadata.json (end timestamp, obs_count, geo_end),
 * set state to OT_STATE_STOPPED.  Does not free any underlying store.
 * end_geo: GPS fix at survey stop, or NULL if unavailable.
 */
esp_err_t ot_survey_stop(ot_survey_session_t *sess, const ot_survey_geo_t *end_geo);

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
 * ot_survey_queue_export — call once for every NEWLY-CREATED (not re-sighted)
 * observation a main-loop radio adapter just inserted into g_obs_store, right
 * after confirming obs_store_add() returned hit_count==1. No-op if sess is
 * not OT_STATE_ACTIVE.
 *
 * Increments sess->obs_count / obs_by_type[] (centralising what all five
 * main.c call sites used to do inline — see git history for the v2.13.87 fix
 * that had to patch that duplicated logic in five places) AND copies the
 * record into a small per-survey pending queue that ot_survey_flush() drains
 * to obs.jsonl on its next call.
 *
 * Why a separate queue instead of reading g_obs_store directly (as the old
 * ot_survey_flush() did): g_obs_store is a single GLOBAL ring buffer shared
 * by every feature (WiFi Scan, BLE, ESP-NOW, 802.15.4, this survey) for the
 * device's whole uptime. Once its capacity is reached, new inserts evict the
 * oldest record via write_head wraparound and obs_store_count() FREEZES at
 * capacity permanently — so any old code that paginated store->records[] by
 * index against obs_store_count() silently stopped seeing new records forever
 * once the store saturated, even though evicted-and-recreated "new" sightings
 * kept inflating obs_count/obs_by_type (field bug, v2.13.89/90, 2026-09-13).
 * This queue is copied out of the record at the moment of creation — before
 * it could ever be evicted — so export durability no longer depends on
 * g_obs_store's capacity, eviction order, or lifetime-wide usage at all.
 *
 * Bounded: if the queue fills between flushes (default cap generous relative
 * to observed field churn), further records are dropped and counted in
 * sess->obs_export_dropped rather than blocking the main loop or growing
 * unbounded — a warning is logged once per survey the first time this
 * happens. obs_count/obs_by_type still increment even if the queue is full
 * or unallocated; only the SD export is affected by queue pressure.
 */
void ot_survey_queue_export(ot_survey_session_t *sess, const obs_record_t *rec);

/*
 * ot_survey_flush — write every record queued by ot_survey_queue_export()
 * since the last call to /session_dir/obs.jsonl (append mode), then clear
 * the queue. Call periodically (e.g. from a timer) under sd_spi_mutex, same
 * as before. No-op (returns ESP_OK) if the queue is currently empty.
 */
esp_err_t ot_survey_flush(ot_survey_session_t *sess);

/*
 * ot_survey_uuid_str — render uuid as 32 lowercase hex chars into buf[33].
 */
void ot_survey_uuid_str(const ot_uuid_t *uuid, char buf[33]);

/*
 * ot_survey_profile_name — human-readable profile name for UI labels.
 */
const char *ot_survey_profile_name(ot_survey_profile_t profile);

/* ── Results (post-survey summary, read back from SD) ────────────────────── */
/*
 * A results view loaded from a session's metadata.json + obs.jsonl — either
 * the session that was just stopped (main.c calls this right after
 * ot_survey_stop() returns), or an older session picked from
 * ot_survey_list_sessions(). This is a read-only snapshot: it does not touch
 * g_active_survey or any live radio/obs_store state.
 *
 * obs_by_type[] is an EXACT full-file count (every line in obs.jsonl is
 * scanned once for this). entries[] is a bounded, deduplicated-by-MAC list
 * for the on-device drill-down UI — same find-or-add-by-MAC idiom already
 * used by obs_store_add()/espnow_find_or_add(), so it naturally caps at the
 * number of *unique devices*, not total observation lines, and a very busy
 * session degrades to "some devices missing from the list" rather than
 * "list truncated mid-alphabet" — entries_truncated is set if the file had
 * more unique devices than entries_cap.
 */
#define OT_RESULT_LABEL_LEN  24

typedef struct {
    uint8_t  obs_type;                        /* obs_type_t */
    uint8_t  src_radio;                       /* obs_radio_t */
    uint8_t  mac[6];
    int8_t   rssi_cur;
    int8_t   rssi_peak;
    uint8_t  confidence;                      /* 0-100 */
    uint8_t  evidence[OBS_MAX_EVIDENCE];
    uint8_t  evidence_count;
    uint16_t hit_count;
    uint32_t first_seen_s;
    uint32_t last_seen_s;
    char     label[OT_RESULT_LABEL_LEN];
} ot_result_entry_t;

typedef struct {
    char     uuid[33];
    char     dir_path[80];
    char     site[OT_SURVEY_SITE_LEN];
    char     building[OT_SURVEY_BUILDING_LEN];
    char     zone[OT_SURVEY_ZONE_LEN];
    char     operator_id[OT_SURVEY_OPERATOR_LEN];
    char     profile_name[20];
    uint32_t start_time_s;
    uint32_t stop_time_s;
    uint32_t obs_count;                       /* exact — full obs.jsonl scan */
    uint32_t obs_by_type[10];                 /* exact — full obs.jsonl scan */
    bool     geo_start_valid, geo_end_valid;
    float    geo_start_lat, geo_start_lon;
    float    geo_end_lat, geo_end_lon;

    ot_result_entry_t *entries;                /* heap_caps_malloc'd — free via ot_survey_results_free() */
    uint16_t            entries_count;
    uint16_t            entries_cap;
    bool                 entries_truncated;
} ot_survey_results_t;

/*
 * ot_survey_results_load — parse metadata.json + obs.jsonl from session_dir
 * into *out. max_entries bounds the drill-down device list (obs_by_type[]
 * counts are always exact regardless of this cap). Caller must call
 * ot_survey_results_free() when done, even on a partial/error return, to
 * release the entries array.
 *
 * Must be called with sd_spi_mutex held (reads from SD), same convention as
 * ot_survey_flush().
 */
esp_err_t ot_survey_results_load(const char *session_dir, ot_survey_results_t *out,
                                  uint16_t max_entries);

/*
 * ot_survey_results_free — release *out's entries array. Safe to call on a
 * zero-initialised or already-freed struct (idempotent).
 */
void ot_survey_results_free(ot_survey_results_t *out);

/* ── Session listing (for the Past Surveys browser) ──────────────────────── */

/* newest-first; older sessions beyond this are still on SD and can be reached
 * by clearing/rotating old sessions, just not listed in one screen. Kept small
 * deliberately: the browser UI is a static array sized OT_SESSION_LIST_MAX *
 * sizeof(ot_session_summary_t), reserved at link time on every board
 * (including CYD2USB, which has no PSRAM to fall back to) — CYD2USB's DRAM
 * budget overflowed at the original value of 40 (field build failure,
 * 2026-09-22). 12 sessions is already more than this codebase's other list
 * caps (e.g. BT Lookout's 16-entry watchlist on NM-CYD-C5, 16 on CYD2USB). */
#define OT_SESSION_LIST_MAX  12

typedef struct {
    char     dir_path[56];  /* "/sdcard/lab/otsurvey/" (22) + 32 hex uuid + NUL = 55 */
    char     site[OT_SURVEY_SITE_LEN];
    uint32_t start_time_s;
    uint32_t obs_count;              /* from metadata.json — may be stale if the
                                       * session crashed before a final flush;
                                       * ot_survey_results_load()'s obs_by_type
                                       * total is always the authoritative count */
} ot_session_summary_t;

/*
 * ot_survey_list_sessions — scan /sdcard/lab/otsurvey/ for session
 * directories, read each one's metadata.json header (site, start_time,
 * obs_count only — NOT the full obs.jsonl), and fill out[] newest-first.
 * Returns the number of sessions found (capped at OT_SESSION_LIST_MAX; the
 * total directory count, if larger, is written to *total_found when
 * total_found is non-NULL).
 *
 * Must be called with sd_spi_mutex held.
 */
int ot_survey_list_sessions(ot_session_summary_t out[OT_SESSION_LIST_MAX], int *total_found);

#if CONFIG_IEEE802154_ENABLED
/*
 * ot_survey_write_154_frame — append one 802.15.4 PSDU to the session PCAPNG.
 *
 * Called from the main loop 802.15.4 adapter (never from ISR context).
 * Caller must hold sd_spi_mutex before calling (write goes to SD card).
 *
 * psdu / psdu_len : MAC frame bytes WITHOUT FCS (ESP-IDF strips FCS in
 *                   promiscuous mode and replaces the slot with RSSI+LQI;
 *                   the PCAPNG link type is DLT_IEEE802_15_4_NOFCS = 230).
 * rssi            : signed dBm value from frame_info.rssi
 * lqi             : 0-255 LQI from frame_info.lqi
 * ts_us           : capture timestamp in microseconds (esp_timer_get_time())
 *
 * Returns ESP_OK on success, ESP_ERR_INVALID_STATE if no PCAPNG file is open,
 * ESP_ERR_INVALID_ARG on bad arguments.
 *
 * PASSIVE ONLY — this function never transmits.
 */
esp_err_t ot_survey_write_154_frame(const uint8_t *psdu, uint8_t psdu_len,
                                     int8_t rssi, uint8_t lqi, uint64_t ts_us);
#endif /* CONFIG_IEEE802154_ENABLED */

#ifdef __cplusplus
}
#endif
