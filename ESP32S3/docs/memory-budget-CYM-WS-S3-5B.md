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
| Version | v3.0.32 |
| Build date | 2026-10-20 |
| .iram0.text | 129,883 B (126.8 KB) |
| .dram0.data | 33,741 B (33.0 KB) |
| .dram0.bss  (internal) | 71,248 B (69.6 KB) |
| .ext_ram.bss  (PSRAM) | 220,860 B (215.7 KB) |
| App binary size | 2,884,384 B (2816.8 KB) |
<!-- MEMORY_METRICS_END -->

## Internal BSS consumers
<!-- BSS_TABLE_START -->
| Library / object | Internal BSS |
|-----------------|-------------|
| `libmain.a` | 54,500 B (53.2 KB) |
| `libnet80211.a` | 7,832 B (7.6 KB) |
| `liblwip.a` | 4,147 B (4.0 KB) |
| `libmesh.a` | 3,939 B (3.8 KB) |
| `libespressif__mdns.a` | 3,583 B (3.5 KB) |
| `librf_hat.a` | 3,153 B (3.1 KB) |
| `libwifi_scanner.a` | 2,425 B (2.4 KB) |
| `libwifi_attacks.a` | 1,990 B (1.9 KB) |
| `libwpa_supplicant.a` | 1,931 B (1.9 KB) |
| `libpp.a` | 1,803 B (1.8 KB) |
| `liblvgl__lvgl.a` | 1,137 B (1.1 KB) |
| `libbtdm_app.a` | 793 B |
| `libfreertos.a` | 764 B |
| `libesp_libc.a` | 540 B |
| `libtfpsacrypto.a` | 472 B |
<!-- BSS_TABLE_END -->
