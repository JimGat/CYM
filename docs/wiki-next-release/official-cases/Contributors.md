# Contributors & Credits

CYM wouldn't be where it is without the people below. They've tested under brutal field conditions, caught bugs before they reached users, submitted patches, and made the firmware faster and more stable for everyone.

---

## Co-Developer

### @birolt29
Co-developer of CYM, not just a contributor — @birolt29 has driven some of the largest architectural and feature work in the project's history, performing deep ESP32-C5 DMA and render pipeline analysis on real hardware and submitting multiple major patch sets, each serial-validated on device before submission.

**Contributions include:**
- **[Official CYM Cases](Official-Cases)** — four board-specific packages for NM-CYD-C5, Classic CYD / 2432S028R, WS-C5-28 and Hosyond ES3C35P 3.5-inch (Standard and Slim); EN/DE/TR manuals, STL/3MF models and original photos. Supplied manual credits remain @birolt29 / @alen29 under CC BY-NC-ND 4.0.
- **[Modern Menu](Modern-Menu) (v2.15.24+)** — selectable four-category Home (Attack, Detect & Defend, Recon & Scan, Tools & System), first-boot chooser, persistent Classic/Modern switching, category-aware Back/Home navigation, and the dual-layout navigation contract
- **Deauth Harvest + detector aging (v2.15.31+)** — passive deauth/disassociation and association-recon observations, multi-Pwnagotchi handling, adaptive dwell/RSSI follow behavior, and 60-second stale-entry aging
- **[Screen Orientation](Screen-Orientation) (v2.15.00)** — landscape/portrait/flipped rotation feature built from scratch over 75+ build/test cycles, with dozens of screens individually redesigned for landscape (Universal Remote, LED Remote, Bluetooth Lookout, Evil Portal, Timing Settings, Chameleon Ultra, GPS Info, Main Menu, and more)
- **WiFi Scan & Attack list redesign (v2.15.00)** — wardrive-style rows, band badge, deauth-feasibility color coding, multi-select
- **Dual-band Handshaker + Deauth Monitor (v2.15.00)** — 2.4 + 5 GHz coverage with GPS-free regulatory domain detection, plus a PMKID (hashcat 22000) capture path
- **Crash fixes (v2.15.00)** — MITM active-capture use-after-free, PN532 Clone/Write/Emulate stack exhaustion, two Chameleon Ultra BLE reconnect bugs
- **v2.10.15 hardware optimization patch** — upload stability, mbedTLS PSRAM routing, BLE Spam memory hardening
- **v2.11.x render performance series** — LCD SPI 40→80 MHz, internal DMA draw buffers, -O2 build optimization, LVGL libc memcpy, 15 ms refresh period, PSRAM 80 MHz. Full-frame LVGL render: **148 ms → ~77 ms (-48%)**
- **SD remount mutex fix** — eliminated a hard reset race between the SD remount task and in-flight LCD DMA transfers
- **PSRAM BSS migration** — moved 17.4 KB of IR/RF433 name tables from internal DRAM to PSRAM, raising the DMA-free heap floor
- **GATT Walker double-init reset fix** — serial-confirmed root cause analysis and fix for the reproducible esp_restart() on 2nd GATT Walker Back cycle
- **TPMS Monitor stop hook** — identified and fixed missing screen teardown causing crash on Back/Home navigation
- Serial-validated testing of every patch on real hardware before submission

---

## Community Contributors

| Person | Contribution |
|--------|-------------|
| **Anubis** | First community video showcase of CYM — [watch here](https://youtu.be/IDm4uz38IDE) 🎬 |
| **ᛕ ᛊ ߇ ᛙ ᚢ (Kevin)** | Deep technical testing and diagnosing the toughest issues |
| **sithwrld999** | Thorough testing and edge case discovery |
| **bkbroiler** | Hands-on testing and constructive feedback |
| **HeavyButter** | Testing and being Paranoid Butter |
| **eCowboy** | Hardware testing and design suggestions |
| **OrdoOuroborus** | Testing, review, and feature ideas |
| **@Zjakkemakke** | Testing and feedback |
| **@PKT-GHOST** | Testing and feedback |
| **el_kaweh (AWOK)** | Reported the NM-CYD-C5 stationary-wardrive SD write stall at 100 networks |
| **Janek (LAB5)** | Correctly diagnosed that report as a fixed-size structure, pointing straight at the fix; co-dedicatee of the CYM Pancake-C5 development-channel build |
| **D3h420** | Friend and remote Pancake-C5 hardware tester; the CYM beta build is dedicated in part to him |

---

## Ecosystem Credits

| Person / Project | Connection |
|-----------------|------------|
| **OyczE** | Designer of the MonsterC5; approved the "Cheap Yellow Monster" name; co-dedicatee of the CYM Pancake-C5 development-channel build |
| **Janek / JanOS** | CYM was originally branched from JanOS — the foundation it grew from |
| **LAB5 Team** | The broader MonsterC5 / LAB5 ecosystem CYM contributes back to |
| **[C5Lab Pancake](https://github.com/C5Lab/pancake)** | Original inspiration for the NM-CYD-C5 CYM concept and source hardware contract for the Pancake-C5 development-channel port. The CYM build is dedicated to D3h420, Janek, and OyczE. |

---

*Want to contribute? See the [Support & Community](Support-and-Community) page.*
