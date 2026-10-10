# Waveshare ESP32-C5-Touch-LCD-2.8 (WS-C5-28) Support

## Official case and assembly manuals

Start with the **[Official CYM Cases](Official-Cases)** supplied by co-developer **@birolt29** for Waveshare WS-C5-28. The collection provides original EN/DE/TR manuals, print models and photos, preserving @birolt29 / @alen29 credits and CC BY-NC-ND 4.0 licensing. Check its wiring/charging and fit caveats before assembly; case designation is not peripheral qualification. Older RF-HAT/community enclosures remain alternatives on [Where To Get It](Where-To-Get-It#3d-printed-cases).

CYM firmware runs on the **Waveshare ESP32-C5-Touch-LCD-2.8** — a 2.8" ESP32-C5 touch board from Waveshare, referred to throughout CYM as **WS-C5-28**. It uses the same ESP32-C5 SoC as the NM-CYD-C5 (WiFi 6 dual-band, BLE 5, 802.15.4) and is **on par with NM-CYD-C5's core feature set** — same radios, same passive survey/wardrive/BLE/ESP-NOW feature set — plus onboard hardware NM-CYD-C5 doesn't have (IMU, temp/humidity, RTC, audio codec) that future CYM releases will build on.

---

## Hardware Overview

| Spec | NM-CYD-C5 (primary) | Waveshare WS-C5-28 |
|------|---------------------|---------------------|
| SoC | ESP32-C5-WROOM-1-N168R (RISC-V, single-core, 240 MHz) | ESP32-C5-WROOM-1-N8 (RISC-V, single-core, 240 MHz) |
| WiFi | WiFi 6 — 2.4 + 5 GHz dual-band | WiFi 6 — 2.4 + 5 GHz dual-band |
| BLE | Bluetooth 5 | Bluetooth 5 |
| 802.15.4 | Yes (Zigbee / Thread / WirelessHART survey) | Yes (same) |
| Flash | 16 MB | **32 MB** |
| PSRAM | 8 MB | 8 MB |
| Display | 2.8" ST7789 240×320 | 2.8" ST7789 240×320 (**color-inverted panel variant** — firmware handles this automatically) |
| Touch | XPT2046 **resistive**, SPI, needs 4-point calibration | CST3530 **capacitive**, I2C, interrupt-driven, **no calibration needed** |
| [Screen Orientation](Screen-Orientation) | Yes (v2.13.x+) | Yes (v2.15.01+, confirmed on hardware) — not available on Classic CYD |
| Backlight | GPIO 25, on/off only | CH32V003 IO expander, true PWM dimming |
| RGB LED | WS2812 (GPIO 27) | **None** |
| Vibrator | Yes (SC8002B amp + ERM motor) | **None** |
| GPS | LP-UART on GPIO 4/5 | UART on GPIO 11 (TX) / 12 (RX) |
| RF expansion | NM-RF-HAT via FPC2 connector | NM-RF-HAT via SD Card Shim + JST wiring (advanced/DIY — see below) |
| Extra onboard sensors | None | **QMI8658 6-axis IMU, SHTC3 temp/humidity, PCF85063A RTC, ES8311 I2S audio codec (mic + speaker)** |

The PCF85063A RTC is used by CYM's [Universal Clock](Universal-Clock); the IMU, environmental sensor, and audio codec remain future integration opportunities.

### PCF85063A battery-backed holdover

The RTC can retain UTC while the main board is off when its backup supply is present. Its frequency reference is an external 32.768-kHz quartz crystal, so real drift depends on crystal tolerance, temperature, loading/layout, aging, calibration, and battery condition. CYM currently uses an uncharacterized 50-ppm allowance (about 4.32 seconds/day) rather than promising the best-case result of one board. See [Universal Clock](Universal-Clock) and the [NXP PCF85063A data sheet](https://www.nxp.com/docs/en/data-sheet/PCF85063A.pdf).

---

## Second Microcontroller: CH32V003 IO Expander

WS-C5-28 has a small second microcontroller on board (CH32V003, RISC-V, I2C address `0x24`) that handles things the ESP32-C5 doesn't have free GPIO for: LCD reset, touch reset, backlight PWM, and an audio amp enable line. CYM's firmware explicitly resets both the LCD and touch controller through this chip at boot — both lines default to floating/input on power-up and need an active reset pulse, which the firmware sends automatically. You don't need to do anything for this; it's mentioned here only because it's a real architectural difference from NM-CYD-C5, where those reset lines don't exist (the display resets via power-on/software-reset and there's no separate touch reset).

---

## RF-HAT on WS-C5-28

The NM-RF-HAT is reachable but requires more manual work than on NM-CYD-C5:

- No FPC2 connector on this board — the RF-HAT's SD-shim SPI bus (GPIO 6/7/8) and its two control signals (GPIO 2/3, replacing NM-CYD-C5's GPIO 8/9) need to be wired by hand to the board's 12-pin SH1.0 expansion connector and SD card shim.
- This is an advanced/DIY setup, not a plug-and-play connection like NM-CYD-C5's ribbon cable.

---

## Flashing WS-C5-28

Use the **CYM Web Flasher** at [jimgat.github.io/CYM](https://jimgat.github.io/CYM) and select **WS-C5-28** from the board dropdown.

For manual flash:
```
esptool.py --chip esp32c5 --port /dev/ttyACM0 write_flash 0x0 CYM-WS-C5-28-full.bin
```
Flash at address `0x0000`. Binary assets for each release are in [GitHub Releases](https://github.com/JimGat/CYM/releases).

---

## SD Card Layout

Same as NM-CYD-C5. All captures go to `/sdcard/lab/<feature>/`.

---

## Known Issues

- IMU, temperature/humidity, and audio hardware are not yet exposed. The RTC is integrated with Universal Clock, but its drift allowance remains an uncharacterized engineering estimate pending physical soak measurements.
- No RGB LED indicator and no vibrator motor — any feature that uses those on NM-CYD-C5 has no equivalent here.
