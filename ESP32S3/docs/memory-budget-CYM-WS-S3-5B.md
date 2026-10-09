# WS-S3-5B memory budget

Beta v2.15.63, ESP-IDF 6.0. Generated from the actual S3 linker map and `idf.py size`; runtime heap is NOT hardware-qualified.

```text
Memory Type Usage Summary
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Memory Type/Section ┃ Used [bytes] ┃ Used [%] ┃ Remain [bytes] ┃ Total [bytes] ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Flash Code          │      1879772 │          │                │               │
│    .text            │      1879772 │          │                │               │
│ Flash Data          │       961432 │          │                │               │
│    .rodata          │       753668 │          │                │               │
│    .bss             │       207452 │          │                │               │
│    .appdesc         │          256 │          │                │               │
│    .tdata           │           56 │          │                │               │
│ DIRAM               │       223628 │    65.43 │         118132 │        341760 │
│    .text            │       111779 │    32.71 │                │               │
│    .bss             │        83328 │    24.38 │                │               │
│    .data            │        28521 │     8.35 │                │               │
│ IRAM                │        16384 │    100.0 │              0 │         16384 │
│    .text            │        15356 │    93.73 │                │               │
│    .vectors         │         1028 │     6.27 │                │               │
│ RTC SLOW            │           36 │     0.44 │           8156 │          8192 │
│    .force_slow      │           36 │     0.44 │                │               │
│ RTC FAST            │           24 │     0.29 │           8168 │          8192 │
│    .rtc_reserved    │           24 │     0.29 │                │               │
└─────────────────────┴──────────────┴──────────┴────────────────┴───────────────┘
```

Application image: 2790592 bytes; app partition 0x700000.

Runtime display allocations (not all represented in linker BSS): two physical 1024x600 RGB565 PSRAM frames = 2457600 bytes; two logical 512x300 RGB565 PSRAM draw frames = 614400 bytes; two 10-line RGB bounce buffers = 40960 internal bytes, plus driver/task/network allocations. Verify internal heap minimum and RGB stability under Wi-Fi, BLE and SD load on real hardware.

## Automatic linker metrics
<!-- MEMORY_METRICS_START -->
| Metric | Value |
|--------|-------|
| Version | v2.15.71 |
| Build date | 2026-10-09 |
| .iram0.text | 127,279 B (124.3 KB) |
| .dram0.data | 28,521 B (27.9 KB) |
| .dram0.bss  (internal) | 83,536 B (81.6 KB) |
| .ext_ram.bss  (PSRAM) | 207,452 B (202.6 KB) |
| App binary size | 2,809,680 B (2743.8 KB) |
<!-- MEMORY_METRICS_END -->

## Internal BSS consumers
<!-- BSS_TABLE_START -->
| Library / object | Internal BSS |
|-----------------|-------------|
| `libmain.a` | 58,630 B (57.3 KB) |
| `librf_hat.a` | 11,433 B (11.2 KB) |
| `libnet80211.a` | 7,832 B (7.6 KB) |
| `liblwip.a` | 4,147 B (4.0 KB) |
| `libmesh.a` | 3,939 B (3.8 KB) |
| `libespressif__mdns.a` | 3,578 B (3.5 KB) |
| `libwifi_scanner.a` | 2,413 B (2.4 KB) |
| `libwifi_attacks.a` | 1,990 B (1.9 KB) |
| `libwpa_supplicant.a` | 1,931 B (1.9 KB) |
| `libpp.a` | 1,803 B (1.8 KB) |
| `liblvgl__lvgl.a` | 1,137 B (1.1 KB) |
| `libbtdm_app.a` | 793 B |
| `libfreertos.a` | 764 B |
| `libesp_libc.a` | 540 B |
| `libtfpsacrypto.a` | 472 B |
<!-- BSS_TABLE_END -->
