/*
 * wh_detect.h — WirelessHART heuristic classifier for 802.15.4 frames
 *
 * Maintains a compact per-session PAN table that tracks which channels each
 * PAN ID has been observed on.  WirelessHART is uniquely identified by the
 * combination of:
 *   (a) AES-128 CCM* security MANDATORY on every frame, and
 *   (b) TDMA channel hopping — the same PAN appears on many channels over
 *       time (WH uses all 16 channels 11-26 in its default channel plan).
 *
 * Scoring thresholds (wh_confidence field in obs_ext_ieee154_t):
 *   0  - 39  : OBS_154_CLASS_UNKNOWN   — no evidence
 *  40  - 69  : probable unknown       — 1 distinguishing feature
 *  70  - 89  : OBS_154_CLASS_WIRELESSHART probable
 *  90  - 100 : OBS_154_CLASS_WIRELESSHART confirmed
 *
 * PASSIVE ONLY — this component never transmits.
 * No ESP-IDF dependencies (only stdint / stdbool / string).
 */

#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

/* Maximum number of distinct PAN IDs tracked per survey session. */
#define WH_PAN_TABLE_SIZE   32u

/*
 * Per-PAN tracking slot.
 * chan_mask: bit k set  ↔  channel (11 + k) observed, k ∈ [0, 15].
 * Total memory: 32 × 8 bytes = 256 bytes in DRAM.
 */
typedef struct {
    uint16_t pan_id;        /* PAN identifier; 0xFFFF = empty slot */
    uint16_t chan_mask;     /* channels observed: bit 0 = ch11, bit 15 = ch26 */
    uint16_t frame_count;   /* total frames observed on this PAN */
    uint8_t  has_secured;   /* ≥1 secured frame seen on this PAN */
    uint8_t  has_beacon;    /* ≥1 beacon frame seen on this PAN */
} wh_pan_entry_t;

typedef struct {
    wh_pan_entry_t entries[WH_PAN_TABLE_SIZE];
    uint8_t        count;   /* entries in use */
} wh_pan_table_t;

/* ── API ─────────────────────────────────────────────────────────────────── */

/*
 * wh_detect_reset — zero the table.  Call at the start of each survey session.
 */
static inline void wh_detect_reset(wh_pan_table_t *tbl)
{
    memset(tbl, 0, sizeof(*tbl));
    /* Mark all slots as empty. */
    for (unsigned i = 0; i < WH_PAN_TABLE_SIZE; i++)
        tbl->entries[i].pan_id = 0xFFFFu;
}

/*
 * wh_detect_update — record the observation of a frame on this PAN + channel.
 * frame_type: 0=beacon, 1=data, 2=ack, 3=mac_cmd  (FCF bits 0-2).
 * security_en: 1 if FCF bit 3 is set.
 * channel: 11-26.
 */
void wh_detect_update(wh_pan_table_t *tbl, uint16_t pan_id,
                      uint8_t frame_type, uint8_t security_en, uint8_t channel);

/*
 * wh_detect_score — compute a WirelessHART confidence value 0-100.
 *
 * Uses both the accumulated PAN table state AND the current frame's fields.
 * Returns 0 when pan_id == 0xFFFF (broadcast / unknown PAN).
 *
 * Scoring model:
 *   security_en flag                    : +20
 *   frame_version == 0 (WH uses 2006)  : +5
 *   short addressing (addr_mode == 2)  : +5
 *   PAN seen on 2+ channels             : +30
 *   PAN seen on 3+ channels             : +50 (replaces +30)
 *   PAN seen on 4+ channels             : +70 (replaces +50)
 *   beacon seen on this PAN             : +5
 *
 * Maximum achievable: 20+5+5+70+5 = 105 → clamped to 100.
 *
 * WirelessHART confirmed path:
 *   security + 4 channels = 20 + 70 = 90 → confirmed.
 */
uint8_t wh_detect_score(const wh_pan_table_t *tbl, uint16_t pan_id,
                        uint8_t frame_type, uint8_t frame_version,
                        uint8_t security_en, uint8_t addr_mode);
