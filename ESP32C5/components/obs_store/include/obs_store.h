/*
 * obs_store.h — Passive Observation Store (Schema v2)
 *
 * Fixed-size observation records, bounded PSRAM-backed store, privacy/redaction
 * policy, and detector registry interface for CYM passive wireless observation.
 *
 * Schema v2 changes vs v1:
 *   - Record widened from 88 to 128 bytes.
 *   - New obs_type_t values: IEEE802154, WIRELESSHART, THREAD_MATTER, ZIGBEE,
 *     ESPNOW_OT, DRONE_ID.
 *   - New obs_radio_t values: IEEE802154, ESPNOW.
 *   - New evidence tags: OBS_EV_154_PAN_COORD, OBS_EV_154_CHAN_HOP,
 *     OBS_EV_WH_TIMING, OBS_EV_WH_NET_LAYER.
 *   - 40-byte ext union appended after label[].  Existing base-record fields
 *     are byte-for-byte identical to v1 — only schema_version changes.
 *   - PSRAM macro falls back to DRAM on non-SPIRAM builds (CYD2USB).
 *
 * Intentionally free of ESP-IDF types so this header can be included in host
 * unit tests compiled with plain gcc.  Adapters that bridge ESP-IDF structures
 * into obs_record_t live in main.c.
 *
 * Memory budget (512-record default store, PSRAM):
 *   sizeof(obs_record_t) == 128 bytes
 *   512 records x 128 bytes = 65,536 bytes (64 KB PSRAM)
 */

#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* ── Schema version ─────────────────────────────────────────────────────── */
#define OBS_SCHEMA_VERSION   2

/* ── Radio source ────────────────────────────────────────────────────────── */
typedef enum {
    OBS_RADIO_WIFI       = 0,
    OBS_RADIO_BLE        = 1,
    OBS_RADIO_IEEE802154 = 2,   /* IEEE 802.15.4 2.4 GHz PHY (C5 only) */
    OBS_RADIO_ESPNOW     = 3,   /* ESP-NOW frames captured via WiFi promiscuous */
} obs_radio_t;

/* ── Observation type ────────────────────────────────────────────────────── */
typedef enum {
    OBS_TYPE_WIFI_AP       = 0,   /* WiFi AP beacon / probe response */
    OBS_TYPE_WIFI_CLIENT   = 1,   /* WiFi client (associated or probing) */
    OBS_TYPE_BLE_ADV       = 2,   /* BLE legacy advertising (1M PHY) */
    OBS_TYPE_BLE_EXT       = 3,   /* BLE 5.0 extended advertising */
    OBS_TYPE_IEEE802154    = 4,   /* Generic 802.15.4 frame (stack TBD) */
    OBS_TYPE_WIRELESSHART  = 5,   /* WirelessHART classified (IEC 62591) */
    OBS_TYPE_THREAD_MATTER = 6,   /* Thread / Matter stack */
    OBS_TYPE_ZIGBEE        = 7,   /* Zigbee PRO stack */
    OBS_TYPE_ESPNOW_OT     = 8,   /* ESP-NOW OT survey observation */
    OBS_TYPE_DRONE_ID      = 9,   /* OpenDroneID Remote ID */
} obs_type_t;

/* ── IEEE 802.15.4 protocol classification ───────────────────────────────── */
typedef enum {
    OBS_154_CLASS_UNKNOWN      = 0,   /* 802.15.4 confirmed, stack unknown */
    OBS_154_CLASS_ZIGBEE       = 1,   /* Zigbee PRO stack_profile detected */
    OBS_154_CLASS_THREAD       = 2,   /* Thread/Matter stack detected */
    OBS_154_CLASS_WIRELESSHART = 3,   /* WirelessHART classified */
    OBS_154_CLASS_ISA100       = 4,   /* ISA100.11a classified */
    OBS_154_CLASS_GENERIC      = 5,   /* 802.15.4, stack unresolvable */
} obs_154_class_t;

/* ── PHY indicator ───────────────────────────────────────────────────────── */
typedef enum {
    OBS_PHY_UNKNOWN   = 0,
    OBS_PHY_11B       = 1,   /* 802.11b DSSS */
    OBS_PHY_11G       = 2,   /* 802.11g OFDM */
    OBS_PHY_11N       = 3,   /* 802.11n HT */
    OBS_PHY_11AC      = 4,   /* 802.11ac VHT */
    OBS_PHY_11AX      = 5,   /* 802.11ax HE (WiFi 6) */
    OBS_PHY_BLE_1M    = 6,   /* BLE 1M PHY */
    OBS_PHY_BLE_2M    = 7,   /* BLE 2M PHY */
    OBS_PHY_BLE_CODED = 8,   /* BLE Coded PHY (long range) */
    OBS_PHY_154_OQPSK = 9,   /* IEEE 802.15.4 O-QPSK 2.4 GHz */
} obs_phy_t;

/* ── Record flags (bitmask in obs_record_t.flags) ───────────────────────── */
#define OBS_FLAG_RANDOM_ADDR    (1u << 0)  /* BLE random / resolvable address */
#define OBS_FLAG_GPS_VALID      (1u << 1)  /* live GPS fix at first_seen */
#define OBS_FLAG_GPS_STALE      (1u << 2)  /* GPS held from last-known position */
#define OBS_FLAG_REDACTED       (1u << 3)  /* privacy redaction applied */
#define OBS_FLAG_HIDDEN_SSID    (1u << 4)  /* WiFi: SSID not broadcast */
#define OBS_FLAG_CARRIER_HIT    (1u << 5)  /* nRF24 RPD carrier flag (not RSSI) */
#define OBS_FLAG_PMF_INFERRED   (1u << 6)  /* WiFi: PMF inferred, not RSN IE */
#define OBS_FLAG_154_SEC        (1u << 7)  /* 802.15.4 security-enabled bit set */

#define OBS_RSSI_UNKNOWN  ((int8_t)-128)
#define OBS_CHAN_UNKNOWN  ((uint8_t)0)

/* ── Evidence tags ───────────────────────────────────────────────────────── */
#define OBS_MAX_EVIDENCE  4

typedef enum {
    OBS_EV_NONE           = 0,
    OBS_EV_OUI_MATCH      = 1,   /* MAC OUI matched a known vendor prefix */
    OBS_EV_SVC_UUID       = 2,   /* BLE service UUID matched a known profile */
    OBS_EV_MFR_DATA       = 3,   /* manufacturer-specific data matched a pattern */
    OBS_EV_SSID_PATTERN   = 4,   /* WiFi SSID matched a watchlist pattern */
    OBS_EV_RATE_ANOMALY   = 5,   /* TX rate outside baseline */
    OBS_EV_RSSI_ANOMALY   = 6,   /* RSSI deviation exceeds baseline variance */
    OBS_EV_RECURRENCE     = 7,   /* device appears in 2+ independent scan sessions */
    OBS_EV_154_PAN_COORD  = 8,   /* 802.15.4 frame from PAN coordinator */
    OBS_EV_154_CHAN_HOP   = 9,   /* TDMA / channel-hopping behaviour observed */
    OBS_EV_WH_TIMING      = 10,  /* WirelessHART-consistent TX timing pattern */
    OBS_EV_WH_NET_LAYER   = 11,  /* WirelessHART network-layer header decoded */
} obs_evidence_t;

/* ── BLE address subtype ─────────────────────────────────────────────────── */
/*
 * Derived passively from the top 2 bits of a BLE random address (no pairing
 * needed) — see BT Core spec Vol 6, Part B, 1.3.2. A stable persistent BLE
 * identity (the IRK-resolved identity address) requires actually bonding
 * with the device, which OT Survey deliberately never does (passive-only,
 * never transmits/connects). This is the closest passively-available signal
 * to "will this MAC still mean the same device next time": PUBLIC and
 * STATIC addresses persist across a session; RPA/NRPA are expected to
 * rotate (RPA typically every ~15 min) — a run of new-looking MACs may
 * still be the same physical device.
 */
typedef enum {
    OBS_BLE_ADDR_PUBLIC  = 0,   /* fixed, manufacturer-assigned */
    OBS_BLE_ADDR_STATIC  = 1,   /* random, top 2 bits 11 — persists until reboot/reset */
    OBS_BLE_ADDR_RPA     = 2,   /* resolvable private, top 2 bits 10 — rotates; needs IRK to resolve */
    OBS_BLE_ADDR_NRPA    = 3,   /* non-resolvable private, top 2 bits 00 — rotates, no identity relation */
    OBS_BLE_ADDR_UNKNOWN = 4,   /* reserved bit pattern (01) — should not occur on real hardware */
} obs_ble_addr_subtype_t;

/* ── Protocol-specific ext payloads (40 bytes each) ─────────────────────── */

/*
 * IEEE 802.15.4 / WirelessHART / Zigbee / Thread extension.
 * Used when obs_type is OBS_TYPE_IEEE802154 / WIRELESSHART / ZIGBEE / THREAD_MATTER.
 *
 * src_addr_ext and dst_addr_ext hold EUI-64 (8-byte) extended addresses when
 * addr_mode == OBS_154_ADDR_EXT; short addresses are in src_addr_short /
 * dst_addr_short with the upper 6 bytes of the ext fields zeroed.
 *
 * wh_confidence is set by the WirelessHART classifier (0=unclassified,
 * 40-69=possible, 70-89=probable, 90-100=confirmed).
 */
typedef struct {
    uint64_t src_addr_ext;     /*  8 — EUI-64 source; zero if addr_mode == SHORT */
    uint64_t dst_addr_ext;     /*  8 — EUI-64 destination */
    uint16_t pan_id;           /*  2 — IEEE 802.15.4 PAN identifier */
    uint16_t src_addr_short;   /*  2 — short source address (0xFFFF = broadcast) */
    uint16_t dst_addr_short;   /*  2 — short destination address */
    uint8_t  frame_type;       /*  1 — 0=beacon, 1=data, 2=ack, 3=mac_cmd */
    uint8_t  frame_version;    /*  1 — 0=802.15.4-2003, 1=802.15.4-2006/2011 */
    uint8_t  seq_num;          /*  1 — DSN / BSN */
    uint8_t  addr_mode;        /*  1 — 0=none, 2=short, 3=extended */
    uint8_t  security_level;   /*  1 — 0=none; 1-7 per 802.15.4 security suite */
    uint8_t  lqi;              /*  1 — link quality indicator (0-255) */
    uint8_t  wh_confidence;    /*  1 — WirelessHART confidence (0-100) */
    uint8_t  proto_class;      /*  1 — obs_154_class_t */
    uint8_t  _pad[10];         /* 10 — reserved for future fields */
    /* Total: 8+8+2+2+2+1+1+1+1+1+1+1+1+10 = 40 bytes */
} obs_ext_ieee154_t;

/*
 * ESP-NOW OT survey extension.
 * payload_excerpt holds the first 32 bytes of the unencrypted ESP-NOW payload
 * (or as much as was captured before encryption).
 */
typedef struct {
    uint8_t  payload_excerpt[32]; /* 32 — first 32 bytes of payload */
    uint8_t  payload_len;         /*  1 — actual payload length (may exceed 32) */
    uint8_t  espnow_ttl;          /*  1 — ESP-NOW TTL field if present */
    uint8_t  _pad[6];             /*  6 — reserved */
    /* Total: 32+1+1+6 = 40 bytes */
} obs_ext_espnow_t;

/*
 * BLE advertisement extension.
 * addr_subtype is the only field populated today (see obs_ble_addr_subtype_t
 * above); the rest is reserved for a future known-device IRK resolving-list
 * feature (bonded devices only — see the header comment on
 * obs_ble_addr_subtype_t for why arbitrary strangers' devices can't get a
 * stable ID passively).
 */
typedef struct {
    uint8_t addr_subtype;    /*  1 — obs_ble_addr_subtype_t */
    uint8_t _pad[39];        /* 39 — reserved */
    /* Total: 1+39 = 40 bytes */
} obs_ext_ble_t;

/*
 * OpenDroneID / Drone Remote ID extension.
 * drone_lat/lon/alt carry the position reported in the Remote ID frame (the
 * drone's self-reported position, not the observer's GPS position).
 */
typedef struct {
    char    operator_id[20]; /* 20 — operator ID from ASTM F3411 / ASD-STAN 4709 */
    float   drone_lat;       /*  4 — self-reported drone latitude */
    float   drone_lon;       /*  4 — self-reported drone longitude */
    float   drone_alt;       /*  4 — self-reported drone altitude (m WGS-84) */
    uint8_t id_type;         /*  1 — UAS ID type (0=none,1=serial,2=CAA,3=UTM,4=specific) */
    uint8_t ua_type;         /*  1 — UA type (0=none,1=aeroplane,2=heli,3=gyro...) */
    uint8_t _pad[6];         /*  6 — reserved */
    /* Total: 20+4+4+4+1+1+6 = 40 bytes */
} obs_ext_drone_t;

/* ── Core observation record (schema v2, 128 bytes) ─────────────────────── */
/*
 * Base layout (bytes 0-87) is identical to schema v1 — existing code that
 * does not use the ext union continues to work unchanged.
 *
 * ext union occupies bytes 88-127.  Which member is active is indicated by
 * obs_type (OBS_TYPE_IEEE802154 / ZIGBEE / THREAD_MATTER / WIRELESSHART
 * → ext.ieee154; OBS_TYPE_ESPNOW_OT → ext.espnow; OBS_TYPE_BLE_ADV /
 * OBS_TYPE_BLE_EXT → ext.ble; OBS_TYPE_DRONE_ID → ext.drone_id; all
 * others → ext.raw is zeroed).
 *
 * Field ordering satisfies natural alignment on 32-bit RISC-V; a
 * _Static_assert in obs_store.c confirms sizeof == 128.
 */
typedef struct {
    /* Provenance — 4 bytes */
    uint8_t  schema_version;     /* always OBS_SCHEMA_VERSION (2) */
    uint8_t  src_radio;          /* obs_radio_t */
    uint8_t  obs_type;           /* obs_type_t */
    uint8_t  flags;              /* OBS_FLAG_* bitmask */

    /* Identity — 12 bytes */
    uint8_t  mac[6];             /* BSSID (WiFi), BLE address, 802.15.4 EUI-64 LSBs */
    uint8_t  peer_mac[6];        /* associated peer; zeroed if not applicable */

    /* Signal — 4 bytes */
    int8_t   rssi_cur;           /* most recent RSSI (dBm); OBS_RSSI_UNKNOWN if N/A */
    int8_t   rssi_peak;          /* highest RSSI seen */
    int8_t   rssi_trend;         /* +1 stronger, 0 stable, -1 weaker vs previous */
    uint8_t  channel;            /* primary channel; OBS_CHAN_UNKNOWN if N/A */

    /* PHY / auth — 2 bytes */
    uint8_t  phy;                /* obs_phy_t */
    uint8_t  auth_mode;          /* wifi_auth_mode_t raw value; 0 for non-WiFi */

    /* Classifier — 6 bytes */
    uint8_t  confidence;         /* 0-100 detector confidence; 0 = unclassified */
    uint8_t  evidence_count;     /* valid entries in evidence[] */
    uint8_t  evidence[OBS_MAX_EVIDENCE]; /* obs_evidence_t values */

    /* Timing — 2 + 2-byte pad + 8 bytes */
    uint16_t hit_count;          /* observations seen; caps at UINT16_MAX */
    uint8_t  _pad[2];            /* explicit pad: keeps first_seen_s 4-byte aligned */
    uint32_t first_seen_s;       /* UTC epoch seconds; 0 if clock not set */
    uint32_t last_seen_s;        /* UTC epoch seconds of most recent observation */

    /* GPS — 16 bytes */
    float    latitude;           /* decimal degrees; 0.0 if GPS unavailable */
    float    longitude;
    float    altitude_m;
    float    accuracy_m;         /* ~150.0 when held from last-known position */

    /* Label — 32 bytes */
    char     label[32];          /* SSID or BLE/device name; may be empty */

    /* Protocol-specific extension — 40 bytes (bytes 88-127) */
    union {
        obs_ext_ieee154_t ieee154;   /* OBS_TYPE_IEEE802154 / WIRELESSHART / ZIGBEE */
        obs_ext_espnow_t  espnow;    /* OBS_TYPE_ESPNOW_OT */
        obs_ext_ble_t     ble;       /* OBS_TYPE_BLE_ADV / OBS_TYPE_BLE_EXT */
        obs_ext_drone_t   drone_id;  /* OBS_TYPE_DRONE_ID */
        uint8_t           raw[40];   /* zeroed for WiFi type */
    } ext;
} obs_record_t; /* expected sizeof == 128 */

/* ── Privacy / redaction policy ──────────────────────────────────────────── */
#define OBS_PRIV_REDACT_GPS    (1u << 0)  /* zero latitude, longitude, altitude, accuracy */
#define OBS_PRIV_REDACT_MAC    (1u << 1)  /* zero mac, peer_mac and ext address fields */
#define OBS_PRIV_REDACT_LABEL  (1u << 2)  /* clear label field */
typedef uint8_t obs_privacy_flags_t;

void obs_redact(obs_record_t *rec, obs_privacy_flags_t policy);

/* ── Bounded store ───────────────────────────────────────────────────────── */
#define OBS_STORE_DEFAULT_CAPACITY  512u

typedef struct {
    obs_record_t *records;
    uint32_t      capacity;
    uint32_t      count;
    uint32_t      write_head;
    uint32_t      overflow;
} obs_store_t;

bool          obs_store_init(obs_store_t *store, uint32_t capacity);
void          obs_store_deinit(obs_store_t *store);
obs_record_t *obs_store_add(obs_store_t *store, const obs_record_t *rec);
obs_record_t *obs_store_find(obs_store_t *store, const uint8_t mac[6]);
uint32_t      obs_store_count(const obs_store_t *store);
uint32_t      obs_store_overflow(const obs_store_t *store);

/* ── Serialisation ───────────────────────────────────────────────────────── */
/*
 * Serialise one record to a JSONL-compatible single-line JSON string.
 * Base fields plus protocol-specific ext fields are emitted.
 * Always null-terminates buf.  Returns bytes written (excl. NUL) or -1 if
 * buf is too small.  Recommended minimum: 384 bytes (ext fields add ~100).
 */
int  obs_record_to_json(const obs_record_t *rec, char *buf, size_t buflen);
bool obs_record_ev_add(obs_record_t *rec, uint8_t ev);

/* ── Detector registry ───────────────────────────────────────────────────── */
typedef struct {
    const char *name;
    uint8_t     version;
    bool      (*analyse)(obs_record_t *rec);
} obs_detector_t;

#define OBS_REGISTRY_MAX  8u

typedef struct {
    const obs_detector_t *detectors[OBS_REGISTRY_MAX];
    uint8_t               count;
} obs_registry_t;

void obs_registry_init(obs_registry_t *reg);
bool obs_registry_register(obs_registry_t *reg, const obs_detector_t *det);
int  obs_registry_run(obs_registry_t *reg, obs_record_t *rec);
