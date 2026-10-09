# CYM CYM-WS-C5-35 — Firmware Memory Budget

> Auto-updated by `ESP32C5/tools/update_memory_map.py` after every successful build.
> Commit this file together with the firmware binary so the numbers always match.

---

## 1. Current build metrics  *(auto-updated — do not edit by hand)*

<!-- MEMORY_METRICS_START -->
| Metric | Value |
|--------|-------|
| Version | v2.15.71 |
| Build date | 2026-10-09 |
| .iram0.text | 135,130 B (132.0 KB) |
| .dram0.data | 44,245 B (43.2 KB) |
| .dram0.bss  (internal) | 100,888 B (98.5 KB) |
| .ext_ram.bss  (PSRAM) | 312,104 B (304.8 KB) |
| App binary size | 3,605,408 B (3520.9 KB) |
<!-- MEMORY_METRICS_END -->

### Top internal BSS consumers  *(auto-updated)*

<!-- BSS_TABLE_START -->
| Library / object | Internal BSS |
|-----------------|-------------|
| `libcym_doom_engine.a` | 97,794 B (95.5 KB) |
| `libmain.a` | 63,329 B (61.8 KB) |
| `libnet80211.a` | 13,559 B (13.2 KB) |
| `librf_hat.a` | 11,352 B (11.1 KB) |
| `libmesh.a` | 3,955 B (3.9 KB) |
| `liblwip.a` | 3,940 B (3.8 KB) |
| `libieee802154.a` | 3,590 B (3.5 KB) |
| `libespressif__mdns.a` | 3,529 B (3.4 KB) |
| `libpp.a` | 3,467 B (3.4 KB) |
| `libwifi_scanner.a` | 2,400 B (2.3 KB) |
| `libcym_doom.a` | 2,396 B (2.3 KB) |
| `libfreertos.a` | 2,148 B (2.1 KB) |
| `libwifi_attacks.a` | 1,935 B (1.9 KB) |
| `libwpa_supplicant.a` | 1,722 B (1.7 KB) |
| `liblvgl__lvgl.a` | 840 B |
<!-- BSS_TABLE_END -->


Native-engine placement correction: the generated top-consumer summary groups input `.bss` by archive and may count external engine input sections as internal. The actual ELF output section and native linker reset-range gate is authoritative. Engine zero state is 93,936 bytes of PSRAM BSS, not internal SRAM; initialized engine state is 19,892 bytes of loaded internal data. See `docs/ws-c5-game-beta.md` for static headroom and pending physical runtime evidence.
