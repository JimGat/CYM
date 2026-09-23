# CYM CYM-WS-C5-28 — Firmware Memory Budget

> Auto-updated by `ESP32C5/tools/update_memory_map.py` after every successful build.
> Commit this file together with the firmware binary so the numbers always match.

---

## 1. Current build metrics  *(auto-updated — do not edit by hand)*

<!-- MEMORY_METRICS_START -->
| Metric | Value |
|--------|-------|
| Version | v2.15.18 |
| Build date | 2026-09-23 |
| .iram0.text | 138,486 B (135.2 KB) |
| .dram0.data | 23,913 B (23.4 KB) |
| .dram0.bss  (internal) | 91,920 B (89.8 KB) |
| .ext_ram.bss  (PSRAM) | 218,136 B (213.0 KB) |
| App binary size | 3,140,256 B (3066.7 KB) |
<!-- MEMORY_METRICS_END -->

### Top internal BSS consumers  *(auto-updated)*

<!-- BSS_TABLE_START -->
| Library / object | Internal BSS |
|-----------------|-------------|
| `libmain.a` | 60,044 B (58.6 KB) |
| `libnet80211.a` | 13,559 B (13.2 KB) |
| `librf_hat.a` | 11,352 B (11.1 KB) |
| `libmesh.a` | 3,955 B (3.9 KB) |
| `liblwip.a` | 3,908 B (3.8 KB) |
| `libieee802154.a` | 3,590 B (3.5 KB) |
| `libpp.a` | 3,467 B (3.4 KB) |
| `libwifi_scanner.a` | 2,400 B (2.3 KB) |
| `libfreertos.a` | 2,148 B (2.1 KB) |
| `libwifi_attacks.a` | 1,935 B (1.9 KB) |
| `libwpa_supplicant.a` | 1,722 B (1.7 KB) |
| `liblvgl__lvgl.a` | 840 B |
| `libesp_libc.a` | 508 B |
| `libtfpsacrypto.a` | 428 B |
| `libble_app.a` | 371 B |
<!-- BSS_TABLE_END -->
