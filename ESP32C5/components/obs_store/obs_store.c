/*
 * obs_store.c — Passive Observation Store implementation (Schema v2)
 *
 * Portability:
 *   ESP_PLATFORM + CONFIG_SPIRAM: PSRAM allocation (NM-CYD-C5, WS-C5-28).
 *   ESP_PLATFORM without CONFIG_SPIRAM: DRAM allocation (CYD2USB — no PSRAM).
 *   No ESP_PLATFORM (host unit tests): standard heap.
 *
 * Schema v2 vs v1: record widened to 128 bytes; new OT obs_type_t values;
 * ext union at offset 88.  Base-record field offsets are unchanged.
 */

#include "obs_store.h"
#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef ESP_PLATFORM
#  include "esp_heap_caps.h"
#  ifdef CONFIG_SPIRAM
     /* PSRAM-capable board: store records in SPIRAM */
#    define OBS_MALLOC(sz)  heap_caps_malloc((sz), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)
#    define OBS_FREE(p)     heap_caps_free(p)
#  else
     /* No PSRAM (CYD2USB): fall back to DRAM.  Capacity is limited. */
#    define OBS_MALLOC(sz)  malloc(sz)
#    define OBS_FREE(p)     free(p)
#  endif
#else
#  include <stdlib.h>
#  define OBS_MALLOC(sz)  malloc(sz)
#  define OBS_FREE(p)     free(p)
#endif

/* Layout verification — catches silent struct-padding changes. */
_Static_assert(sizeof(obs_record_t) == 128,
    "obs_record_t must be exactly 128 bytes — check field order or explicit padding");

/* Base-record offsets must remain identical to schema v1. */
_Static_assert(offsetof(obs_record_t, hit_count)    == 28, "hit_count offset");
_Static_assert(offsetof(obs_record_t, first_seen_s) == 32, "first_seen_s must be 4-byte aligned");
_Static_assert(offsetof(obs_record_t, latitude)     == 40, "latitude offset");
_Static_assert(offsetof(obs_record_t, label)        == 56, "label offset");

/* ext union starts immediately after label[32]. */
_Static_assert(offsetof(obs_record_t, ext)          == 88, "ext union offset");

/* ext sub-struct sizes must each be exactly 40 bytes. */
_Static_assert(sizeof(obs_ext_ieee154_t) == 40, "obs_ext_ieee154_t must be 40 bytes");
_Static_assert(sizeof(obs_ext_espnow_t)  == 40, "obs_ext_espnow_t must be 40 bytes");
_Static_assert(sizeof(obs_ext_ble_t)     == 40, "obs_ext_ble_t must be 40 bytes");
_Static_assert(sizeof(obs_ext_drone_t)   == 40, "obs_ext_drone_t must be 40 bytes");

/* ── Privacy / redaction ─────────────────────────────────────────────────── */

void obs_redact(obs_record_t *rec, obs_privacy_flags_t policy)
{
    if (!rec) return;

    if (policy & OBS_PRIV_REDACT_GPS) {
        rec->latitude   = 0.0f;
        rec->longitude  = 0.0f;
        rec->altitude_m = 0.0f;
        rec->accuracy_m = 0.0f;
        rec->flags &= (uint8_t)~(OBS_FLAG_GPS_VALID | OBS_FLAG_GPS_STALE);
        /* Also zero any GPS carried in the drone_id ext. */
        if (rec->obs_type == OBS_TYPE_DRONE_ID) {
            rec->ext.drone_id.drone_lat = 0.0f;
            rec->ext.drone_id.drone_lon = 0.0f;
            rec->ext.drone_id.drone_alt = 0.0f;
        }
    }
    if (policy & OBS_PRIV_REDACT_MAC) {
        memset(rec->mac,      0, 6);
        memset(rec->peer_mac, 0, 6);
        /* Zero extended 802.15.4 addresses. */
        if (rec->obs_type >= OBS_TYPE_IEEE802154 && rec->obs_type <= OBS_TYPE_ZIGBEE) {
            rec->ext.ieee154.src_addr_ext   = 0;
            rec->ext.ieee154.dst_addr_ext   = 0;
            rec->ext.ieee154.src_addr_short = 0;
            rec->ext.ieee154.dst_addr_short = 0;
        }
    }
    if (policy & OBS_PRIV_REDACT_LABEL) {
        memset(rec->label, 0, sizeof(rec->label));
        /* Also zero operator_id from drone observations. */
        if (rec->obs_type == OBS_TYPE_DRONE_ID)
            memset(rec->ext.drone_id.operator_id, 0,
                   sizeof(rec->ext.drone_id.operator_id));
    }

    rec->flags |= (uint8_t)OBS_FLAG_REDACTED;
}

/* ── Store lifecycle ─────────────────────────────────────────────────────── */

bool obs_store_init(obs_store_t *store, uint32_t capacity)
{
    if (!store) return false;

    memset(store, 0, sizeof(*store));
    uint32_t cap = (capacity == 0) ? OBS_STORE_DEFAULT_CAPACITY : capacity;

    store->records = (obs_record_t *)OBS_MALLOC((size_t)cap * sizeof(obs_record_t));
    if (!store->records) return false;

    memset(store->records, 0, (size_t)cap * sizeof(obs_record_t));
    store->capacity   = cap;
    store->count      = 0;
    store->write_head = 0;
    store->overflow   = 0;
    return true;
}

void obs_store_deinit(obs_store_t *store)
{
    if (!store) return;
    if (store->records) {
        OBS_FREE(store->records);
        store->records = NULL;
    }
    store->capacity   = 0;
    store->count      = 0;
    store->write_head = 0;
    store->overflow   = 0;
}

/* ── Internal helpers ────────────────────────────────────────────────────── */

static bool mac_equal(const uint8_t a[6], const uint8_t b[6])
{
    return memcmp(a, b, 6) == 0;
}

static bool mac_is_zero(const uint8_t mac[6])
{
    for (int i = 0; i < 6; i++) if (mac[i]) return false;
    return true;
}

/*
 * Merge an incoming record into an existing slot.
 * Updates signal, timing, evidence, and confidence.
 * The ext union is NOT merged — callers update it explicitly when needed.
 */
static void merge_record(obs_record_t *dst, const obs_record_t *src)
{
    int8_t old_rssi = dst->rssi_cur;
    dst->rssi_cur   = src->rssi_cur;
    if (src->rssi_cur != OBS_RSSI_UNKNOWN && src->rssi_cur > dst->rssi_peak)
        dst->rssi_peak = src->rssi_cur;
    if (src->rssi_cur != OBS_RSSI_UNKNOWN && old_rssi != OBS_RSSI_UNKNOWN) {
        if      (src->rssi_cur > old_rssi) dst->rssi_trend = +1;
        else if (src->rssi_cur < old_rssi) dst->rssi_trend = -1;
        else                               dst->rssi_trend =  0;
    }

    if (src->last_seen_s > dst->last_seen_s)
        dst->last_seen_s = src->last_seen_s;

    if (dst->hit_count < UINT16_MAX)
        dst->hit_count++;

    for (uint8_t si = 0; si < src->evidence_count && si < OBS_MAX_EVIDENCE; si++) {
        uint8_t ev = src->evidence[si];
        if (ev == OBS_EV_NONE) continue;
        bool found = false;
        for (uint8_t di = 0; di < dst->evidence_count && di < OBS_MAX_EVIDENCE; di++) {
            if (dst->evidence[di] == ev) { found = true; break; }
        }
        if (!found && dst->evidence_count < OBS_MAX_EVIDENCE)
            dst->evidence[dst->evidence_count++] = ev;
    }
    if (src->confidence > dst->confidence)
        dst->confidence = src->confidence;

    /* Carry forward 802.15.4 WH confidence if it improves. */
    if ((dst->obs_type == OBS_TYPE_IEEE802154 || dst->obs_type == OBS_TYPE_WIRELESSHART) &&
        (src->obs_type == OBS_TYPE_IEEE802154 || src->obs_type == OBS_TYPE_WIRELESSHART)) {
        if (src->ext.ieee154.wh_confidence > dst->ext.ieee154.wh_confidence)
            dst->ext.ieee154.wh_confidence = src->ext.ieee154.wh_confidence;
    }
}

/* ── Store operations ────────────────────────────────────────────────────── */

obs_record_t *obs_store_find(obs_store_t *store, const uint8_t mac[6])
{
    if (!store || !store->records || mac_is_zero(mac)) return NULL;
    for (uint32_t i = 0; i < store->count; i++) {
        if (mac_equal(store->records[i].mac, mac))
            return &store->records[i];
    }
    return NULL;
}

obs_record_t *obs_store_add(obs_store_t *store, const obs_record_t *rec)
{
    if (!store || !store->records || !rec) return NULL;

    obs_record_t *existing = obs_store_find(store, rec->mac);
    if (existing) {
        merge_record(existing, rec);
        return existing;
    }

    uint32_t slot = store->write_head;
    if (store->count < store->capacity) {
        store->count++;
    } else {
        if (store->overflow < UINT32_MAX)
            store->overflow++;
    }

    obs_record_t *dst = &store->records[slot];
    memcpy(dst, rec, sizeof(obs_record_t));
    dst->schema_version = OBS_SCHEMA_VERSION;
    dst->hit_count      = 1;
    if (dst->rssi_cur != OBS_RSSI_UNKNOWN)
        dst->rssi_peak = dst->rssi_cur;
    dst->rssi_trend = 0;

    store->write_head = (slot + 1) % store->capacity;
    return dst;
}

bool obs_record_ev_add(obs_record_t *rec, uint8_t ev)
{
    if (!rec) return false;
    for (uint8_t i = 0; i < rec->evidence_count; i++) {
        if (rec->evidence[i] == ev) return false;
    }
    if (rec->evidence_count >= OBS_MAX_EVIDENCE) return false;
    rec->evidence[rec->evidence_count++] = ev;
    return true;
}

uint32_t obs_store_count(const obs_store_t *store)    { return store ? store->count    : 0; }
uint32_t obs_store_overflow(const obs_store_t *store) { return store ? store->overflow : 0; }

/* ── JSON serialisation ──────────────────────────────────────────────────── */

/*
 * Append protocol-specific ext fields for IEEE 802.15.4-family observations.
 * Returns bytes written or -1 on overflow.
 */
static int append_ext_ieee154(const obs_record_t *rec, char *buf, size_t buflen, size_t used)
{
    const obs_ext_ieee154_t *x = &rec->ext.ieee154;
    int n = snprintf(buf + used, buflen - used,
        ",\"pan_id\":%u,\"src_short\":%u,\"dst_short\":%u"
        ",\"src_ext\":\"%016llX\",\"dst_ext\":\"%016llX\""
        ",\"frame_type\":%u,\"frame_ver\":%u,\"seq\":%u"
        ",\"addr_mode\":%u,\"sec_level\":%u,\"lqi\":%u"
        ",\"wh_conf\":%u,\"proto_class\":%u",
        (unsigned)x->pan_id,
        (unsigned)x->src_addr_short,
        (unsigned)x->dst_addr_short,
        (unsigned long long)x->src_addr_ext,
        (unsigned long long)x->dst_addr_ext,
        (unsigned)x->frame_type, (unsigned)x->frame_version, (unsigned)x->seq_num,
        (unsigned)x->addr_mode, (unsigned)x->security_level, (unsigned)x->lqi,
        (unsigned)x->wh_confidence, (unsigned)x->proto_class);
    return n;
}

int obs_record_to_json(const obs_record_t *rec, char *buf, size_t buflen)
{
    if (!rec || !buf || buflen == 0) return -1;

    char ev_str[64] = "[";
    for (uint8_t i = 0; i < rec->evidence_count && i < OBS_MAX_EVIDENCE; i++) {
        char tmp[8];
        snprintf(tmp, sizeof(tmp), i ? ",%u" : "%u", (unsigned)rec->evidence[i]);
        strncat(ev_str, tmp, sizeof(ev_str) - strlen(ev_str) - 1);
    }
    strncat(ev_str, "]", sizeof(ev_str) - strlen(ev_str) - 1);

    /* Sanitise label: escape backslash and double-quote for JSON. */
    char safe_label[64] = {0};
    size_t si = 0;
    for (size_t li = 0; li < sizeof(rec->label) && rec->label[li] && si < sizeof(safe_label) - 3; li++) {
        char c = rec->label[li];
        if (c == '"' || c == '\\') safe_label[si++] = '\\';
        safe_label[si++] = c;
    }
    safe_label[si] = '\0';

    int n = snprintf(buf, buflen,
        "{\"v\":%u,\"radio\":%u,\"type\":%u,\"flags\":%u,"
        "\"mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\","
        "\"rssi\":%d,\"rssi_peak\":%d,\"trend\":%d,"
        "\"ch\":%u,\"phy\":%u,\"auth\":%u,"
        "\"conf\":%u,\"ev\":%s,"
        "\"hits\":%u,\"first\":%lu,\"last\":%lu,"
        "\"lat\":%.6f,\"lon\":%.6f,\"alt\":%.1f,\"acc\":%.1f,"
        "\"label\":\"%s\"",
        (unsigned)rec->schema_version,
        (unsigned)rec->src_radio,
        (unsigned)rec->obs_type,
        (unsigned)rec->flags,
        rec->mac[0], rec->mac[1], rec->mac[2],
        rec->mac[3], rec->mac[4], rec->mac[5],
        (int)rec->rssi_cur, (int)rec->rssi_peak, (int)rec->rssi_trend,
        (unsigned)rec->channel, (unsigned)rec->phy, (unsigned)rec->auth_mode,
        (unsigned)rec->confidence, ev_str,
        (unsigned)rec->hit_count,
        (unsigned long)rec->first_seen_s,
        (unsigned long)rec->last_seen_s,
        (double)rec->latitude, (double)rec->longitude,
        (double)rec->altitude_m, (double)rec->accuracy_m,
        safe_label);

    if (n < 0 || (size_t)n >= buflen) return -1;
    size_t used = (size_t)n;

    /* Append protocol-specific ext fields. */
    int ext_n = 0;
    switch ((obs_type_t)rec->obs_type) {
    case OBS_TYPE_IEEE802154:
    case OBS_TYPE_WIRELESSHART:
    case OBS_TYPE_THREAD_MATTER:
    case OBS_TYPE_ZIGBEE:
        ext_n = append_ext_ieee154(rec, buf, buflen, used);
        break;
    case OBS_TYPE_ESPNOW_OT: {
        const obs_ext_espnow_t *e = &rec->ext.espnow;
        ext_n = snprintf(buf + used, buflen - used,
            ",\"plen\":%u,\"ttl\":%u",
            (unsigned)e->payload_len, (unsigned)e->espnow_ttl);
        break;
    }
    case OBS_TYPE_BLE_ADV:
    case OBS_TYPE_BLE_EXT: {
        const obs_ext_ble_t *b = &rec->ext.ble;
        /* addr_sub: 0=public 1=static 2=resolvable-private(rotates) 3=non-resolvable-private(rotates) 4=unknown */
        ext_n = snprintf(buf + used, buflen - used,
            ",\"addr_sub\":%u", (unsigned)b->addr_subtype);
        break;
    }
    case OBS_TYPE_DRONE_ID: {
        const obs_ext_drone_t *d = &rec->ext.drone_id;
        /* Sanitise operator_id: it may contain arbitrary bytes from RF. */
        char safe_opid[24] = {0};
        size_t oi = 0;
        for (size_t li = 0; li < sizeof(d->operator_id) && d->operator_id[li] && oi < sizeof(safe_opid) - 3; li++) {
            char c = d->operator_id[li];
            if (c == '"' || c == '\\') safe_opid[oi++] = '\\';
            safe_opid[oi++] = c;
        }
        safe_opid[oi] = '\0';
        ext_n = snprintf(buf + used, buflen - used,
            ",\"op_id\":\"%s\",\"d_lat\":%.6f,\"d_lon\":%.6f,\"d_alt\":%.1f"
            ",\"id_type\":%u,\"ua_type\":%u",
            safe_opid,
            (double)d->drone_lat, (double)d->drone_lon, (double)d->drone_alt,
            (unsigned)d->id_type, (unsigned)d->ua_type);
        break;
    }
    default:
        break;
    }

    if (ext_n < 0) return -1;
    used += (size_t)ext_n;
    if (used + 2 >= buflen) return -1;

    buf[used++] = '}';
    buf[used]   = '\0';
    return (int)used;
}

/* ── Detector registry ───────────────────────────────────────────────────── */

void obs_registry_init(obs_registry_t *reg)
{
    if (!reg) return;
    memset(reg, 0, sizeof(*reg));
}

bool obs_registry_register(obs_registry_t *reg, const obs_detector_t *det)
{
    if (!reg || !det || reg->count >= OBS_REGISTRY_MAX) return false;
    reg->detectors[reg->count++] = det;
    return true;
}

int obs_registry_run(obs_registry_t *reg, obs_record_t *rec)
{
    if (!reg || !rec) return 0;
    int classified = 0;
    for (uint8_t i = 0; i < reg->count; i++) {
        const obs_detector_t *d = reg->detectors[i];
        if (d && d->analyse && d->analyse(rec)) {
            classified++;
            break; /* first-match wins */
        }
    }
    return classified;
}
