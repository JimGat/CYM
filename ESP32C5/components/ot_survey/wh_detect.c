/*
 * wh_detect.c — WirelessHART heuristic classifier
 * No ESP-IDF dependencies; only stdint / stdbool.
 */

#include "wh_detect.h"

/* ── Internal helpers ─────────────────────────────────────────────────────── */

static wh_pan_entry_t *find_or_alloc(wh_pan_table_t *tbl, uint16_t pan_id)
{
    /* Search for existing slot. */
    for (unsigned i = 0; i < WH_PAN_TABLE_SIZE; i++) {
        if (tbl->entries[i].pan_id == pan_id)
            return &tbl->entries[i];
    }
    /* Allocate new slot if space available. */
    if (tbl->count < WH_PAN_TABLE_SIZE) {
        wh_pan_entry_t *e = &tbl->entries[tbl->count++];
        e->pan_id      = pan_id;
        e->chan_mask   = 0;
        e->frame_count = 0;
        e->has_secured = 0;
        e->has_beacon  = 0;
        return e;
    }
    /* Table full — find the least-recently-used slot (lowest frame_count). */
    wh_pan_entry_t *lru = &tbl->entries[0];
    for (unsigned i = 1; i < WH_PAN_TABLE_SIZE; i++) {
        if (tbl->entries[i].frame_count < lru->frame_count)
            lru = &tbl->entries[i];
    }
    lru->pan_id      = pan_id;
    lru->chan_mask   = 0;
    lru->frame_count = 0;
    lru->has_secured = 0;
    lru->has_beacon  = 0;
    return lru;
}

static const wh_pan_entry_t *find_entry(const wh_pan_table_t *tbl, uint16_t pan_id)
{
    for (unsigned i = 0; i < WH_PAN_TABLE_SIZE; i++) {
        if (tbl->entries[i].pan_id == pan_id)
            return &tbl->entries[i];
    }
    return NULL;
}

/* Count set bits (channels seen) in a 16-bit mask. */
static uint8_t popcount16(uint16_t v)
{
    uint8_t n = 0;
    while (v) { n += (v & 1u); v >>= 1; }
    return n;
}

/* ── Public API ───────────────────────────────────────────────────────────── */

void wh_detect_update(wh_pan_table_t *tbl, uint16_t pan_id,
                      uint8_t frame_type, uint8_t security_en, uint8_t channel)
{
    if (!tbl || pan_id == 0xFFFFu) return;   /* broadcast / no PAN */
    if (channel < 11 || channel > 26)        return;

    wh_pan_entry_t *e = find_or_alloc(tbl, pan_id);
    if (!e) return;

    /* Mark this channel as seen. */
    e->chan_mask |= (uint16_t)(1u << (channel - 11u));
    if (e->frame_count < 0xFFFFu) e->frame_count++;
    if (security_en)               e->has_secured = 1;
    if (frame_type == 0)           e->has_beacon  = 1;
}

uint8_t wh_detect_score(const wh_pan_table_t *tbl, uint16_t pan_id,
                        uint8_t frame_type, uint8_t frame_version,
                        uint8_t security_en, uint8_t addr_mode)
{
    (void)frame_type;   /* reserved for future beacon-payload analysis */

    if (!tbl || pan_id == 0xFFFFu) return 0;

    int score = 0;

    /* Feature: mandatory security (WirelessHART always enables AES-128 CCM*). */
    if (security_en) score += 20;

    /* Feature: frame version 0 (802.15.4-2006; Thread uses version 2). */
    if (frame_version == 0) score += 5;

    /* Feature: short addressing (WH field devices use 16-bit short addresses). */
    if (addr_mode == 2) score += 5;

    /* Feature: multi-channel PAN sighting — the primary WirelessHART discriminator.
     * WH TDMA channel hopping means the same PAN appears on many channels;
     * Zigbee typically stays on one channel. */
    const wh_pan_entry_t *e = find_entry(tbl, pan_id);
    if (e) {
        uint8_t ch_count = popcount16(e->chan_mask);
        if      (ch_count >= 4) score += 70;
        else if (ch_count >= 3) score += 50;
        else if (ch_count >= 2) score += 30;

        if (e->has_beacon) score += 5;
    }

    return (score > 100) ? 100 : (uint8_t)score;
}
