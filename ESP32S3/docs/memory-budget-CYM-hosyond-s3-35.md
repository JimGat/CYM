# CYM hosyond-s3-35 — Firmware Memory Budget

> Auto-updated by `ESP32S3/tools/update_memory_map.py` after every successful build.
> Commit this file together with the firmware binary so the numbers always match.

---

## 1. Current build metrics  *(auto-updated — do not edit by hand)*

<!-- MEMORY_METRICS_START -->
| Metric | Value |
|--------|-------|
| Version | v2.15.30 |
| Build date | 2026-09-26 |
| .iram0.text | 128,587 B (125.6 KB) |
| .dram0.data | 28,477 B (27.8 KB) |
| .dram0.bss  (internal) | 77,632 B (75.8 KB) |
| .ext_ram.bss  (PSRAM) | 207,396 B (202.5 KB) |
| App binary size | 2,702,416 B (2639.1 KB) |
<!-- MEMORY_METRICS_END -->

### Top internal BSS consumers  *(auto-updated)*

<!-- BSS_TABLE_START -->
| Library / object | Internal BSS |
|-----------------|-------------|
| `libmain.a` | 55,059 B (53.8 KB) |
| `librf_hat.a` | 11,433 B (11.2 KB) |
| `libnet80211.a` | 7,832 B (7.6 KB) |
| `liblwip.a` | 4,094 B (4.0 KB) |
| `libmesh.a` | 3,939 B (3.8 KB) |
| `libwifi_scanner.a` | 2,413 B (2.4 KB) |
| `libwifi_attacks.a` | 1,990 B (1.9 KB) |
| `libwpa_supplicant.a` | 1,931 B (1.9 KB) |
| `libpp.a` | 1,803 B (1.8 KB) |
| `liblvgl__lvgl.a` | 1,137 B (1.1 KB) |
| `libbtdm_app.a` | 793 B |
| `libfreertos.a` | 764 B |
| `libesp_libc.a` | 540 B |
| `libtfpsacrypto.a` | 472 B |
| `libefuse.a` | 364 B |
<!-- BSS_TABLE_END -->

---

## 2. Board notes

**Board:** Hosyond 3.5" ES3C35P — ESP32-S3R8, dual-core Xtensa LX7 240 MHz, 16 MB flash, 8 MB OPI PSRAM.

This is a **bring-up firmware** (not the shared CYM application). The binary is intentionally small —
it contains only the S3 display/touch/SD bring-up code, not the full CYM feature set.
As features are ported from the C5 tree (wardrive, BLE scanner, RF-HAT support, etc.), the binary
size will grow toward the C5/ESP32 range (~3 MB).

Key S3 characteristics vs NM-CYD-C5:
- **ST77922 QSPI** at 40 MHz (4 data lines, no DC pin); factory 320×480 init table, RGB565/INVON, no mirror
- **Dual-core** — jammer/RF tasks can be pinned to Core 1, eliminating single-core timing contention
- **8 MB OPI PSRAM** — larger buffers available; PSRAM BSS currently unused (will populate as features land)
- **No 802.15.4** — ESP32-S3 lacks the IEEE 802.15.4 radio; OT Air Survey and Zigbee Scout are not available on this target
