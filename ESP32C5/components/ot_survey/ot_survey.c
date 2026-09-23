/*
 * ot_survey.c — Passive OT Air Survey session management
 *
 * PASSIVE ONLY: this component never transmits.  It manages session lifecycle,
 * UUID generation, SD directory provisioning, metadata serialisation, and record
 * routing to obs_store.
 *
 * All three boards compile this file.  Feature guards:
 *   CONFIG_IEEE802154_ENABLED  — Zigbee/WirelessHART profiles valid only on C5.
 *   CONFIG_BOARD_HAS_PSRAM     — obs_store internal allocation uses PSRAM on C5.
 */

#include "ot_survey.h"
#include "ot_radio.h"
#include "obs_store.h"
#include "pcapng.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include <sys/stat.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <dirent.h>

static const char *TAG = "ot_survey";

#if CONFIG_IEEE802154_ENABLED
/* PCAPNG file handle for the active survey session; NULL when idle. */
static pcapng_writer_t *s_pcapng = NULL;
#endif

/* ── Export queue — see ot_survey_queue_export()'s doc comment in the header
 * for why this exists (fixes obs.jsonl silently freezing once g_obs_store
 * saturates). Allocated in ot_survey_start(), freed in ot_survey_stop(); a
 * plain array + count, not a ring — ot_survey_flush() drains it completely
 * each call and resets count to 0, so it never needs to wrap. */
#define OT_EXPORT_QUEUE_CAP  2048u   /* 2048 * 128B = 256KB PSRAM; ~5x the
                                      * largest single-flush-window burst
                                      * observed in the field (399/30s, 2026-09-13) */
/* DRAM-only fallback capacity (CYD2USB, no PSRAM) — 2048 * 128B = 256KB never
 * fit its ~50-90KB free internal DRAM either; the fallback's own comment
 * claimed "MALLOC_CAP_8BIT alone still succeeds on CYD2USB" but field
 * evidence disproved that (2026-09-22: "export queue allocation failed").
 * Same board-memory-budget rationale as OBS_STORE_CYD2USB_CAPACITY -
 * shrunk from an initial 128 (16KB) to 32 (4KB) alongside that same fix's
 * capacity cut, after 128+obs_store's original 256-entry size together
 * left too little margin for the OT Survey scheduler's WiFi->BLE handoff
 * and crashed the board (field report 2026-09-23, see obs_store.h). This
 * queue is a soft-fail burst buffer, not the survey's primary count (that's
 * sess->obs_count/obs_by_type, always tracked regardless) - failing small
 * is far preferable to failing by taking the whole board down. */
#define OT_EXPORT_QUEUE_CAP_DRAM  32u
static obs_record_t *s_export_pending       = NULL;
static uint32_t      s_export_pending_count = 0;
static uint32_t      s_export_pending_cap   = 0;  /* actual allocated capacity — may be
                                                    * OT_EXPORT_QUEUE_CAP or the smaller
                                                    * _DRAM fallback; ot_survey_queue_export()
                                                    * MUST bounds-check against this, not the
                                                    * compile-time OT_EXPORT_QUEUE_CAP, or a
                                                    * DRAM-fallback session overflows the
                                                    * smaller buffer. */
static bool          s_export_overflow_logged = false;

/*
 * g_active_survey — points to the running session while state is ACTIVE or PAUSED;
 * NULL when idle.  Written only from ot_survey_start() / ot_survey_stop().
 * Main loop adapters read it (without a mutex) to increment obs_count.
 */
ot_survey_session_t *g_active_survey = NULL;

#define OT_SURVEY_ROOT "/sdcard/lab/otsurvey"

/* ── UUID helpers ─────────────────────────────────────────────────────────── */

static void generate_uuid(ot_uuid_t *out)
{
    /* Generate 128 bits from the hardware RNG and lay out as RFC 4122 v4. */
    uint32_t r[4];
    for (int i = 0; i < 4; i++) r[i] = esp_random();
    memcpy(out->bytes, r, 16);
    /* Set version bits (v4) and variant bits (RFC 4122). */
    out->bytes[6] = (out->bytes[6] & 0x0F) | 0x40;
    out->bytes[8] = (out->bytes[8] & 0x3F) | 0x80;
}

void ot_survey_uuid_str(const ot_uuid_t *uuid, char buf[33])
{
    for (int i = 0; i < 16; i++)
        snprintf(buf + i * 2, 3, "%02x", uuid->bytes[i]);
    buf[32] = '\0';
}

/* ── Profile names ────────────────────────────────────────────────────────── */

const char *ot_survey_profile_name(ot_survey_profile_t profile)
{
    switch (profile) {
    case OT_PROFILE_BALANCED:      return "Balanced";
    case OT_PROFILE_WIFI_HEAVY:    return "WiFi Heavy";
    case OT_PROFILE_BLE_HEAVY:     return "BLE Heavy";
    case OT_PROFILE_154_HEAVY:     return "802.15.4 Heavy";
    case OT_PROFILE_ESPNOW_FOCUS:  return "ESP-NOW Focus";
    case OT_PROFILE_DRONE_WATCH:   return "Drone Watch";
    case OT_PROFILE_WIRELESSHART:  return "WirelessHART";
    case OT_PROFILE_THREAD_MATTER: return "Thread/Matter";
    default:                       return "Unknown";
    }
}

/* ── SD directory helpers ─────────────────────────────────────────────────── */

static esp_err_t ensure_dir(const char *path)
{
    struct stat st;
    if (stat(path, &st) == 0 && S_ISDIR(st.st_mode)) return ESP_OK;
    if (mkdir(path, 0755) != 0 && errno != EEXIST) {
        ESP_LOGE(TAG, "mkdir %s failed: %s", path, strerror(errno));
        return ESP_FAIL;
    }
    return ESP_OK;
}

/* ── Metadata writer ──────────────────────────────────────────────────────── */

/*
 * Write (or overwrite) metadata.json in the session directory.
 * Called on start (state="active") and on stop (adds end_time, obs_count).
 */
static esp_err_t write_metadata(const ot_survey_session_t *sess)
{
    char path[96];
    snprintf(path, sizeof(path), "%s/metadata.json", sess->dir_path);

    FILE *f = fopen(path, "w");
    if (!f) {
        ESP_LOGE(TAG, "Cannot open %s: %s", path, strerror(errno));
        return ESP_FAIL;
    }

    char uuid_str[33];
    ot_survey_uuid_str(&sess->uuid, uuid_str);

    const char *state_str;
    switch (sess->state) {
    case OT_STATE_ACTIVE:  state_str = "active";  break;
    case OT_STATE_PAUSED:  state_str = "paused";  break;
    case OT_STATE_STOPPED: state_str = "stopped"; break;
    case OT_STATE_ERROR:   state_str = "error";   break;
    default:               state_str = "idle";    break;
    }

    fprintf(f,
        "{\n"
        "  \"schema\": 1,\n"
        "  \"uuid\": \"%s\",\n"
        "  \"state\": \"%s\",\n"
        "  \"profile\": \"%s\",\n"
        "  \"org\": \"%s\",\n"
        "  \"site\": \"%s\",\n"
        "  \"building\": \"%s\",\n"
        "  \"zone\": \"%s\",\n"
        "  \"operator\": \"%s\",\n"
        "  \"description\": \"%s\",\n"
        "  \"start_time\": %lu,\n"
        "  \"stop_time\": %lu,\n"
        "  \"obs_count\": %lu,\n"
        "  \"privacy_flags\": %u,\n"
        "  \"geo_start\": {\"valid\": %s, \"lat\": %.6f, \"lon\": %.6f, \"alt\": %.1f, \"acc\": %.1f},\n"
        "  \"geo_end\": {\"valid\": %s, \"lat\": %.6f, \"lon\": %.6f, \"alt\": %.1f, \"acc\": %.1f}\n"
        "}\n",
        uuid_str,
        state_str,
        ot_survey_profile_name(sess->cfg.profile),
        sess->cfg.org,
        sess->cfg.site,
        sess->cfg.building,
        sess->cfg.zone,
        sess->cfg.operator_id,
        sess->cfg.description,
        (unsigned long)sess->start_time_s,
        (unsigned long)sess->stop_time_s,
        (unsigned long)sess->obs_count,
        (unsigned)sess->cfg.privacy,
        sess->geo_start.valid ? "true" : "false",
        (double)sess->geo_start.latitude, (double)sess->geo_start.longitude,
        (double)sess->geo_start.altitude_m, (double)sess->geo_start.accuracy_m,
        sess->geo_end.valid ? "true" : "false",
        (double)sess->geo_end.latitude, (double)sess->geo_end.longitude,
        (double)sess->geo_end.altitude_m, (double)sess->geo_end.accuracy_m);

    fclose(f);
    return ESP_OK;
}

/* ── Public API ───────────────────────────────────────────────────────────── */
/* ot_survey_init() (eager boot-time /sdcard/lab/otsurvey creation) was removed in
 * v2.13.99 — it always failed at boot (SD isn't mounted yet that early) and was
 * redundant with ot_survey_start()'s own directory creation below, which now
 * does both directory levels itself and is only ever called once a survey
 * actually starts. See main.c's app_main() and s_ots_start_cb() comments. */

esp_err_t ot_survey_start(const ot_survey_config_t *cfg, ot_survey_session_t *sess,
                           const ot_survey_geo_t *start_geo)
{
    if (!cfg || !sess) return ESP_ERR_INVALID_ARG;

    memset(sess, 0, sizeof(*sess));
    generate_uuid(&sess->uuid);
    memcpy(&sess->cfg, cfg, sizeof(*cfg));
    sess->state = OT_STATE_ACTIVE;
    sess->start_time_s = (uint32_t)(esp_timer_get_time() / 1000000ULL);
    if (start_geo) sess->geo_start = *start_geo;  /* else zeroed by memset above (valid=false) */

    /* Export queue for ot_survey_queue_export()/ot_survey_flush() — see their
     * doc comments. Defensive free first in case a prior session's stop()
     * was skipped (should not happen, but leaking PSRAM across many survey
     * cycles would be worse than a redundant free-of-NULL). */
    if (s_export_pending) { heap_caps_free(s_export_pending); s_export_pending = NULL; }
    s_export_pending = (obs_record_t *)heap_caps_malloc(
        (size_t)OT_EXPORT_QUEUE_CAP * sizeof(obs_record_t),
        MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (s_export_pending) {
        s_export_pending_cap = OT_EXPORT_QUEUE_CAP;
    } else {
        /* Fall back to internal RAM rather than losing the whole export path -
         * at the much smaller DRAM-fallback capacity (see OT_EXPORT_QUEUE_CAP_DRAM's
         * doc comment for why the full 2048-entry size never fits CYD2USB). */
        s_export_pending = (obs_record_t *)heap_caps_malloc(
            (size_t)OT_EXPORT_QUEUE_CAP_DRAM * sizeof(obs_record_t), MALLOC_CAP_8BIT);
        if (s_export_pending) {
            s_export_pending_cap = OT_EXPORT_QUEUE_CAP_DRAM;
        } else {
            s_export_pending_cap = 0;
            ESP_LOGW(TAG, "export queue allocation failed — obs.jsonl export disabled "
                          "this session (obs_count/obs_by_type still track normally)");
        }
    }
    s_export_pending_count   = 0;
    s_export_overflow_logged = false;

    /* Build /sdcard/lab/otsurvey/<uuid>/ */
    char uuid_str[33];
    ot_survey_uuid_str(&sess->uuid, uuid_str);
    snprintf(sess->dir_path, sizeof(sess->dir_path), "%s/%s", OT_SURVEY_ROOT, uuid_str);

    /* mkdir() is not recursive — /sdcard/lab must exist before OT_SURVEY_ROOT
     * ("/sdcard/lab/otsurvey") can be created underneath it. This used to be
     * ot_survey_init()'s job, called eagerly at boot; that always failed (SD
     * isn't mounted that early) and was removed in v2.13.99 in favor of doing
     * both directory levels here, lazily, when a survey actually starts (the
     * caller, s_ots_start_cb(), now calls ensure_sd_mounted() first). */
    esp_err_t rc = ensure_dir("/sdcard/lab");
    if (rc != ESP_OK) {
        sess->state = OT_STATE_ERROR;
        return rc;
    }
    rc = ensure_dir(OT_SURVEY_ROOT);
    if (rc != ESP_OK) {
        sess->state = OT_STATE_ERROR;
        return rc;
    }
    rc = ensure_dir(sess->dir_path);
    if (rc != ESP_OK) {
        sess->state = OT_STATE_ERROR;
        return rc;
    }

    rc = write_metadata(sess);
    if (rc != ESP_OK) {
        sess->state = OT_STATE_ERROR;
        return rc;
    }

    /* Start radio scheduler — activates survey lock and begins radio time-slicing. */
    rc = ot_radio_scheduler_start(cfg->profile);
    if (rc != ESP_OK) {
        ESP_LOGW(TAG, "Radio scheduler start failed (%d) — session active, scheduler idle", rc);
        /* Non-fatal: session is still created and can collect obs_store records;
         * radio will be statically in whatever mode the caller leaves it in. */
    }

    /* Publish the active session pointer so main-loop adapters can tap in. */
    g_active_survey = sess;

#if CONFIG_IEEE802154_ENABLED
    {
        char pcap_path[96];
        snprintf(pcap_path, sizeof(pcap_path), "%s/ieee802154.pcapng", sess->dir_path);
        s_pcapng = pcapng_open(pcap_path, PCAPNG_LINKTYPE_IEEE802_15_4_NOFCS);
        if (!s_pcapng)
            ESP_LOGW(TAG, "Failed to open PCAPNG file %s — 802.15.4 capture disabled",
                     pcap_path);
        else
            ESP_LOGI(TAG, "802.15.4 PCAPNG open: %s", pcap_path);
    }
#endif

    ESP_LOGI(TAG, "Survey started: %s profile=%s dir=%s",
             uuid_str, ot_survey_profile_name(cfg->profile), sess->dir_path);
    return ESP_OK;
}

esp_err_t ot_survey_stop(ot_survey_session_t *sess, const ot_survey_geo_t *end_geo)
{
    if (!sess) return ESP_ERR_INVALID_ARG;
    if (sess->state == OT_STATE_STOPPED) return ESP_OK;

    /* Clear active pointer before stopping so adapters stop tapping immediately. */
    if (g_active_survey == sess) g_active_survey = NULL;

    sess->state       = OT_STATE_STOPPED;
    sess->stop_time_s = (uint32_t)(esp_timer_get_time() / 1000000ULL);
    if (end_geo) sess->geo_end = *end_geo;  /* else left zeroed (valid=false) */

    /* Stop radio scheduler and release survey lock. */
    ot_radio_scheduler_stop();

#if CONFIG_IEEE802154_ENABLED
    if (s_pcapng) {
        pcapng_close(s_pcapng);
        s_pcapng = NULL;
        ESP_LOGI(TAG, "802.15.4 PCAPNG closed (%lu frames)", (unsigned long)0);
    }
#endif

    /* Drain anything queued since the last periodic flush (up to one flush
     * interval's worth) before freeing the queue, so stopping doesn't lose
     * the tail end of the session. Same unguarded-by-sd_spi_mutex I/O
     * pattern this function already has for write_metadata()/pcapng_close()
     * immediately below/above — not introducing a new risk category. */
    ot_survey_flush(sess);
    if (s_export_pending) { heap_caps_free(s_export_pending); s_export_pending = NULL; }
    s_export_pending_count = 0;
    s_export_pending_cap   = 0;

    if (sess->obs_export_dropped > 0)
        ESP_LOGW(TAG, "Survey %s: %lu observations dropped from obs.jsonl export "
                      "(export queue was full) — obs_count/obs_by_type are unaffected",
                 sess->dir_path, (unsigned long)sess->obs_export_dropped);

    esp_err_t rc = write_metadata(sess);
    if (rc != ESP_OK) {
        ESP_LOGW(TAG, "Failed to finalise metadata for %s", sess->dir_path);
        return rc;
    }

    uint32_t elapsed = sess->stop_time_s - sess->start_time_s;
    ESP_LOGI(TAG, "Survey stopped: %s elapsed=%lus obs=%lu",
             sess->dir_path, (unsigned long)elapsed, (unsigned long)sess->obs_count);
    return ESP_OK;
}

esp_err_t ot_survey_pause(ot_survey_session_t *sess)
{
    if (!sess) return ESP_ERR_INVALID_ARG;
    if (sess->state != OT_STATE_ACTIVE) return ESP_ERR_INVALID_STATE;
    sess->state = OT_STATE_PAUSED;
    /* Pause scheduler — radio goes idle, survey lock stays OFF during pause
     * so other features can be used temporarily. */
    ot_radio_scheduler_stop();
    return write_metadata(sess);
}

esp_err_t ot_survey_resume(ot_survey_session_t *sess)
{
    if (!sess) return ESP_ERR_INVALID_ARG;
    if (sess->state != OT_STATE_PAUSED) return ESP_ERR_INVALID_STATE;
    sess->state = OT_STATE_ACTIVE;
    /* Restart scheduler for the same profile. */
    ot_radio_scheduler_start(sess->cfg.profile);
    return write_metadata(sess);
}

esp_err_t ot_survey_record_obs(ot_survey_session_t *sess, obs_store_t *store,
                                const obs_record_t *rec)
{
    if (!sess || !store || !rec) return ESP_ERR_INVALID_ARG;
    if (sess->state != OT_STATE_ACTIVE) return ESP_ERR_INVALID_STATE;

    obs_record_t copy;
    memcpy(&copy, rec, sizeof(copy));

    /* Apply session privacy policy before storing. */
    if (sess->cfg.privacy != 0)
        obs_redact(&copy, sess->cfg.privacy);

    obs_record_t *stored = obs_store_add(store, &copy);
    if (stored) {
        sess->obs_count++;
        return ESP_OK;
    }

    /* Store returned NULL — it either merged into an existing slot or is full.
     * A merge is not an error; count only new records. */
    return ESP_OK;
}

void ot_survey_queue_export(ot_survey_session_t *sess, const obs_record_t *rec)
{
    if (!sess || !rec || sess->state != OT_STATE_ACTIVE) return;

    /* Centralised counting — see the header doc comment for why this used to
     * be duplicated inline across five main.c call sites. */
    sess->obs_count++;
    if (rec->obs_type < 10) sess->obs_by_type[rec->obs_type]++;

    if (!s_export_pending) return;  /* allocation failed at start() — already logged there */

    /* Bounds-check against the ACTUAL allocated capacity, not the compile-time
     * OT_EXPORT_QUEUE_CAP - a DRAM-fallback session (CYD2USB) allocated the
     * smaller OT_EXPORT_QUEUE_CAP_DRAM instead, and checking against the larger
     * constant would let s_export_pending_count walk past the real buffer. */
    if (s_export_pending_count >= s_export_pending_cap) {
        sess->obs_export_dropped++;
        if (!s_export_overflow_logged) {
            ESP_LOGW(TAG, "export queue full (%u) — dropping records from obs.jsonl until "
                          "the next flush; obs_count/obs_by_type keep counting normally",
                     s_export_pending_cap);
            s_export_overflow_logged = true;
        }
        return;
    }

    s_export_pending[s_export_pending_count++] = *rec;
}

esp_err_t ot_survey_flush(ot_survey_session_t *sess)
{
    if (!sess) return ESP_ERR_INVALID_ARG;
    if (sess->state == OT_STATE_IDLE || sess->state == OT_STATE_ERROR)
        return ESP_ERR_INVALID_STATE;

    if (s_export_pending_count == 0)
        return ESP_OK; /* nothing new to write */

    char path[96];
    snprintf(path, sizeof(path), "%s/obs.jsonl", sess->dir_path);

    FILE *f = fopen(path, "a");  /* append — only ever write records queued since last flush */
    if (!f) {
        ESP_LOGE(TAG, "Cannot open %s: %s", path, strerror(errno));
        return ESP_FAIL; /* queue is left intact — retried on the next flush call */
    }

    /* JSON serialisation buffer — min 384 bytes per obs_record_to_json() spec. */
    char buf[400];
    uint32_t written = 0;

    for (uint32_t i = 0; i < s_export_pending_count; i++) {
        int n = obs_record_to_json(&s_export_pending[i], buf, sizeof(buf));
        if (n > 0) {
            fwrite(buf, 1, (size_t)n, f);
            fputc('\n', f);
            written++;
        }
    }
    fclose(f);

    ESP_LOGI(TAG, "Flushed %lu new records (session total=%lu) to %s",
             (unsigned long)written, (unsigned long)sess->obs_count, path);

    s_export_pending_count = 0; /* drained — queue is reused, not reallocated, between flushes */
    return ESP_OK;
}

/* ── Minimal JSON field extractors ───────────────────────────────────────────
 * obs_record_to_json()/write_metadata() emit a fixed, known key set with no
 * nesting beyond the geo_start/geo_end objects (handled by search-from-offset
 * below) — a full JSON parser would be pure overhead here. These scan for
 * "key": and read the value in whichever form that key is always emitted as.
 * Not a general-purpose parser: assumes well-formed input from our own
 * writer, not arbitrary/adversarial JSON. */

static const char *json_find_key(const char *json, const char *key)
{
    char search[40];
    snprintf(search, sizeof(search), "\"%s\"", key);
    const char *p = strstr(json, search);
    if (!p) return NULL;
    p += strlen(search);
    while (*p && (*p == ' ' || *p == '\t' || *p == ':')) p++;
    return p;
}

static bool json_get_str(const char *json, const char *key, char *out, size_t out_sz)
{
    const char *p = json_find_key(json, key);
    if (!p || *p != '"') { if (out_sz) out[0] = '\0'; return false; }
    p++;
    size_t i = 0;
    while (*p && *p != '"' && i < out_sz - 1) {
        if (*p == '\\' && *(p + 1)) p++;   /* skip escape char, copy the escaped char itself */
        out[i++] = *p++;
    }
    out[i] = '\0';
    return true;
}

static bool json_get_u32(const char *json, const char *key, uint32_t *out)
{
    const char *p = json_find_key(json, key);
    if (!p) return false;
    *out = (uint32_t)strtoul(p, NULL, 10);
    return true;
}

static bool json_get_i32(const char *json, const char *key, int32_t *out)
{
    const char *p = json_find_key(json, key);
    if (!p) return false;
    *out = (int32_t)strtol(p, NULL, 10);
    return true;
}

static bool json_get_float(const char *json, const char *key, float *out)
{
    const char *p = json_find_key(json, key);
    if (!p) return false;
    *out = strtof(p, NULL);
    return true;
}

static bool json_get_bool(const char *json, const char *key, bool *out)
{
    const char *p = json_find_key(json, key);
    if (!p) return false;
    *out = (strncmp(p, "true", 4) == 0);
    return true;
}

static bool json_get_mac(const char *json, const char *key, uint8_t mac[6])
{
    const char *p = json_find_key(json, key);
    if (!p || *p != '"') return false;
    p++;
    unsigned m[6];
    if (sscanf(p, "%2x:%2x:%2x:%2x:%2x:%2x", &m[0], &m[1], &m[2], &m[3], &m[4], &m[5]) != 6)
        return false;
    for (int i = 0; i < 6; i++) mac[i] = (uint8_t)m[i];
    return true;
}

/* "ev":[1,7,10] -> evidence[], evidence_count (0-OBS_MAX_EVIDENCE) */
static uint8_t json_get_evidence(const char *json, uint8_t out[OBS_MAX_EVIDENCE])
{
    const char *p = json_find_key(json, "ev");
    if (!p || *p != '[') return 0;
    p++;
    uint8_t n = 0;
    while (*p && *p != ']' && n < OBS_MAX_EVIDENCE) {
        char *end;
        long v = strtol(p, &end, 10);
        if (end == p) break;   /* not a number — malformed, stop */
        out[n++] = (uint8_t)v;
        p = end;
        while (*p == ',' || *p == ' ') p++;
    }
    return n;
}

/* ── Results loading ─────────────────────────────────────────────────────── */

esp_err_t ot_survey_results_load(const char *session_dir, ot_survey_results_t *out,
                                  uint16_t max_entries)
{
    if (!session_dir || !out) return ESP_ERR_INVALID_ARG;
    memset(out, 0, sizeof(*out));

    /* dir_path + uuid: the caller-supplied path is OT_SURVEY_ROOT/<uuid>; pull
     * the uuid back out of the path rather than requiring a second argument. */
    strncpy(out->dir_path, session_dir, sizeof(out->dir_path) - 1);
    const char *slash = strrchr(session_dir, '/');
    strncpy(out->uuid, slash ? slash + 1 : session_dir, sizeof(out->uuid) - 1);

    /* ── metadata.json ── */
    char meta_path[96];
    snprintf(meta_path, sizeof(meta_path), "%s/metadata.json", session_dir);
    FILE *mf = fopen(meta_path, "r");
    if (!mf) return ESP_ERR_NOT_FOUND;

    fseek(mf, 0, SEEK_END);
    long meta_sz = ftell(mf);
    fseek(mf, 0, SEEK_SET);
    if (meta_sz <= 0 || meta_sz > 4096) { fclose(mf); return ESP_ERR_INVALID_SIZE; }
    char *meta_buf = heap_caps_malloc((size_t)meta_sz + 1, MALLOC_CAP_8BIT);
    if (!meta_buf) { fclose(mf); return ESP_ERR_NO_MEM; }
    fread(meta_buf, 1, (size_t)meta_sz, mf);
    fclose(mf);
    meta_buf[meta_sz] = '\0';

    json_get_str(meta_buf, "site",       out->site,       sizeof(out->site));
    json_get_str(meta_buf, "building",   out->building,   sizeof(out->building));
    json_get_str(meta_buf, "zone",       out->zone,        sizeof(out->zone));
    json_get_str(meta_buf, "operator",   out->operator_id, sizeof(out->operator_id));
    json_get_str(meta_buf, "profile",    out->profile_name, sizeof(out->profile_name));
    json_get_u32(meta_buf, "start_time", &out->start_time_s);
    json_get_u32(meta_buf, "stop_time",  &out->stop_time_s);

    /* geo_start/geo_end are nested objects with their own "lat"/"lon" keys —
     * json_find_key() finds the FIRST "lat"/"lon" in the whole buffer, which
     * is geo_start's, and the SECOND occurrence (geo_end's) needs searching
     * from after geo_start's object closes. Simple and sufficient for this
     * fixed two-object layout. */
    const char *geo_start_p = strstr(meta_buf, "\"geo_start\"");
    const char *geo_end_p   = strstr(meta_buf, "\"geo_end\"");
    if (geo_start_p) {
        json_get_bool(geo_start_p, "valid", &out->geo_start_valid);
        json_get_float(geo_start_p, "lat", &out->geo_start_lat);
        json_get_float(geo_start_p, "lon", &out->geo_start_lon);
    }
    if (geo_end_p) {
        json_get_bool(geo_end_p, "valid", &out->geo_end_valid);
        json_get_float(geo_end_p, "lat", &out->geo_end_lat);
        json_get_float(geo_end_p, "lon", &out->geo_end_lon);
    }
    heap_caps_free(meta_buf);

    /* ── obs.jsonl — exact per-type counts (full scan) + capped device list ── */
    if (max_entries > 0) {
        out->entries = (ot_result_entry_t *)heap_caps_malloc(
            (size_t)max_entries * sizeof(ot_result_entry_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (!out->entries) {
            out->entries = (ot_result_entry_t *)heap_caps_malloc(
                (size_t)max_entries * sizeof(ot_result_entry_t), MALLOC_CAP_8BIT);
        }
        out->entries_cap = out->entries ? max_entries : 0;
    }

    char obs_path[96];
    snprintf(obs_path, sizeof(obs_path), "%s/obs.jsonl", session_dir);
    FILE *of = fopen(obs_path, "r");
    if (!of) return ESP_OK;   /* metadata alone is still a valid (empty) result */

    char line[400];
    while (fgets(line, sizeof(line), of)) {
        uint32_t type_u = 0;
        if (!json_get_u32(line, "type", &type_u) || type_u >= 10) continue;
        out->obs_by_type[type_u]++;
        out->obs_count++;

        if (!out->entries) continue;   /* counts-only pass (alloc failed or max_entries==0) */

        uint8_t mac[6];
        if (!json_get_mac(line, "mac", mac)) continue;

        /* find-or-add by MAC — same idiom as obs_store_add()/espnow_find_or_add() */
        ot_result_entry_t *e = NULL;
        for (uint16_t i = 0; i < out->entries_count; i++) {
            if (memcmp(out->entries[i].mac, mac, 6) == 0) { e = &out->entries[i]; break; }
        }
        if (!e) {
            if (out->entries_count >= out->entries_cap) {
                out->entries_truncated = true;
                continue;
            }
            e = &out->entries[out->entries_count++];
            memset(e, 0, sizeof(*e));
            memcpy(e->mac, mac, 6);
            e->obs_type = (uint8_t)type_u;
            int32_t radio_i = 0;
            if (json_get_i32(line, "radio", &radio_i)) e->src_radio = (uint8_t)radio_i;
            uint32_t first_u = 0;
            if (json_get_u32(line, "first", &first_u)) e->first_seen_s = first_u;
            json_get_str(line, "label", e->label, sizeof(e->label));
        }

        int32_t rssi_i = 0, rssi_peak_i = 0, conf_i = 0;
        if (json_get_i32(line, "rssi", &rssi_i))       e->rssi_cur    = (int8_t)rssi_i;
        if (json_get_i32(line, "rssi_peak", &rssi_peak_i)) e->rssi_peak = (int8_t)rssi_peak_i;
        if (json_get_i32(line, "conf", &conf_i))       e->confidence  = (uint8_t)conf_i;
        e->evidence_count = json_get_evidence(line, e->evidence);
        uint32_t last_u = 0;
        if (json_get_u32(line, "last", &last_u)) e->last_seen_s = last_u;
        if (e->hit_count < UINT16_MAX) e->hit_count++;
    }
    fclose(of);
    return ESP_OK;
}

void ot_survey_results_free(ot_survey_results_t *out)
{
    if (!out) return;
    if (out->entries) { heap_caps_free(out->entries); out->entries = NULL; }
    out->entries_count = 0;
    out->entries_cap   = 0;
}

/* ── Session listing ──────────────────────────────────────────────────────── */

int ot_survey_list_sessions(ot_session_summary_t out[OT_SESSION_LIST_MAX], int *total_found)
{
    int found = 0;
    int listed = 0;

    DIR *d = opendir(OT_SURVEY_ROOT);
    if (!d) { if (total_found) *total_found = 0; return 0; }

    struct dirent *ent;
    /* Newest-first: sessions are UUIDv4, not sortable by name/time, so this
     * does a single pass reading every metadata.json's start_time and
     * insertion-sorts into out[] — OT_SESSION_LIST_MAX is small (40) so an
     * O(n * OT_SESSION_LIST_MAX) insertion sort is cheap next to the SD I/O
     * cost of opening each metadata.json in the first place. */
    while ((ent = readdir(d)) != NULL) {
        if (ent->d_name[0] == '.') continue;
        if (ent->d_type != DT_DIR
#ifdef DT_UNKNOWN
            && ent->d_type != DT_UNKNOWN
#endif
        ) continue;

        char meta_path[128];
        snprintf(meta_path, sizeof(meta_path), "%s/%s/metadata.json", OT_SURVEY_ROOT, ent->d_name);
        FILE *mf = fopen(meta_path, "r");
        if (!mf) continue;   /* not a session dir (or mid-write) — skip */

        char buf[512];
        size_t n = fread(buf, 1, sizeof(buf) - 1, mf);
        fclose(mf);
        buf[n] = '\0';

        ot_session_summary_t cand = {0};
        snprintf(cand.dir_path, sizeof(cand.dir_path), "%s/%s", OT_SURVEY_ROOT, ent->d_name);
        json_get_str(buf, "site", cand.site, sizeof(cand.site));
        json_get_u32(buf, "start_time", &cand.start_time_s);
        json_get_u32(buf, "obs_count",  &cand.obs_count);

        found++;

        /* Insertion-sort into out[] newest-first, keeping only the top
         * OT_SESSION_LIST_MAX by start_time_s. */
        int pos = listed < OT_SESSION_LIST_MAX ? listed : OT_SESSION_LIST_MAX - 1;
        if (listed >= OT_SESSION_LIST_MAX && cand.start_time_s <= out[pos].start_time_s)
            continue;   /* older than everything already kept — drop */
        while (pos > 0 && out[pos - 1].start_time_s < cand.start_time_s) {
            out[pos] = out[pos - 1];
            pos--;
        }
        out[pos] = cand;
        if (listed < OT_SESSION_LIST_MAX) listed++;
    }
    closedir(d);

    if (total_found) *total_found = found;
    return listed;
}

/* ── 802.15.4 PCAPNG writer ───────────────────────────────────────────────── */

#if CONFIG_IEEE802154_ENABLED
esp_err_t ot_survey_write_154_frame(const uint8_t *psdu, uint8_t psdu_len,
                                     int8_t rssi, uint8_t lqi, uint64_t ts_us)
{
    (void)rssi;  /* captured in obs_store; not embedded in PCAPNG frame body */
    (void)lqi;

    if (!psdu || psdu_len == 0) return ESP_ERR_INVALID_ARG;
    if (!s_pcapng)              return ESP_ERR_INVALID_STATE;

    pcapng_write_frame(s_pcapng, psdu, psdu_len, ts_us);
    return ESP_OK;
}
#endif /* CONFIG_IEEE802154_ENABLED */
