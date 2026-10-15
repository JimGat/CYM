# Getting Started with CYM

## Official case and assembly manuals

Start with the **[Official CYM Cases](Official-Cases)** supplied by co-developer **@birolt29** for your exact board. The collection provides original EN/DE/TR manuals, print models and photos, preserving @birolt29 / @alen29 credits and CC BY-NC-ND 4.0 licensing. Check its wiring/charging and fit caveats before assembly; case designation is not peripheral qualification. Older RF-HAT/community enclosures remain alternatives on [Where To Get It](Where-To-Get-It#3d-printed-cases).

This page covers everything a first-time user needs to get CYM running correctly: flashing the firmware, setting up the SD card, understanding touch behavior, enabling the RF-HAT, and wiring a GPS module.

CYM currently releases on four boards — see [Supported Hardware](Home#supported-hardware). This guide is written around **NM-CYD-C5** (the primary/preferred board); most of it applies to NM-CYD-C5, Classic CYD, WS-C5-28, and the released Hosyond ES3C35P 3.5-inch target. The Waveshare ESP32-C5-Touch-LCD-3.5 (`ws-c5-35`) is [Coming Soon](Waveshare-C5-35-Coming-Soon), but is not yet supported and has no CYM image or web-flasher entry. The Hosyond 2.8-inch and 4.0-inch variants remain development targets; see [Hosyond ESP32-S3 Family](Hosyond-ESP32-S3-Family). The resistive-touch section (§3) is NM-CYD-C5 / Classic CYD only—Waveshare and ES3C35P use capacitive touch—and RF-HAT enablement (§4) remains board-specific.

---

## 1. Flash the Firmware

The fastest path is the web flasher — no toolchain required.

### [CYM Web Flasher](https://jimgat.github.io/CYM/)

1. Open the flasher in Chrome or Edge (Web Serial API required).
2. Pick a released board from the selector (NM-CYD-C5, Classic CYD, or Waveshare WS-C5-28) and plug it in via USB-C (or USB, on Classic CYD). Hosyond S3 boards are not selectable until their ports pass hardware qualification.
3. Click **Connect**, select the port, click **Flash**.
4. When flashing completes, the board resets automatically.

The **Stable** tab installs the latest release. The **Dev** tab installs the latest `Jimgat_Dev` build.

---

## 2. SD Card Setup

CYM expects a FAT32 microSD card (any size works; 8–32 GB is typical). The firmware creates its own folder structure — you do not need to manually create directories.

### First boot

On first boot CYM mounts the SD card and is ready to use. Some features need their resource files before they work (e.g. OUI lookups, RFID key dictionary).

### SD Provision — create the full folder tree

Go to **Settings → SD Card → Validate & Provision** and confirm.

This creates all expected directories and default config files in one pass. **Existing files are never overwritten.** The status message shows how many items were created and how many were already present (e.g. `Done - 59 created, 3 OK`).

### Expected folder layout after provision

```
/sdcard/lab/
    wardrives/        WiFi + BLE wardrive CSV files
    handshakes/       WPA2 PCAP + HCCAPX captures
    espnow/           ESP-NOW frame logs
    bluetooth/        BLE scan exports, spooflist.csv
    rfid/
        keys/         mf_keys.dic (MIFARE key dictionary)
        hf/           High-frequency card dumps
        lf/           Low-frequency card dumps
        logs/         RFID operation logs
    tpms/             Tyre pressure sensor logs
    sub-ghz/          CC1101 captures, .sub replay files
    ir/               IR captures
    gps/              GPS track logs
```

### SD Asset Repository

The [CYM-SD-Assets](https://github.com/JimGat/CYM-SD-Assets) repository contains pre-built resource files:

| File | Purpose |
|------|---------|
| `lab/ouilist.bin` | OUI vendor table for BLE/WiFi device manufacturer lookup |
| `lab/rfid/keys/mf_keys.dic` | Extended MIFARE key dictionary (beyond the 16 built-in keys) |

Download these and copy them into the matching paths on the SD card after provisioning.

### Troubleshooting SD issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| "SD mount failed" on boot | Card not inserted or wrong format | Reformat FAT32; try a different card |
| Missing feature data (OUI, keys) | Resource files not on card | Download from SD-Assets repo and provision |
| UI freezes mid-wardrive | SD card error during write | Use a name-brand card; avoid cheap bulk cards |

---

## 2a. Choose the Home menu

On first boot with no saved preference, CYM opens the **Home Layout** chooser. Tap **Modern** for @birolt29's four-category home or **Classic** for the original tile-oriented home. To switch later—or to change back—open **Settings → Screen**, select **Modern** or **Classic** in the **Home:** row, and tap **Save**. The change applies without reinstalling firmware and persists in NVS.

## 3. Resistive Touch — What You Need to Know

> **NM-CYD-C5 and Classic CYD only.** Waveshare WS-C5-28 and Hosyond ES3C35P use capacitive touch panels — they work like phone screens, need no calibration, and none of this section applies to them.

The NM-CYD-C5 uses a **resistive touch panel**, not capacitive. Resistive touch works differently from a phone screen.

### Press firmly

Resistive touch requires deliberate pressure. Light grazes, fingernail edges, or angled presses all produce an inaccurate reading. Use the flat pad of your finger and press with intent. If a tap does not register, press harder and more directly.

### The red dot is intentional

A small **red dot** appears on screen wherever the firmware detected a press. This is deliberate press-location feedback — it shows exactly where the firmware saw the contact, not where you intended to tap. If the dot lands away from your intended target, the calibration may need adjustment or you may be pressing at an angle.

### Touch calibration

Calibration maps the raw ADC readings from the touch panel to screen pixel coordinates. If touches feel consistently off in one area (especially corners or edges), running calibration fixes this.

**Where to calibrate:**
- Settings → Screen → Recalibrate Touch

**What happens:**
1. A full-screen calibration mode starts showing yellow corner brackets.
2. The hint "Resistive touch - press firmly / Red dot shows detected point" stays visible throughout.
3. Tap each of the four corners when prompted (1/4 through 4/4).
4. A confirmation button appears — tap it to save. If you miss or the countdown expires, calibration restarts.

**When to recalibrate:**
- After first flash
- After the device has been dropped or the panel shifted
- Any time touches feel offset by more than a few pixels

---

## 4. RF-HAT Enablement

The NM-RF-HAT expansion board adds five RF modules (CC1101, nRF24, PN532, IR, RF433). These features are **hidden by default** and only appear after you enable the RF-HAT.

### Enable the RF-HAT

1. Connect the NM-RF-HAT to the NM-CYD-C5 via the 14-pin FPC connector.
2. In CYM: **Settings → NM-RF-HAT → Enable**.
3. Restart or navigate back to the home screen.
4. Two new tiles appear on the home screen: **Infrared** and **Radio**.

### DIP switch quick reference

Each module has a dedicated DIP switch. Turn only the switch for the module you are using ON:

| DIP | Module |
|-----|--------|
| 1 | CC1101 Sub-GHz (315/433/868/915 MHz) |
| 2 | nRF24L01+ 2.4 GHz (with AT2401C PA/LNA) |
| 3 | PN532 NFC/RFID |
| 4 | IR TX/RX (940 nm LED + 38 kHz demod) |
| 5 | RF433 OOK TX/RX |

Only one DIP at a time; they share the same SPI/I2C GPIO pins.

### All 5 modules are functional in v2.12.x

| Module | Status | Notes |
|--------|--------|-------|
| CC1101 | Working | Band Scope, Capture, Replay, Z-Wave Scout, Jammer, TPMS, .sub files |
| nRF24 | Working | Channel Scan, Sniffer, Futaba S-FHSS, Jammer |
| PN532 | Working | Scan/Read, Clone, Emulate, Key Test (+ SD dictionary) |
| IR | Working | Capture (5s), Replay, TV-B-Gone, Jammer, Universal, Edit Files |
| RF433 | Working | OOK Scan, Fox Hunt |

> **PN532 range note:** The PN532 on the NM-RF-HAT has shorter read range than a standalone breakout board. Cards may need to be held nearly touching the antenna area. This is a hardware layout limitation of the RF-HAT, not a firmware issue.

---

## 5. GPS Wiring

A GPS module is optional and only needed for Wardriving. Without GPS, wardrive still logs networks — coordinates will be blank or use a manually set position.

### Recommended module

**Teyleten Robot ATGM336H** (GPS+BDS, CASIC chipset) — 3.3 V UART, onboard patch antenna.

| Where | Search term |
|-------|------------|
| Amazon ASIN B09LQDG1HY | Teyleten Robot ATGM336H |
| AliExpress | "ATGM336H GPS BDS module UART" |

### Solderless vs. wired

**Solderless path (recommended for NM-CYD-C5):** The NerdMiner ATGM336H module is designed to plug directly into the LP-UART header on the NM-CYD-C5 without soldering. Check the NerdMiner accessory listings at [nmminer.com](https://www.nmminer.com).

**Wired path:** Use a generic ATGM336H module with four jumper wires.

### Pin mapping

| GPS module pin | NM-CYD-C5 pin | Notes |
|----------------|---------------|-------|
| TX (GPS output) | GPIO 4 | GPS → ESP32 receive |
| RX (GPS input) | GPIO 5 | ESP32 → GPS transmit |
| VCC | 3.3 V or 5 V | Most ATGM336H breakout boards have an onboard LDO and accept either |
| GND | GND | |

> **Note:** GPIO 4 and 5 are the LP-UART header on the NM-CYD-C5. The header is labeled on the silkscreen.

### Serial settings

| Setting | Value |
|---------|-------|
| Default baud | 9600 (1 Hz fix rate) |
| High-speed baud (opt-in) | 115200 (5 Hz fix rate — see Options → GPS Baud) |
| Data bits | 8 |
| Stop bits | 1 |
| Parity | None |
| Protocol | NMEA 0183 ($GPRMC, $GPGGA) |

CYM auto-detects the baud rate at boot — if you previously set 115200, it is picked up automatically on the next start.

### Troubleshooting GPS

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| No fix after 2+ minutes outside | Normal cold start | Wait up to 5 minutes on first power-up; subsequent starts are faster |
| GPS icon always grey/slashed | Wiring or baud mismatch | Check TX/RX wiring (swap if needed); verify VCC is 3.3 V |
| Coordinates drift at standstill | Normal GPS position wander | Expected; 3–8 m wander is typical indoors or with weak sky view |
| Wardrive starts immediately without GPS | Last-known position in NVS | Expected; uses 150 m accuracy fallback automatically |

---

## 6. Go Dark — Covert Operating Mode

Go Dark turns the display completely off while keeping all firmware running. It is distinct from the auto-dim timeout: in Go Dark, both the LCD panel signal and the backlight GPIO are cut -- no display glow, no status indication, no visible screen from any angle.

**Activate Go Dark:** Long-press the **Go Dark** button in Settings, or tap the moon icon in the top-bar quick menu (on screens that show it).

**Wake from Go Dark (two methods):**

| Method | How |
|--------|-----|
| **BOOT (only when provided as an application input)** | Double-click or hold 2 seconds. Not available on WS-C5-35 (GPIO28 is GPS RX) or WS-S3-5B. Do not press BOOT as their wake workaround. |
| **Full-screen touch hold** | Hold anywhere continuously for **5 seconds**, then release. WS-C5-35 requires v3.0.3 Development; v3.0.2 omitted its touch-wake polling path. |

The 5-second hold requirement is deliberate: a shorter threshold caused false wakes from the display's own LVGL DMA flush cycles, which intermittently touch the SPI bus in patterns the resistive touch driver could misread. Touches shorter than 5 seconds are ignored entirely while the display is off. Once you complete the hold, the display returns immediately.

All scanning, BLE observation, BT Lookout, and haptic alerts continue normally while in Go Dark. This makes it the ideal operating mode for covert carry: device in a pocket or bag, screen completely dark, haptic alerts still firing on watchlist hits.

---

## 7. WiFi Visual Tools — What is What

CYM has two distinct WiFi visualization tools that are sometimes confused:

| Tool | Menu label | What it shows |
|------|-----------|---------------|
| **Channel Analyzer** | WiFi → Channel Analyzer | Bar graph of AP count and signal density per channel. Static survey tool. Tap a bar to see SSIDs on that channel. |
| **WiFi Band Scope** | WiFi → WiFi Scope | Real-time swept spectrum scan across selected 2.4 GHz or 5 GHz channels. Shows live signal level as a moving waterfall. |

Both are passive — they only receive, never transmit.

---

## 8. Wardrive Is Not an Attack

Wardrive lives on the **main home screen** (not under WiFi Attacks). It is a passive collection tool — the radio listens, it never transmits or deauthenticates. All data is logged to the SD card and can be uploaded to WiGLE or WDG Wars.

See the [Wardriving & Geolocation](Wardriving) wiki page for full details.
