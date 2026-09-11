# CYM hosyond-s3-35 — Firmware Memory Budget

> Auto-updated by `ESP32S3/tools/update_memory_map.py` after every successful build.
> Commit this file together with the firmware binary so the numbers always match.

---

## 1. Current build metrics  *(auto-updated — do not edit by hand)*

<!-- MEMORY_METRICS_START -->
| Metric | Value |
|--------|-------|
| Version | v2.13.80 |
| Build date | 2026-09-11 |
| .iram0.text | 68,875 B (67.3 KB) |
| .dram0.data | 17,421 B (17.0 KB) |
| .dram0.bss  (internal) | 37,104 B (36.2 KB) |
| .ext_ram.bss  (PSRAM) | 0 B |
| App binary size | 586,800 B (573.0 KB) |
<!-- MEMORY_METRICS_END -->

### Top internal BSS consumers  *(auto-updated)*

<!-- BSS_TABLE_START -->
| Library / object | Internal BSS |
|-----------------|-------------|
| `liblvgl__lvgl.a` | 33,909 B (33.1 KB) |
| `libfreertos.a` | 764 B |
| `libesp_libc.a` | 540 B |
| `libtfpsacrypto.a` | 472 B |
| `libefuse.a` | 364 B |
| `libesp_system.a` | 333 B |
| `libesp_hw_support.a` | 322 B |
| `liblog.a` | 276 B |
| `libmain.a` | 164 B |
| `libesp_psram.a` | 62 B |
| `libfatfs.a` | 56 B |
| `libesp_driver_ledc.a` | 48 B |
| `libesp_mm.a` | 48 B |
| `libvfs.a` | 44 B |
| `libnvs_flash.a` | 40 B |
<!-- BSS_TABLE_END -->

---

## 2. Board notes

**Board:** Hosyond 3.5" ES3C35P — ESP32-S3R8, dual-core Xtensa LX7 240 MHz, 16 MB flash, 8 MB OPI PSRAM.

This is a **bring-up firmware** (v2.13.79 framework-test build). The binary is intentionally small —
it contains only the S3 display/touch/SD bring-up code, not the full CYM feature set.
As features are ported from the C5 tree (wardrive, BLE scanner, RF-HAT support, etc.), the binary
size will grow toward the C5/ESP32 range (~3 MB).

Key S3 characteristics vs NM-CYD-C5:
- **ST77922 QSPI** at 80 MHz (4-wire, no DC pin) vs ST7789 standard SPI
- **Dual-core** — jammer/RF tasks can be pinned to Core 1, eliminating single-core timing contention
- **8 MB OPI PSRAM** — larger buffers available; PSRAM BSS currently unused (will populate as features land)
- **No 802.15.4** — ESP32-S3 lacks the IEEE 802.15.4 radio; OT Air Survey and Zigbee Scout are not available on this target
