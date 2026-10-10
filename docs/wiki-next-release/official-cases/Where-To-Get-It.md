# Where to Get It

![CYM Logo](images/CYM_Dexter_Logo.png)

Everything you need to build and flash a Cheap Yellow Monster.

---

## Flash the Firmware (Easiest Start)

No toolchain needed. Plug in a released board via USB-C (or USB, on Classic CYD) and flash directly from your browser. CYM currently supports four release boards—see [Supported Hardware](Home#supported-hardware). The Hosyond ES3C35P 3.5-inch is available directly in the flasher; the 2.8-inch and 4.0-inch Hosyond variants remain development targets.

### [⚡ CYM Web Flasher — jimgat.github.io/CYM](https://jimgat.github.io/CYM/)

![CYM Web Flasher](images/deedee_flasher.png)

- Works in Chrome and Edge (Web Serial API required)
- **Board** selector: NM-CYD-C5, Classic CYD, Waveshare WS-C5-28, or Hosyond ES3C35P 3.5-inch
- **Stable** tab: latest released firmware from `main`
- **Dev** tab: latest test build from `Jimgat_Dev` branch — new features first
- No drivers needed on Linux or Mac; Windows may require the [CP210x driver](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)

### Manual Flash (esptool)

All required binaries for every board are attached to every [GitHub Release](https://github.com/JimGat/CYM/releases). **Bootloader offset differs by chip** — ESP32-C5 boards (NM-CYD-C5, WS-C5-28) use `0x2000`; the Classic CYD (plain ESP32) uses `0x1000`.

**NM-CYD-C5** (`--chip esp32c5`):
```bash
esptool.py --chip esp32c5 --baud 460800 write_flash \
  0x2000  bootloader.bin \
  0x8000  partition-table.bin \
  0x10000 CYM-NM28C5.bin
```

**Waveshare WS-C5-28** (`--chip esp32c5`):
```bash
esptool.py --chip esp32c5 --baud 460800 write_flash \
  0x2000  bootloader.bin \
  0x8000  partition-table.bin \
  0x10000 CYM-WS-C5-28.bin
```

**Classic CYD / CYD-2432S028** (`--chip esp32` — note the `0x1000` bootloader offset):
```bash
esptool.py --chip esp32 --baud 460800 write_flash \
  0x1000  bootloader.bin \
  0x8000  partition-table.bin \
  0x10000 CYM-CYD-2432S028.bin
```

Each board's `bootloader.bin` and `partition-table.bin` are board-specific — use the set from the same release/board, don't mix them. Alternatively, each release also has a merged `*-full.bin` per board (bootloader + partition table + firmware already combined) that flashes as a single file at `0x0000` with any flasher that accepts a full image.

---

## Hardware

### NM-CYD-C5 — Primary / Preferred Board

[![CYM Hardware](images/CheepYellowMonster.jpg)](https://www.nmminer.com/product/nm-cyd-c5/)

The heart of CYM, and the primary/preferred board — new features land here first, and it's the only board with the full NM-RF-HAT plug-and-play expansion. ESP32-C5, 2.8″ ST7789 touch display, MicroSD, WS2812 RGB LED, all in a compact CYD form factor.

| Where | Link |
|-------|------|
| **Official store (nmminer.com)** | [nmminer.com/product/nm-cyd-c5](https://www.nmminer.com/product/nm-cyd-c5/) |
| Board documentation & schematics | [github.com/RockBase-iot/NM-CYD-C5](https://github.com/RockBase-iot/NM-CYD-C5) |

---

### Classic CYD (ESP32-2432S028R) — Also Supported

The original dual-USB "Cheap Yellow Display" board that started the CYD ecosystem. Widely available from many generic sellers — there's no single official store. See [Classic CYD Support](Classic-CYD-Support) for what works and what's different from NM-CYD-C5.

| Where | Search term |
|-------|------|
| AliExpress / Amazon / generic electronics sellers | "ESP32-2432S028R" or "Cheap Yellow Display dual USB" |

---

### Waveshare ESP32-C5-Touch-LCD-2.8 (WS-C5-28) — Also Supported, New

Waveshare's own ESP32-C5 touch board — on par with NM-CYD-C5's core feature set, plus onboard IMU, temp/humidity, RTC, and audio codec. See [Waveshare WS-C5-28 Support](Waveshare-WS-C5-28-Support) for hardware differences and RF-HAT wiring.

| Where | Link |
|-------|------|
| **Official store (Waveshare)** | [waveshare.com](https://www.waveshare.com/) — search "ESP32-C5-Touch-LCD-2.8" |
| Board documentation | [github.com/waveshareteam/ESP32-C5-Touch-LCD-2.8](https://github.com/waveshareteam/ESP32-C5-Touch-LCD-2.8) |

---

### Waveshare ESP32-C5-Touch-LCD-3.5 — Coming Soon

A dedicated CYM port is planned for Waveshare's 320×480 ESP32-C5 board. Jim has ordered **SKU 35419 / ESP32-C5-Touch-LCD-3.5-C**, which includes the BF3901 camera and a 3.7 V lithium battery. The board is not currently supported and must not be flashed with the WS-C5-28 image.

| Where | Link |
|---|---|
| Official order page for SKU 35419 | [Waveshare ESP32-C5-Touch-LCD-3.5-C](https://www.waveshare.com/esp32-c5-touch-lcd-3.5.htm?sku=35419) |
| Board documentation | [Waveshare documentation](https://docs.waveshare.com/ESP32-C5-Touch-LCD-3.5) |
| CYM port status and arrival checklist | [WS-C5-35 Coming Soon](Waveshare-C5-35-Coming-Soon) |

The planned target uses its own ST7796, FT6336, AXP2101, CH32V006, pin-map, package, and eventual web-flasher entry. Its exposed UART header is reserved for board-specific GPS support once the exact C5 GPIO map is verified.

---

### Hosyond ESP32-S3 Display Family — Development Targets

Hosyond/LCDWiki sells related ESP32-S3 N16R8 boards in 2.8-inch, 3.5-inch, and 4.0-inch sizes. CYM support is under development; do not buy one expecting the current CYM web flasher to support it yet. See [Hosyond ESP32-S3 Family](Hosyond-ESP32-S3-Family) for exact controller, bus, and status differences.

| Board | Documentation | CYM status |
|---|---|---|
| 2.8-inch ES3C28P — ILI9341V + FT6336G, 240×320 | [LCDWiki 2.8-inch](https://www.lcdwiki.com/2.8inch_ESP32-S3_Display) | Planned/documented; full shared CYM port pending |
| 3.5-inch ES3C35P — ST77922 QSPI/TDDI, 320×480 | [LCDWiki 3.5-inch](https://www.lcdwiki.com/3.5inch_ESP32-S3_Display); earlier core vendor documents are tracked in CYM | Released shared-CYM target in v2.15.34; selectable in the web flasher. Display/touch and current menu/detector workflow physically exercised; remaining peripherals retain their documented qualification gates. |
| 4.0-inch ES3C40P — ST7796S + FT6336U, 320×480 | [LCDWiki 4.0-inch](https://www.lcdwiki.com/4.0inch_ESP32-S3_Display) | Planned/documented; full shared CYM port pending |

All three are 2.4-GHz Wi-Fi/BLE boards; they do not provide ESP32-C5 5-GHz Wi-Fi or 802.15.4.

---

### NM-RF-HAT — RF Expansion Board

Adds CC1101 Sub-GHz, nRF24L01+ 2.4 GHz, PN532 NFC/RFID, IR TX/RX, and RF433 OOK. DIP switches select which module is active. All ICs are soldered on-board — no plug-in modules to lose.

| Where | Link |
|-------|------|
| **Official store (nmminer.com)** | [nmminer.com](https://www.nmminer.com) — search "NM-RF-HAT" |
| Board documentation | [github.com/RockBase-iot/NM-CYD-C5](https://github.com/RockBase-iot/NM-CYD-C5) |

> **DIP switch quick reference:**
> DIP 1 = CC1101 Sub-GHz · DIP 2 = nRF24L01+ · DIP 3 = PN532 NFC/RFID · DIP 4 = IR · DIP 5 = RF433

---

### GPS Module (Optional — for Wardriving)

Any ATGM336H-based 3.3 V UART module works. The Teyleten Robot 2-pack is the confirmed tested option.

| Where | Search term |
|-------|------------|
| [Amazon (ASIN B09LQDG1HY)](https://www.amazon.com/dp/B09LQDG1HY) | Teyleten Robot ATGM336H |
| AliExpress | "ATGM336H GPS BDS module UART" |

**Wiring (LP-UART header on NM-CYD-C5):**

| GPS pin | NM-CYD-C5 pin | Notes |
|---------|---------------|-------|
| TX | GPIO 4 | GPS output → ESP32 receive |
| RX | GPIO 5 | ESP32 transmit → GPS input |
| VCC | 3.3 V or 5 V | Most ATGM336H breakout boards have an onboard LDO; both voltages work |
| GND | GND | |

Default baud: **9600 / 1 Hz**. Opt-in 115200 / 5 Hz available in Options → GPS Baud (ATGM336H confirmed). CYM auto-detects baud on boot. See [Getting Started → GPS Wiring](Getting-Started#5-gps-wiring) for full troubleshooting guide.

---

### Haptic Vibrator (Optional — for haptic alerts)

Any small 3 V ERM coin or cylinder vibrator motor. Requires a small diode circuit on the SPEAK_IN header — see [Haptic Feedback](Haptic-Feedback) for the full build guide and wiring photos.

| What | Where |
|------|-------|
| ERM vibrator motor (3 V, 8–16 Ω) | AliExpress — search "ERM vibrator motor 3V" or "coin vibration motor 10mm" |
| 1N5819 Schottky diode | Any electronics supplier |
| 1N4148 signal diode | Any electronics supplier |

---

## 3D Printed Cases

![Dexters Lab Splash](images/DextersLab_Splash.png)

### Official CYM Cases — @birolt29

**[Official CYM Cases](Official-Cases)** are the preferred collection supplied by CYM co-developer **@birolt29**, with exact-board models, original photos and manuals in **EN (English), DE (German) and TR (Turkish)**.

- **NM-CYD-C5** — [Thingiverse 7420383](https://www.thingiverse.com/thing:7420383), manual Rev 2
- **Classic CYD / 2432S028R** — [Thingiverse 7420388](https://www.thingiverse.com/thing:7420388), manual Rev 1
- **Waveshare WS-C5-28** — [Thingiverse 7417770](https://www.thingiverse.com/thing:7417770), manual Rev 4
- **Hosyond ES3C35P 3.5-inch** — [Thingiverse 7420392](https://www.thingiverse.com/thing:7420392), Standard and Slim, manual Rev 1

Preserve original **@birolt29 / @alen29** attribution and **CC BY-NC-ND 4.0** licensing. Read the assembly caveats on the official-case page: these packages do not establish RF-HAT fit, Classic CN1 GPS compatibility or peripheral qualification.

### Alternative community / RF-HAT cases

The following older community-designed enclosures remain alternatives for the full NM-CYD-C5 + NM-RF-HAT stack.

| Case | Link | Notes |
|------|------|-------|
| **MakerWorld** — GPS + 18650 battery | [makerworld.com/en/models/2670158](https://makerworld.com/en/models/2670158-case-for-nm-rf-hat-cyd2usb-atgm336h-18650) | Full field kit with onboard battery; DIP switches internal |
| **Printables** — Magnetic lid | [printables.com/model/1638712](https://www.printables.com/model/1638712-cyd-nm-rf-hat-enclosure-case-magnetic-6x2mm-magnet) | 6×2 mm magnets; clean look; DIP switches internal |
| **Thingiverse** — Community favorite | [thingiverse.com/thing:7305463](https://www.thingiverse.com/thing:7305463) | DIP switches accessible from exterior — best for frequent module switching |

> **Tip:** If you switch RF modules often (DIP 1–5), the older Thingiverse RF-HAT alternative above is the one described here with external DIP switch access. For the other two cases, consider soldering short extension wires to the switch pads and mounting a panel-mount DIP switch externally before printing.

---

## Source Code & Releases

| Resource | Link |
|----------|------|
| GitHub repository | [github.com/JimGat/CYM](https://github.com/JimGat/CYM) |
| Latest release + binaries | [github.com/JimGat/CYM/releases](https://github.com/JimGat/CYM/releases) |
| Web flasher | [jimgat.github.io/CYM](https://jimgat.github.io/CYM/) |

---

![DeeDee](images/DeeDee.png)
