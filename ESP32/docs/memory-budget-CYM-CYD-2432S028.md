# CYM CYM-CYD-2432S028 — Firmware Memory Budget

> Auto-updated by `ESP32C5/tools/update_memory_map.py` after every successful build.
> Commit this file together with the firmware binary so the numbers always match.

---

## 1. Current build metrics  *(auto-updated — do not edit by hand)*

<!-- MEMORY_METRICS_START -->
| Metric | Value |
|--------|-------|
| Version | v2.13.77 |
| Build date | 2026-09-11 |
| .iram0.text | 105,203 B (102.7 KB) |
| .dram0.data | 26,371 B (25.8 KB) |
| .dram0.bss  (internal) | 96,152 B (93.9 KB) |
| .ext_ram.bss  (PSRAM) | 0 B |
| App binary size | 2,640,560 B (2578.7 KB) |
<!-- MEMORY_METRICS_END -->

### Top internal BSS consumers  *(auto-updated)*

<!-- BSS_TABLE_START -->
| Library / object | Internal BSS |
|-----------------|-------------|
| `libmain.a` | 62,947 B (61.5 KB) |
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
