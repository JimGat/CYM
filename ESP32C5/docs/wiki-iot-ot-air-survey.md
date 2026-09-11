# IOT/OT Air Survey — Wiki

> **Version:** v2.13.77 | **Branch:** Jimgat_Dev | **Scope:** All three boards (NM-CYD-C5, WS-C5-28, CYD-2432S028)

## Overview

The IOT/OT Air Survey is a **passive-only** multi-radio observation system that catalogues
OT (operational technology) and IoT devices within radio range. It never transmits probes,
deauthentication frames, spoofed advertisements, or any other disruptive traffic.

The survey produces structured observation records (`obs_record_t`) that capture device
identity, protocol classification, RF metrics, and GPS position. Records are persisted to
SD card in JSONL format with optional per-session 802.15.4 PCAPNG capture.

---

## Navigation: IOT/OT Menu

The home screen "IOT/OT" tile opens an umbrella submenu:

```
Home Screen
└── IOT/OT tile
    ├── Zigbee Scout  [ESP32-C5 only — CONFIG_IEEE802154_ENABLED]
    └── OT Air Survey [all boards]
```

**Tile routing** is handled by `show_iot_ot_menu_screen()`. The Zigbee Scout sub-tile is
compiled only when `CONFIG_IEEE802154_ENABLED` is set (ESP32-C5 boards). The CYD-2432S028
(ESP32) shows the IOT/OT tile and can run OT Air Survey via WiFi, BLE, and ESP-NOW, but
does not show the Zigbee Scout sub-tile.

---

## What the Survey Collects

Every device or network node seen during a survey is captured as an `obs_record_t`
(128 bytes, schema v2). The record carries:

### Base fields (88 bytes)

| Field | Type | Description |
|-------|------|-------------|
| `mac[6]` | uint8_t[6] | Primary MAC / EUI-64 low 6 bytes |
| `peer_mac[6]` | uint8_t[6] | Peer MAC for ESP-NOW frames |
| `obs_type` | uint8_t | Protocol class (see table below) |
| `src_radio` | uint8_t | Capture radio (WiFi / BLE / 802.15.4 / ESP-NOW) |
| `phy` | uint8_t | PHY: 11b/g/n/ac/ax, BLE 1M/2M/Coded, 802.15.4 O-QPSK |
| `channel` | uint8_t | RF channel at time of capture |
| `rssi_cur` | int8_t | RSSI at most recent sighting (dBm) |
| `rssi_peak` | int8_t | Peak RSSI across all sightings (dBm) |
| `auth_mode` | uint8_t | WiFi authentication mode (AP only) |
| `flags` | uint16_t | GPS validity, PMF inferred, random address, etc. |
| `hit_count` | uint16_t | Number of times this record has been updated |
| `obs_count` | uint16_t | Reserved (obs_store level) |
| `label[32]` | char | SSID, BLE name, or allowlist-overridden user label |
| `latitude` | double | GPS latitude (0.0 if no valid fix) |
| `longitude` | double | GPS longitude |
| `altitude_m` | float | GPS altitude (metres) |
| `accuracy_m` | float | GPS horizontal accuracy (metres) |
| `first_seen_s` | uint32_t | Boot-relative timestamp of first sighting |
| `last_seen_s` | uint32_t | Boot-relative timestamp of most recent sighting |
| `evidence[]` | uint8_t[4] | Up to 4 `obs_ev_t` evidence tags |

### Extension union (40 bytes, `ext`)

For 802.15.4 frames the `ext.ieee154` field is populated:

| Field | Description |
|-------|-------------|
| `pan_id` | PAN identifier |
| `src_addr_short` | 16-bit short address (0 if unused) |
| `dst_addr_short` | 16-bit destination short address |
| `src_addr_ext` | 64-bit EUI extended source address |
| `dst_addr_ext` | 64-bit EUI extended destination address |
| `frame_type` | Beacon / Data / Ack / Cmd / Multipurpose |
| `frame_version` | 802.15.4 frame version (0=2003, 1=2006, 2=2015) |
| `security_level` | 0–7 (0 = no security) |
| `lqi` | Link Quality Indicator 0–255 |
| `wh_confidence` | WirelessHART heuristic confidence 0–100 |
| `proto_class` | Zigbee / Thread / WirelessHART / ISA100 / Generic |

### Observation types (`obs_type_t`)

| Value | Name | Populated by |
|-------|------|--------------|
| 0 | WIFI_AP | WiFi scan (AP beacons/probe responses) |
| 1 | WIFI_CLIENT | WiFi promiscuous (client stations) |
| 2 | BLE_ADV | BLE legacy advertising (1M PHY) |
| 3 | BLE_EXT | BLE 5.0 extended advertising |
| 4 | IEEE802154 | Generic 802.15.4 frame, stack unknown |
| 5 | WIRELESSHART | WirelessHART classified (confidence ≥ 40) |
| 6 | THREAD_MATTER | Thread / Matter stack detected |
| 7 | ZIGBEE | Zigbee PRO stack profile detected |
| 8 | ESPNOW_OT | ESP-NOW frame (src+dst MACs, RSSI, channel) |
| 9 | DRONE_ID | OpenDroneID / Remote ID |

### Per-session counters (v2.13.77+)

`ot_survey_session_t` now carries:
- `obs_count` — total observations recorded
- `obs_by_type[10]` — per-type breakdown (indexed by `obs_type_t`)
- `flush_head` — append-mode cursor: next index to write on flush

---

## Radio Profiles

Eight profiles control time-slice allocation across available radios. Profiles that
include 802.15.4 are silently downgraded to WiFi+BLE on non-capable boards.

| # | Name | WiFi | BLE | 802.15.4 | Notes |
|---|------|------|-----|----------|-------|
| 0 | Balanced | 40% | 40% | 20% | Default — best general coverage |
| 1 | WiFi Heavy | 70% | 20% | 10% | Dense AP environments |
| 2 | BLE Heavy | 20% | 70% | 10% | Asset tracking, BLE mesh |
| 3 | 802.15.4 Heavy | 20% | 10% | 70% | C5 only — dense OT sensor environments |
| 4 | ESP-NOW Focus | 50% | 30% | 20% | ESP32 mesh / ESP-NOW gateway discovery |
| 5 | Drone Watch | 35% | 50% | 15% | OpenDroneID detection emphasis |
| 6 | WirelessHART | 10% | 10% | 80% | C5 only — IEC 62591 industrial environments |
| 7 | Thread/Matter | 15% | 15% | 70% | C5 only — home automation / smart building |

Profile is selected on the OT Air Survey config screen and passed to
`ot_radio_scheduler_start()` which arms the radio time-slicer.

---

## Storage Layout

Each survey session creates a directory under `/sdcard/lab/otsurvey/<uuid>/`:

```
/sdcard/lab/otsurvey/
├── allowlist.json               # optional — user-defined device labels
└── <32-char-uuid>/
    ├── metadata.json            # session config, start/stop times, obs_count
    ├── obs.jsonl                # JSONL — one obs_record per line (append-mode)
    └── ieee802154.pcapng        # raw 802.15.4 frames (ESP32-C5 only)
```

### metadata.json

Written at survey start and updated at stop:

```json
{
  "uuid": "3c8f...",
  "profile": "Balanced",
  "site": "Building A / Floor 2",
  "start_time_s": 1234567890,
  "stop_time_s": 1234568490,
  "obs_count": 127,
  "state": "stopped"
}
```

### obs.jsonl

JSONL (newline-delimited JSON). Each line is one serialised `obs_record_t`. Flushed
incrementally via `ot_survey_flush()` — as of v2.13.77, flush uses **append mode** so
each call only writes new records (those after `flush_head`), avoiding full-file rewrites.

Example lines:
```jsonl
{"type":"WIFI_AP","mac":"3c:dc:75:9d:5c:60","ssid":"LabNet5","rssi":-62,"ch":6,"auth":"WPA3","lat":37.3861,"lon":-122.0839}
{"type":"BLE_ADV","mac":"aa:bb:cc:dd:ee:ff","name":"Temp-Sensor-01","rssi":-75,"phy":"1M"}
{"type":"ESPNOW_OT","mac":"24:6f:28:ab:cd:ef","peer":"ff:ff:ff:ff:ff:ff","rssi":-58,"ch":1}
{"type":"WIRELESSHART","mac":"00:1b:1e:02:03:04","pan":0x1a2b,"wh_conf":82,"ch":15}
```

### ieee802154.pcapng (ESP32-C5 only)

Raw 802.15.4 MAC frames in PCAPNG format. Link type: `DLT_IEEE802_15_4_NOFCS` (230).
FCS is stripped by the ESP32-C5 radio driver; RSSI/LQI are embedded in the PCAPNG
enhanced packet block custom options. Open in Wireshark for frame-level analysis.

---

## Device Allowlist

Drop a file at `/sdcard/lab/otsurvey/allowlist.json` (one JSON object per line) to
assign known labels to specific MACs:

```json
{"mac":"24:6f:28:ab:cd:ef","label":"Pump-PLC-01"}
{"mac":"00:1b:1e:02:03:04","label":"WH-Gateway-West"}
{"mac":"aa:bb:cc:00:11:22","label":"BLE-Beacon-Lobby"}
```

- Loaded when survey starts (reads at most 64 entries)
- Overwrites auto-detected label (SSID, BLE name) for matching MACs
- Stored in heap (PSRAM on C5, default heap on ESP32) — freed when survey stops
- MAC matching is exact (6 bytes, no OUI wildcards)
- Format: `{"mac":"HH:HH:HH:HH:HH:HH","label":"..."}` — lowercase or uppercase hex accepted

---

## WirelessHART Detection

The WirelessHART heuristic (`wh_detect_update` / `wh_detect_score`) runs on every
802.15.4 frame and scores each PAN 0–100 for WirelessHART likelihood:

| Confidence | Classification |
|------------|----------------|
| 0–39 | Generic 802.15.4 (obs_type = IEEE802154) |
| 40–69 | Possible WirelessHART |
| 70–89 | Probable WirelessHART |
| 90–100 | Confirmed WirelessHART (obs_type = WIRELESSHART) |

Scoring factors: security_en bit, TDMA-style channel hopping (same PAN observed on 2+
channels), network layer indicators in the frame control field.

---

## Gaps / Roadmap

| Feature | Status | Notes |
|---------|--------|-------|
| Append-mode JSONL flush | Done (v2.13.77) | Per-session flush_head cursor |
| Per-type counters | Done (v2.13.77) | obs_by_type[10] in session + UI breakdown |
| Device allowlist | Done (v2.13.77) | /sdcard/lab/otsurvey/allowlist.json |
| SD mutex in s_ots_start_cb | Pending | ot_survey_start() does direct SD I/O without mutex |
| SIEM export | Deferred | Will be a separate headless-device project |
| WirelessHART channel-hop logging | Pending | Channel-hop events not yet stored as evidence tags |
| GPS waypoint marking | Pending | Survey path not yet recorded as GPX/track |
| Pause / Resume UI | Pending | API exists (ot_survey_pause/resume), no UI yet |
| Thread stack detection | Partial | proto_class=THREAD set on TLV match; no full decode |
| ISA100.11a detection | Partial | proto_class=ISA100; heuristic only |

---

## Passive-Only Guarantee

The OT Air Survey **never transmits**. The passive-only constraint is enforced at multiple
levels:

1. `ot_survey_start()` → `g_ot_survey_active = true` → all attack entry points check this
   flag and refuse to start while a survey is active.
2. `ot_radio_scheduler_start()` → sets `g_ot_survey_active` before arming any radio.
3. All obs creation paths (`obs_store_add`) are called from the main loop, never from
   transmit paths.
4. The PCAPNG writer (`pcapng_write_frame`) only stores frames already received; it has
   no transmit interface.

Do not add any transmit capability to any code path guarded by or called from an active
survey session.

---

*Generated by Claude Code — Jimgat_Dev — v2.13.77*
