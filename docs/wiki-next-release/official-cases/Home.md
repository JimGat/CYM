# Cheap Yellow Monster — Research & Pen Test Wiki

![CYM Logo](images/CYM_Dexter_Logo.png)

CYM-NM28C5 is a pocket-sized WiFi 6 + BLE security toolkit and RF research platform. One shared firmware source tree ships on **four released boards** plus the new **Pancake-C5 DIY development-channel target (not stable)**: the **NM-CYD-C5** (primary/preferred), **Classic CYD**, **Waveshare ESP32-C5-Touch-LCD-2.8**, **Hosyond ES3C35P 3.5-inch**, and opt-in Pancake target. The Hosyond 2.8-inch and 4.0-inch variants remain planned ports. See [Supported Hardware](#supported-hardware) below.

> CYM is not an official LAB5 project, but it is unofficially supported by the LAB5 community and has a dedicated thread on the **[LAB5 Discord](https://discord.gg/Vuq2SmCbk5)** for setup help, field tips, and development discussion.

---

## Official CYM Cases

Start with the **[Official CYM Cases](Official-Cases)** supplied by CYM co-developer **@birolt29**: NM-CYD-C5, Classic CYD / 2432S028R, Waveshare WS-C5-28 and Hosyond ES3C35P 3.5-inch (Standard and Slim). Includes **English, German and Turkish manuals**, print models and original photos. Original @birolt29 / @alen29 credits and CC BY-NC-ND 4.0 licensing are preserved. Older community/RF-HAT cases remain alternatives on [Where To Get It](Where-To-Get-It#3d-printed-cases).

## Supported Hardware

| Board | Status | What you get |
|---|---|---|
| **[NM-CYD-C5](https://github.com/RockBase-iot/NM-CYD-C5)** — optionally with the **NM-RF-HAT** | ⭐ **Primary / preferred hardware for all features** | Full feature set: WiFi 6 (2.4 + 5 GHz), BLE 5, 802.15.4, ESP-NOW, GPS wardriving — plus, with the NM-RF-HAT, CC1101 Sub-GHz, nRF24, PN532 NFC/RFID, and IR. New features land here first. |
| **Classic CYD** (ESP32-2432S028R) | ✅ Supported | WiFi 2.4 GHz only (original single-core ESP32, no WiFi 6/5 GHz), BLE, ESP-NOW, wardriving (no GPS — GPIO conflict with SPI on this board). No 802.15.4, no [Screen Orientation](Screen-Orientation)/landscape mode. NM-RF-HAT reachable via an SD Card Shim — see [Classic CYD Support](Classic-CYD-Support). |
| **[Waveshare ESP32-C5-Touch-LCD-2.8](https://github.com/waveshareteam/ESP32-C5-Touch-LCD-2.8)** (WS-C5-28) | ✅ Supported | On par with NM-CYD-C5's core feature set (WiFi 6, BLE 5, 802.15.4, ESP-NOW, GPS wardriving), plus onboard IMU, temp/humidity, RTC, and audio codec — see [Waveshare WS-C5-28 Support](Waveshare-WS-C5-28-Support). |
| **[C5Lab Pancake DIY](https://github.com/C5Lab/pancake)** (`pancake-c5`) | 🧪 **Development channel only; not stable; remote hardware qualification pending** | Dedicated shared-firmware profile for the 3.5-inch 480×320 capacitive-touch DIY build. Available only from the development channel (`?beta=1`). Dedicated to D3h420, Janek, and OyczE — see [Pancake-C5 DIY — Development Channel](Pancake-C5). |
| **[Waveshare ESP32-C5-Touch-LCD-3.5](https://www.waveshare.com/esp32-c5-touch-lcd-3.5.htm?sku=35419)** (`ws-c5-35`) | 🚧 **Coming Soon; hardware ordered, not yet supported** | Planned dedicated target: ESP32-C5, ST7796 320×480 SPI display, FT6336 touch, AXP2101 PMIC, CH32V006 helper controller, TF card, audio and sensors. Jim's SKU 35419 includes the BF3901 camera and battery. See [WS-C5-35 Coming Soon](Waveshare-C5-35-Coming-Soon). |
| **[Hosyond ESP32-S3 2.8-inch](https://www.lcdwiki.com/2.8inch_ESP32-S3_Display)** | 🧪 Port planned; not released | ESP32-S3 N16R8, ILI9341V 240×320 SPI, FT6336G touch, SDIO, audio, battery and RGB. 2.4-GHz Wi-Fi/BLE; no 5 GHz/802.15.4. |
| **[Hosyond ESP32-S3 3.5-inch](https://www.lcdwiki.com/3.5inch_ESP32-S3_Display)** (`hosyond-s3-35`) | ✅ Released in v2.15.34; web-flasher supported | Full shared CYM application on ESP32-S3 N16R8 with ST77922 320×480 QSPI/TDDI, 8 MB OPI PSRAM, capacitive touch, 2.4-GHz Wi-Fi and BLE. Display/touch, both menu layouts, and Deauth Harvest were physically exercised; SD, RGB, battery ADC, UART GPS, broader radio coverage, and bounded soak remain pending qualification. |
| **[Hosyond ESP32-S3 4.0-inch](https://www.lcdwiki.com/4.0inch_ESP32-S3_Display)** | 🧪 Port planned; not released | ESP32-S3 N16R8, ST7796S 320×480 SPI, FT6336U touch, SDIO, audio, battery and RGB. 2.4-GHz Wi-Fi/BLE; no 5 GHz/802.15.4. |

See [Hosyond ESP32-S3 Family](Hosyond-ESP32-S3-Family) for the full comparison and support boundary. All four released boards are selectable in the normal [web flasher](https://jimgat.github.io/CYM/); Pancake-C5 is not a Stable target and remains available only through the Development-channel `?beta=1` selector until physical qualification.

---

## What's New — v2.15.34

### v2.15.34 — Hosyond ES3C35P release, @birolt29 Modern Menu showcase, Deauth Harvest evidence

- **Hosyond ES3C35P 3.5-inch:** promoted to the fourth release board and added to the web flasher with the shared CYM application.
- **Modern Menu by co-developer [@birolt29](https://github.com/birolt29):** choose **Modern** in the automatic first-boot **Home Layout** prompt to use the four-category home. To switch later—or change back—open **Settings → Screen**, select **Modern** or **Classic** in the **Home:** row, and tap **Save**.
- **Deauth Harvest:** adds cautious deauthentication/disassociation and association-sweep observations, with subtype, reason, direction, destination evidence, receive channel, aging, and protected-frame handling.

### v2.15.00 — Screen Orientation (landscape mode), redesigned WiFi list, dual-band Handshaker

Headline: **NM-CYD-C5 now runs in landscape** — a new [Screen Orientation](Screen-Orientation) feature (portrait/landscape/flipped, NVS-persisted) built by co-developer [@birolt29](https://github.com/birolt29) over 75+ build/test cycles, with dozens of screens individually redesigned for the wider layout. Full changelog in the [GitHub release notes](https://github.com/JimGat/CYM/releases). Highlights:

| Area | Change |
|------|--------|
| **[Screen Orientation](Screen-Orientation)** | New Settings → Screen → Orientation selector (0°/90°/180°/270°, NM-CYD-C5 only). Landscape layouts for Universal Remote, LED Remote, Bluetooth Lookout, Evil Portal, Timing Settings, Chameleon Ultra, GPS Info, the Main Menu, and more. |
| **WiFi Scan & Attack list** | Redesigned wardrive-style rows — band badge, SSID, Ch/RSSI/Auth, auth color-coded by deauth feasibility, multi-select. Portrait and landscape. |
| **Dual-band Handshaker** | Now covers 2.4 + 5 GHz with GPS-free regulatory domain detection (ETSI/FCC), plus a PMKID (hashcat 22000) capture path. |
| **Crash fixes** | MITM active-capture crash (missing screen teardown), PN532 Clone/Write/Emulate crashes (stack exhaustion), and two Chameleon Ultra BLE reconnect bugs (bond incorrectly deleted on benign disconnect; bond-reuse reconnect could hang forever). |
| **Navigation fixes** | Several screens where top-Back fell through to the Main Menu instead of the parent menu; display timeout now physically cuts the backlight instead of just blanking the panel. |

### v2.14.00 — Multi-board support graduates to stable; OT Air Survey hardening

Headline: **the Classic CYD and Waveshare WS-C5-28 join NM-CYD-C5 as fully supported boards.** Nearly 100 commits since the last stable release — full changelog in the [GitHub release notes](https://github.com/JimGat/CYM/releases). Highlights:

| Area | Change |
|------|--------|
| **Multi-board support** | Classic CYD and Waveshare WS-C5-28 promoted from beta to fully supported. WS-C5-28 first-hardware-boot bring-up: fixed touch controller init, touch/LCD reset sequencing, and a Kconfig authoring bug that silently disabled color inversion on both WS-C5-28 and (previously unnoticed) Classic CYD. |
| **OT Air Survey hardening** | Fixed two separate all-zero-MAC counting bugs (802.15.4 and WiFi feeds), an obs.jsonl export path that could silently stop writing mid-survey, a WiFi/BLE radio-switch race that corrupted scan results, and wired up passive ESP-NOW detection (previously never actually enabled during a survey). |
| **ESP-NOW detection fix** | Frame detector was missing the Action-No-Ack (broadcast) 802.11 subtype — broadcast ESP-NOW traffic was invisible to both ESP-NOW Scout and OT Air Survey; unicast was unaffected. |
| **New multi-board build discipline** | Any change to shared firmware source must now build clean on every board that compiles it in the same session — codified after a shared-code change silently broke Classic CYD's build for several versions before anyone rebuilt that board. |

---

![Main Menu](images/Main_Menu.bmp)

> **Legal notice:** All techniques documented here are intended for use on networks, devices, and RF environments you own or have explicit written authorization to test. Unauthorized interception, injection, or jamming is illegal in most jurisdictions.

---

## Pages

### RF Attack Surface (requires NM-RF-HAT)
| Page | What it covers |
|------|---------------|
| [Sub-GHz RF Research](Sub-GHz-RF-Research) | CC1101: capture, replay, band scope, Z-Wave Scout, frequency scan |
| [2.4 GHz ISM Research](2.4GHz-ISM-Research) | nRF24: channel scan, protocol sniffer, Futaba S-FHSS RC analysis |
| [NFC & RFID Hub](NFC-RFID) | Chameleon Ultra BLE: LF/HF read, physical EM410X/HID Prox Clone T5577 with read-back verification, Slot Manager/Clone to Slot, dumps, and SD workflows; PN532 tools |
| [Infrared](Infrared) | RMT capture, replay, LED strip control |

### Wireless Security Research
| Page | What it covers |
|------|---------------|
| [WiFi Security Research](WiFi-Security-Research) | Deauth, handshake capture, evil twin, ESP-NOW Scout, Chanalizer |
| [Wardriving & Geolocation](Wardriving) | Passive WiFi + BLE mapping, WiGLE / WDG Wars export |
| [BLE & Bluetooth Research](BLE-Research) | GATT Walker, BT Lookout, device enumeration, drone detection |
| [Drone Research](Drone) | Drone Detector (passive Remote ID scanner) + Drone Spoof (synthetic F3411 beacon) |
| [OT/IoT Air Survey](OT-Air-Survey) | Passive multi-radio survey (WiFi/BLE/ESP-NOW/802.15.4), GPS-stamped device log, WirelessHART/Zigbee/Thread classification |

---

## Hardware at a Glance

![CYM Hardware](images/CheepYellowMonster.jpg)

| Component | Spec |
|-----------|------|
| SoC | ESP32-C5 · RISC-V 240 MHz · WiFi 6 (2.4 + 5 GHz) · BT 5 |
| Display | 2.8″ ST7789 240×320 touch |
| Storage | MicroSD (FAT32) for all captures |
| Sub-GHz | CC1101 (300–928 MHz) via NM-RF-HAT DIP 1 |
| 2.4 GHz ISM | nRF24L01+ + AT2401C PA/LNA (+20 dBm) via DIP 2 |
| NFC/RFID | PN532 (ISO14443A/B, ISO18092) via DIP 3 |
| IR | 940 nm TX LED + 38 kHz demod RX via DIP 4 |
| 433 MHz OOK | T2-433M TX + R4A_433 superheterodyne RX via DIP 5 |

All captures save to `/sdcard/lab/<feature>/` on the microSD card.

**SD Asset Repository:** Pre-built SD card assets (OUI vendor table, MIFARE key dictionary, and more) are available for download at **[github.com/JimGat/CYM-SD-Assets](https://github.com/JimGat/CYM-SD-Assets)**. Drop the files into `/sdcard/lab/` after your first SD provision to enable OUI vendor lookup in BLE scan and extended MIFARE key coverage in card dumps.

---

### Getting Started
| Page | What it covers |
|------|---------------|
| [Getting Started](Getting-Started) | **First-time setup** — touch calibration, resistive touch + red dot, SD card layout, RF-HAT enablement, GPS wiring |
| [Where To Get It](Where-To-Get-It) | Board, RF-HAT, GPS, cases, web flasher, manual flash |
| [Support & Community](Support-and-Community) | [LAB5 Discord](https://discord.gg/Vuq2SmCbk5), GitHub, contributing, credits |

### Quick Reference
| Page | What it covers |
|------|---------------|
| [Use Cases](Use-Cases) | Master list of all real-world field scenarios — one page, every feature |
| [Universal Clock](Universal-Clock) | Display-only, Client/AP NTP, GPS/RTC source trust, offline FT4/FT8 time service, and conservative accuracy grid |
| [Modern Menu](Modern-Menu) | Complete Modern category map, conditional tiles, navigation behavior, and Deauth Harvest placement |
| [Screen Orientation](Screen-Orientation) | Landscape/portrait rotation (NM-CYD-C5), how to enable it, redesigned-screen gallery |

### Hardware Variants
| Page | What it covers |
|------|---------------|
| [Classic CYD Support](Classic-CYD-Support) | ESP32-2432S028R (CYD2USB) — what works, what's absent, buffer reductions, dual-core advantage, flash instructions |
| [Waveshare WS-C5-28 Support](Waveshare-WS-C5-28-Support) | ESP32-C5-Touch-LCD-2.8 — hardware differences, battery-backed RTC, RF-HAT wiring, and flash instructions |
| [Pancake-C5 DIY — Development Channel](Pancake-C5) | C5Lab 3.5-inch capacitive DIY target, pin map, beta flashing, dedication, and remote qualification checklist |
| [Waveshare WS-C5-35 Coming Soon](Waveshare-C5-35-Coming-Soon) | ESP32-C5-Touch-LCD-3.5 — saved SKU 35419 hardware inventory, architectural differences, implementation gates, and arrival checklist |
| [Hosyond ESP32-S3 Family](Hosyond-ESP32-S3-Family) | 2.8/3.5/4.0-inch controller, bus, pin-map and development-status comparison |

### Hardware Add-ons
| Page | What it covers |
|------|---------------|
| [Haptic Feedback](Haptic-Feedback) | ERM vibrator motor build, wiring, which features use it and how |

### Community
| Page | What it covers |
|------|---------------|
| [Videos](Videos) | Community reviews, showcases, and tutorials |
| [Contributors](Contributors) | Everyone who helped build and improve CYM |

---

<p align="center">
  <a href="https://youtu.be/00yGLaB4jWk" target="_blank">
    <img src="https://img.youtube.com/vi/00yGLaB4jWk/maxresdefault.jpg" alt="Cheap Yellow Monster Firmware for Esp32-C5 CYD — Valleytech Custom Solutions" width="80%"/>
  </a>
  <br/>
  <em>CYM Firmware Review (v2.12.0) — <strong>Valleytech Custom Solutions</strong> &nbsp;·&nbsp; <a href="https://youtu.be/00yGLaB4jWk">Watch on YouTube ▶</a></em>
</p>

---

![DeeDee](images/DeeDee.png)
