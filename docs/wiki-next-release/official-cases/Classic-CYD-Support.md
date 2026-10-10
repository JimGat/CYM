# Classic CYD (ESP32-2432S028R) Support

## Official case and assembly manuals

Start with the **[Official CYM Cases](Official-Cases)** supplied by co-developer **@birolt29** for Classic CYD / 2432S028R. The collection provides original EN/DE/TR manuals, print models and photos, preserving @birolt29 / @alen29 credits and CC BY-NC-ND 4.0 licensing. Check its wiring/charging and fit caveats before assembly; case designation is not peripheral qualification. Older RF-HAT/community enclosures remain alternatives on [Where To Get It](Where-To-Get-It#3d-printed-cases). **Classic GPS caution:** the case manual’s CN1 IO22/IO27 route is not the known-good CYM receive-only GPIO1/P3 harness. Do not repin working hardware to match it without board/firmware-specific verification. The older GPS-unavailable statements elsewhere on this stable page are not a verdict on the newer development-profile harness.

CYM firmware runs on the **ESP32-2432S028R** — commonly called the "Classic CYD" or "Cheap Yellow Display (2USB variant)". This is the original dual-USB ESP32 board that started the CYD ecosystem. CYM ships a board-specific build for it (`CYM-CYD2USB`).

The Classic CYD supports the full **NM-RF-HAT** expansion board via an **SD Card Shim** that routes the HSPI SPI bus through the SD card slot connector and relocates the SD card to the NM-RF-HAT's onboard SD socket. All five RF modules (CC1101, nRF24, PN532, IR, RF433) are available with the shim installed.

Without the shim, the RF-HAT features are unavailable. The standard `CYM-CYD2USB` build targets the base board (no RF-HAT). A separate `CYM-CYD2USB-RFHAT` build variant is available for Halehound and similar configurations that include the shim + RF-HAT.

> **Boot indicator:** When CYM boots on a Classic CYD, the splash screen shows `Classic CYD - reduced functionality` in amber below the version number. This refers to the hardware differences listed below (no 5 GHz, no vibrator, smaller buffers due to no PSRAM) and does not reflect RF-HAT availability when the shim is installed.

---

## Hardware Overview

| Spec | NM-CYD-C5 (primary) | Classic CYD / CYD2USB |
|------|---------------------|-----------------------|
| SoC | ESP32-C5 (RISC-V, single-core, 240 MHz) | ESP32-WROOM-32 (Xtensa LX6, **dual-core**, 240 MHz) |
| WiFi | WiFi 6 — **2.4 + 5 GHz dual-band** | WiFi 4 — **2.4 GHz only** |
| BLE | Bluetooth 5 | Bluetooth 4.2 |
| Flash | 16 MB | **4 MB** |
| PSRAM | 8 MB | **none** |
| 802.15.4 | Yes (Zigbee / Thread scanner) | **No** |
| Display | 2.8" ST7789 240x320 | 2.8" ILI9341 240x320 |
| Touch | XPT2046 resistive | XPT2046 resistive |
| LED | WS2812 NeoPixel (GPIO 27) | Common-anode RGB (GPIO 4/16/17) |
| RF expansion | NM-RF-HAT via FPC2 connector | NM-RF-HAT via **SD Card Shim** |
| Vibrator | Yes (SC8002B amp + ERM motor) | **No** |
| GPS | LP-UART (GPIO 4/5) | **Pin conflict — not usable** |
| SD card | Shared SPI bus (with display + touch) | HSPI bus (repurposed via shim for RF-HAT) |

---

## SD Card Shim — RF-HAT on Classic CYD

The **SD Card Shim** is an adapter that plugs into the Classic CYD's microSD card slot and routes the onboard HSPI SPI bus (GPIO 18/23/19/5) to the NM-RF-HAT. The RF-HAT's onboard microSD socket takes over SD card duties — it is accessible regardless of which DIP switch is active, exactly as on NM-CYD-C5.

With the shim installed:
- All five NM-RF-HAT modules are available: CC1101 (Sub-GHz), nRF24L01+ (2.4 GHz ISM), PN532 (NFC/RFID), IR, and RF433 OOK
- The SD card is in the RF-HAT's socket, not the Classic CYD's slot
- The HSPI bus (formerly SD) is now the RF-HAT SPI bus
- Use the `CYM-CYD2USB-RFHAT` firmware build

The Halehound device is the reference implementation of Classic CYD + SD Card Shim + NM-RF-HAT.

---

## What Is Not Available on Classic CYD (any build)

These features are absent due to missing hardware — no firmware workaround exists.

| Feature | Reason |
|---------|--------|
| **5 GHz WiFi scanning / wardriving** | ESP32-WROOM-32 is 2.4 GHz only |
| **Zigbee / Thread scout** | No 802.15.4 radio on ESP32 |
| **Haptic feedback** | No vibrator motor or amp |
| **GPS** | GPIO conflict with SPI bus pins on Classic CYD |
| **Screen Orientation (landscape mode)** | Not supported on Classic CYD, by design — see note below |

### Note: Screen Orientation is not supported on Classic CYD

[Screen Orientation](Screen-Orientation) (landscape/portrait/flipped, Settings → Screen → Orientation) is available on **NM-CYD-C5** and **WS-C5-28** only — the Classic CYD does not have this feature and there is no plan to add it in the near term. This isn't a missing-hardware limitation the way 5 GHz or GPS are: it's that Classic CYD's ILI9341 panel already needs a board-specific `swap_xy` + mirror MADCTL transform just to display correctly in native portrait (see the Hardware Overview table above — different panel driver than NM-CYD-C5/WS-C5-28's ST7789), and its XPT2046 touch runs over software-bit-banged SPI on its own dedicated bus rather than the shared hardware-SPI setup the other two boards use. Layering LVGL's software rotation on top of that would need its own verification pass, which hasn't been done. If you want landscape mode on Classic CYD, open an issue — it's not ruled out, just not implemented.

---

## What Is Available (Full Feature, any build)

These features work the same as on NM-CYD-C5:

- WiFi attacks — Deauth, Evil Twin, KARMA, SAE Overflow, BlackOut
- Handshake capture (HCCAPX) and PCAP frame capture
- Wardriving (2.4 GHz WiFi + BLE — no 5 GHz)
- BLE scanning, GATT Walker, BT Lookout (Dee Dee Detector)
- Drone Detector (passive Remote ID scanner) and Drone Spoof
- Tracker Scanner (AirTag / SmartTag / Tile passive detection)
- Passive Observation System (OBS) classifiers
- ESP-NOW listener / debugger
- BLE Blaster, BLE Spoof, BLE Duck (BlueDuck HID)
- Touch calibration (XPT2046, same 4-point flow as NM-CYD-C5)
- SD card capture for all wireless features
- OTA update via web flasher
- Go Dark mode
- WiGLE / WDG Wars wardrive upload (2.4 GHz data only)

**RF-HAT features (requires SD Card Shim + CYM-CYD2USB-RFHAT build):**

- Sub-GHz RF (CC1101) — capture, replay, Z-Wave Scout, band scope, frequency scan, jammer
- 2.4 GHz ISM nRF24 — channel scan, sniffer, Futaba S-FHSS, jammer
- NFC / RFID (PN532) — card read, clone, emulate, key test
- Infrared (IR) — RMT capture, replay
- 433 MHz OOK — scan, capture, replay

---

## Reduced Buffer Sizes (No PSRAM)

The Classic CYD has no PSRAM. The NM-CYD-C5 uses 8 MB PSRAM for large data structures — on Classic CYD these are reduced to fit in the ESP32's ~99 KB of internal DRAM BSS. All reductions are guarded by `#if CONFIG_BOARD_HAS_PSRAM` so the NM-CYD-C5 retains full sizes.

| Buffer | NM-CYD-C5 | Classic CYD | Practical impact |
|--------|-----------|-------------|-----------------|
| WiFi scan / attack target list | 128 APs | **16 APs** | Busy venues with >16 visible APs show only the strongest 16 from a scan |
| BLE scan dedup window | 128 MACs | **16 MACs** | Dense venues: devices outside the 16-entry window may re-appear in the BLE log |
| BT Lookout watchlist | 64 entries | **16 entries** | Max 16 devices/OUI entries in the Dee Dee Detector CSV watchlist |
| BT Lookout cooldown slots | 16 | **8** | Up to 8 recently-alerted MACs suppressed from repeat triggers |
| Wardrive AP dedup window | 100 APs | **20 APs** | Dense AP environments can re-log the same AP after 20 different APs are seen |
| Wardrive UI update FIFO | 20 frames | **8 frames** | Cosmetic: rapid AP bursts may drop display updates; SD CSV log is unaffected |
| ESP-NOW device table | 32 sessions | **8 sessions** | Tracks 8 concurrent ESP-NOW device MACs before oldest is evicted |
| BLE Spoof profile list | 64 profiles | **8 profiles** | Max 8 spoof profiles loaded simultaneously |
| RFID card display list | 20 cards | **4 cards** | SD-browsed card list shows 4 entries at a time |
| BLE Chameleon payload | 4096 B | **512 B** | Chameleon BLE frame payload capped at 512 bytes |
| BlueDuck script list | 32 scripts | **8 scripts** | SD-listed BLE Duck scripts capped at 8 |
| WANA AP monitor table | 48 APs | **8 APs** | WiFi Analyzer tracks up to 8 APs |
| Deauth monitor table | 50 attacks | **12 attacks** | Passive deauth detector tracks 12 concurrent attack events |

---

## WiFi Throughput Reduction

To free the 27+ KB of IRAM required to link the firmware on Classic CYD, two ESP-IDF WiFi IRAM speed optimisations are disabled (`CONFIG_ESP_WIFI_IRAM_OPT=n`, `CONFIG_ESP_WIFI_RX_IRAM_OPT=n`). Espressif states these reduce WiFi throughput. In practice the impact is minimal for toolkit use — all operations work on short management frame exchanges, not raw throughput.

---

## The Dual-Core Advantage

The Classic CYD's ESP32-WROOM-32 is **dual-core** (two Xtensa LX6 cores), while the NM-CYD-C5 is single-core RISC-V. CYM pins the main LVGL / WiFi / BLE task to Core 0 and background scan tasks to Core 1. This gives the Classic CYD a structural timing advantage for the nRF24 jammer — the jammer task gets a fully dedicated core, isolated from LVGL and WiFi. The NM-CYD-C5 jammer competes for CPU on its single core, limiting effective sweep timing. See [2.4 GHz ISM Research](2.4GHz-ISM-Research) for the full analysis.

---

## Flashing Classic CYD

Use the **CYM Web Flasher** at [jimgat.github.io/CYM](https://jimgat.github.io/CYM) and select **Classic CYD (CYD2USB)** or **Classic CYD + RF-HAT (CYD2USB-RFHAT)** from the board dropdown.

For manual flash:
```
esptool.py --chip esp32 --port /dev/ttyUSB0 write_flash 0x0 CYM-CYD2USB-full.bin
```
Flash at address `0x0000`. Binary assets for each release are in [GitHub Releases](https://github.com/JimGat/CYM/releases).

---

## SD Card Layout

Same as NM-CYD-C5. All captures go to `/sdcard/lab/<feature>/`. With the SD Card Shim, the card is physically in the RF-HAT socket — the firmware path is unchanged.

---

## Known Issues

- **GPS is not available.** GPIO conflict with SPI pins.
- **Battery level indicator** shows nothing — no usable battery ADC pin configuration.
- The RGB LED is a **common-anode** discrete LED (GPIO 4/16/17, active-LOW), not a WS2812. Behavior from the user perspective is the same.
