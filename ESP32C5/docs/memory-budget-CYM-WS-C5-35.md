# CYM CYM-WS-C5-35 — Firmware Memory Budget

> Auto-updated by `ESP32C5/tools/update_memory_map.py` after every successful build.
> Commit this file together with the firmware binary so the numbers always match.

---

## 1. Current build metrics  *(auto-updated — do not edit by hand)*

<!-- MEMORY_METRICS_START -->
| Metric | Value |
|--------|-------|
| Version | v3.0.23 |
| Build date | 2026-10-18 |
| .iram0.text | 142,768 B (139.4 KB) |
| .dram0.data | 50,465 B (49.3 KB) |
| .dram0.bss  (internal) | 96,096 B (93.8 KB) |
| .ext_ram.bss  (PSRAM) | 339,880 B (331.9 KB) |
| App binary size | 4,193,424 B (4095.1 KB) |
<!-- MEMORY_METRICS_END -->

### Top internal BSS consumers  *(auto-updated)*

<!-- BSS_TABLE_START -->
| Library / object | Internal BSS |
|-----------------|-------------|
| `libcym_doom_engine.a` | 98,086 B (95.8 KB) |
| `libmain.a` | 51,801 B (50.6 KB) |
| `libnet80211.a` | 13,559 B (13.2 KB) |
| `librf_hat.a` | 11,352 B (11.1 KB) |
| `libZXing_bound.a` | 10,112 B (9.9 KB) |
| `libcym_doom.a` | 7,376 B (7.2 KB) |
| `libstdc++.a` | 4,256 B (4.2 KB) |
| `libmesh.a` | 3,955 B (3.9 KB) |
| `liblwip.a` | 3,940 B (3.8 KB) |
| `libieee802154.a` | 3,590 B (3.5 KB) |
| `libespressif__mdns.a` | 3,529 B (3.4 KB) |
| `libpp.a` | 3,467 B (3.4 KB) |
| `libwifi_scanner.a` | 2,400 B (2.3 KB) |
| `libfreertos.a` | 2,148 B (2.1 KB) |
| `libwifi_attacks.a` | 1,935 B (1.9 KB) |
<!-- BSS_TABLE_END -->


Native-engine placement correction: the generated top-consumer summary groups input `.bss` by archive and may count external engine input sections as internal. The actual ELF output section and native linker reset-range gate is authoritative. Engine zero state is 93,936 bytes of PSRAM BSS, not internal SRAM; initialized engine state is 19,892 bytes of loaded internal data. See `docs/ws-c5-game-beta.md` for static headroom and pending physical runtime evidence.
