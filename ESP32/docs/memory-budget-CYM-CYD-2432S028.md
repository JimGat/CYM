# CYM CYM-CYD-2432S028 — Firmware Memory Budget

> Auto-updated by `ESP32C5/tools/update_memory_map.py` after every successful build.
> Commit this file together with the firmware binary so the numbers always match.

---

## 1. Current build metrics  *(auto-updated — do not edit by hand)*

<!-- MEMORY_METRICS_START -->
| Metric | Value |
|--------|-------|
| Version | v2.15.11 |
| Build date | 2026-09-22 |
| .iram0.text | 105,203 B (102.7 KB) |
| .dram0.data | 26,387 B (25.8 KB) |
| .dram0.bss  (internal) | 96,696 B (94.4 KB) |
| .ext_ram.bss  (PSRAM) | 0 B |
| App binary size | 2,682,464 B (2619.6 KB) |
<!-- MEMORY_METRICS_END -->

### Top internal BSS consumers  *(auto-updated)*

<!-- BSS_TABLE_START -->
| Library / object | Internal BSS |
|-----------------|-------------|
| `libmain.a` | 63,460 B (62.0 KB) |
| `libnet80211.a` | 9,857 B (9.6 KB) |
| `liblwip.a` | 4,094 B (4.0 KB) |
| `libwifi_scanner.a` | 3,949 B (3.9 KB) |
| `libmesh.a` | 3,939 B (3.8 KB) |
| `libbtdm_app.a` | 2,924 B (2.9 KB) |
| `librf_hat.a` | 2,473 B (2.4 KB) |
| `libpp.a` | 2,123 B (2.1 KB) |
| `libwifi_attacks.a` | 1,990 B (1.9 KB) |
| `libwpa_supplicant.a` | 1,931 B (1.9 KB) |
| `liblvgl__lvgl.a` | 1,137 B (1.1 KB) |
| `libfreertos.a` | 748 B |
| `libbt.a` | 607 B |
| `libesp_libc.a` | 540 B |
| `libtfpsacrypto.a` | 381 B |
<!-- BSS_TABLE_END -->
