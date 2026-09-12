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
#include <sys/stat.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <time.h>

static const char *TAG = "ot_survey";

#if CONFIG_IEEE802154_ENABLED
/* PCAPNG file handle for the active survey session; NULL when idle. */
static pcapng_writer_t *s_pcapng = NULL;
#endif

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

esp_err_t ot_survey_init(void)
{
    /* Ensure /sdcard/lab/ exists before creating /sdcard/lab/otsurvey/.
     * Other features (wardrives, handshakes) create this lazily — we need it here. */
    ensure_dir("/sdcard/lab");
    return ensure_dir(OT_SURVEY_ROOT);
}

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

    /* Build /sdcard/lab/otsurvey/<uuid>/ */
    char uuid_str[33];
    ot_survey_uuid_str(&sess->uuid, uuid_str);
    snprintf(sess->dir_path, sizeof(sess->dir_path), "%s/%s", OT_SURVEY_ROOT, uuid_str);

    esp_err_t rc = ensure_dir(OT_SURVEY_ROOT);
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

esp_err_t ot_survey_flush(ot_survey_session_t *sess, obs_store_t *store)
{
    if (!sess || !store) return ESP_ERR_INVALID_ARG;
    if (sess->state == OT_STATE_IDLE || sess->state == OT_STATE_ERROR)
        return ESP_ERR_INVALID_STATE;

    char path[96];
    snprintf(path, sizeof(path), "%s/obs.jsonl", sess->dir_path);

    uint32_t count = obs_store_count(store);
    if (sess->flush_head >= count)
        return ESP_OK; /* nothing new to write */

    FILE *f = fopen(path, "a");  /* append — only write records added since last flush */
    if (!f) {
        ESP_LOGE(TAG, "Cannot open %s: %s", path, strerror(errno));
        return ESP_FAIL;
    }

    /* JSON serialisation buffer — min 384 bytes per obs_record_to_json() spec. */
    char buf[400];
    uint32_t written = 0;

    for (uint32_t i = sess->flush_head; i < count; i++) {
        const obs_record_t *r = &store->records[i];
        int n = obs_record_to_json(r, buf, sizeof(buf));
        if (n > 0) {
            fwrite(buf, 1, (size_t)n, f);
            fputc('\n', f);
            written++;
        }
    }
    fclose(f);

    sess->flush_head = count; /* advance cursor past written records */

    ESP_LOGI(TAG, "Flushed %lu new records (total=%lu) to %s",
             (unsigned long)written, (unsigned long)count, path);
    return ESP_OK;
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
