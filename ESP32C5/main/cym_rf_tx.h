#pragma once
// ─────────────────────────────────────────────────────────────────────────────
// Central management-frame TX chokepoint (ESP32-C5 dual-band).
//
// Every raw esp_wifi_80211_tx() used to send a management frame (deauth / disassoc /
// SAE / drone-RID spoof) funnels through cym_mgmt_tx() instead. It is currently an
// UNCONDITIONAL passthrough: CYM deliberately ships WITHOUT RF self-restrictions.
//
// Rationale (@birolt29, 2026-09-22): this is a defensive-security research tool run on
// the operator's OWN devices, behind a startup legal notice; peer firmwares (Ghost ESP,
// Marauder) don't self-restrict either, and enforcing regional / DFS radio law in
// firmware is the operator's responsibility, not the firmware's. An earlier build gated
// 5 GHz DFS TX (ch 52-144, no CAC on C5) and weighed a region-aware 149-165 gate; both
// were dropped by decision — we don't limit features "just in case", and device TX power
// is low. Any firmware-level RF policy is the upstream maintainer's call to make on the
// public release, not something a contributor should pre-impose here.
//
// The wrapper is KEPT (not reverted to raw calls) purely as the single point all
// mgmt-frame TX passes through, so if such a policy IS ever wanted (a region gate, a
// per-feature interlock) it is one edit here instead of at 10 call sites.
// ─────────────────────────────────────────────────────────────────────────────
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static inline esp_err_t cym_mgmt_tx(wifi_interface_t ifx, const void *buffer,
                                    int len, bool en_sys_seq)
{
    return esp_wifi_80211_tx(ifx, buffer, len, en_sys_seq);
}

// ─────────────────────────────────────────────────────────────────────────────
// Dual-band TX readiness (ESP32-C5). Call ONCE before a channel-hopping TX loop
// (deauth / disassoc / SAE / blackout) so esp_wifi_set_channel() will actually
// accept a 5 GHz target channel. Two independent levers, BOTH required:
//
//   1. band mode AUTO  — without it a set_channel() for a 5 GHz channel is
//      SILENTLY rejected: no error returned, the radio just stays on its last
//      2.4 GHz channel, so the frame goes out on the wrong band. The driver
//      inherits whatever band mode the previous WiFi user left (e.g. 2G_ONLY
//      forced by a WPA-sec / wardrive upload), so this must be re-asserted.
//   2. MANUAL country + full 5 GHz mask (0x1FFFFFFE = bits 1-28 = ch 36-177) —
//      makes the radio accept DFS / upper-5 GHz channels (esp. EU 100-144) that
//      the AUTO regdomain intermittently blocks. cc is cosmetic under MANUAL
//      (2.4 GHz governed by schan/nchan = ch 1-13, 5 GHz entirely by the mask).
//      Full mask = no self-restriction, matching this file's RF policy: we TX on
//      whatever channel the operator's selected target actually occupies.
//
// This mirrors the proven Handshaker path (band AUTO at main.c:12645 +
// hs_apply_country's MANUAL 5G mask at main.c:11478). It is mode-agnostic — the
// calling feature owns its WiFi mode (APSTA for AP-iface TX, STA for STA-iface).
// No-op on non-5 GHz boards (classic ESP32 / S3): the CONFIG guards compile out.
static inline void cym_mgmt_tx_prepare_dualband(void)
{
#if CONFIG_BOARD_HAS_5GHZ
    esp_wifi_set_band_mode(WIFI_BAND_MODE_AUTO);
    vTaskDelay(pdMS_TO_TICKS(50));
#endif
#if CONFIG_SOC_WIFI_SUPPORT_5G
    wifi_country_t wc = { .schan = 1, .nchan = 13,
                          .policy = WIFI_COUNTRY_POLICY_MANUAL };
    wc.cc[0] = 'D'; wc.cc[1] = 'E'; wc.cc[2] = '\0';  // cosmetic under MANUAL
    wc.wifi_5g_channel_mask = 0x1FFFFFFEu;            // ch 36-177, no restriction
    esp_wifi_set_country(&wc);
#endif
}

// Set the radio channel and CONFIRM it landed there via an esp_wifi_get_channel()
// readback (retried once). Returns true only if the radio is actually on `ch`.
//
// Why a raw TX path must check this: on the ESP32-C5, esp_wifi_set_channel() for a
// DFS 5 GHz channel (52-144 — no CAC on C5, cannot be SoftAP/TX there) is REJECTED
// silently: no error, the radio simply stays on its previous (2.4 GHz) channel. A
// deauth/SAE frame sent afterwards then goes out on the WRONG band — sprayed onto
// whatever 2.4 GHz channel the radio was left on, never reaching the 5 GHz target.
// Callers must SKIP the transmit when this returns false. DFS stays fully available
// for passive RX (sniff/wardrive) — this only gates TX to channels the radio proved
// it is really on. Mirrors main.c:wifi_set_channel_verified (kept in sync).
static inline bool cym_set_channel_verified(uint8_t ch)
{
    esp_wifi_set_channel(ch, WIFI_SECOND_CHAN_NONE);
    uint8_t ac; wifi_second_chan_t sc;
    if (esp_wifi_get_channel(&ac, &sc) == ESP_OK && ac == ch) return true;
    vTaskDelay(pdMS_TO_TICKS(5));
    esp_wifi_set_channel(ch, WIFI_SECOND_CHAN_NONE);
    return (esp_wifi_get_channel(&ac, &sc) == ESP_OK && ac == ch);
}
