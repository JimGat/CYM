# Waveshare ESP32-C5-Touch-LCD-3.5 — Experimental

Development channel only; not stable. Hardware validation pending.

CYM support for the **Waveshare ESP32-C5-Touch-LCD-3.5** exists as an experimental board target (`ws-c5-35`). A dedicated binary and web-flasher entry are available via the development channel (`?beta=1`). This build must not be flashed with the existing WS-C5-28 image — and vice versa.

Jim's ordered unit is **SKU 35419 / ESP32-C5-Touch-LCD-3.5-C**, the version supplied with the BF3901 camera and a 3.7 V lithium battery.[1] Physical qualification has not been completed.

## Vendor BSP reference

The board adapter was implemented from the [Waveshare ESP32-C5-Touch-LCD-3.5](https://github.com/waveshareteam/ESP32-C5-Touch-LCD-3.5) vendor BSP at commit `04e6134cf3e37309b2bec9915189efeace1161bc`. Pin definitions, CH32V006 IO expander protocol, ST7796 display initialization, and FT6336 touch driver were derived from that BSP.

## Implementation status

- **Display:** ST7796 320x480 SPI, BGR element order, color-invert, mirror(true, false) - from vendor BSP
- **Touch:** FT6336 capacitive via dedicated `esp_lcd_touch_ft6336` local component (not the Pancake driver)
- **IO expander:** CH32V006 16-bit little-endian I2C protocol (registers 0x02/0x03/0x05) - distinct from WS-C5-28's CH32V003
- **Backlight:** PWM via CH32V006 IO expander register 0x05
- **PMIC:** AXP2101 at I2C 0x34, probe-only (chip ID read, no rail programming)
- **GPS:** disabled - UART header is exposed but not wired in firmware; `BOARD_HAS_GPS=0`, `BOARD_TIME_HAS_GPS_UART=0`
- **Audio:** disabled (`BOARD_HAS_AUDIO=0`)
- **Battery ADC:** disabled (`BOARD_HAS_BATTERY_ADC=0`)
- **RGB LED:** disabled (`BOARD_HAS_RGB_LED=0`)
- **RTC:** disabled (`BOARD_TIME_HAS_RTC=0`)

## Why this should be a contained port

The board retains the ESP32-C5 foundation used by NM-CYD-C5 and WS-C5-28: 240 MHz RISC-V CPU, dual-band 2.4/5 GHz Wi-Fi, BLE 5, IEEE 802.15.4, 32 MB flash, and 8 MB PSRAM.[1][2] CYM's shared application, radio features, storage formats, Classic and Modern navigation contracts, and most build infrastructure should therefore remain common.

The board is not electrically interchangeable with WS-C5-28. Display, touch, power management, helper-controller protocol, resolution, external connector layout, and internal pin ownership require a separate board profile and physical qualification.

## Vendor-confirmed hardware inventory

| Resource | ESP32-C5-Touch-LCD-3.5-C (SKU 35419) | CYM impact |
|---|---|---|
| Module | ESP32-C5-WROOM-1U, external FPC dual-band antenna | Reuse the ESP32-C5 application and radio stack |
| Memory | 32 MB flash, 8 MB PSRAM | Sufficient for CYM and partial LVGL draw buffers |
| LCD | 3.5-inch IPS, 320×480, SPI, ST7796 | New panel initialization, geometry, rotation, and throughput qualification |
| Touch | FT6336 capacitive touch over I2C | New board-specific touch backend and coordinate transforms |
| Power | AXP2101 PMIC, rechargeable 3.7 V battery support | New power sequencing, battery, backlight, and shutdown handling |
| Helper MCU | CH32V006 I/O expander | Reuse the CYM expander abstraction concept, but not WS-C5-28's CH32V003 protocol without evidence |
| Storage | TF/microSD slot | Exact bus and chip-select must come from the C5 schematic/BSP |
| Sensors | QMI8658 IMU, PCF85063 RTC, SHTC3 temperature/humidity | Familiar peripherals, enabled only after board-specific bus verification |
| Audio | ES8311 codec, NS4150B amplifier, microphone and speaker connector | Keep capability gated until pin map and hardware tests are complete |
| Camera | BF3901 fitted on SKU 35419 | Record pin ownership and prevent conflicts even when CYM does not initialize the camera |
| Expansion | 32-pin 2.54 mm female header with UART and I2C labels | UART is the intended external GPS connection for this board |
| Controls | RESET, BOOT, and programmable PWR buttons | Board-specific button and PMIC behavior |

A 320×480 RGB565 full-screen image is 307,200 bytes. The panel has twice the pixels of a 240×320 display, so CYM should retain partial DMA-capable LVGL draw buffers rather than require two full-screen buffers.

## Visible expansion-header labels

Waveshare's order-page board label shows these external signal names:[1]

- `5V`, `G`, `SWD`, several `NC` positions
- ESP-side labels `0`, `1`, `9`, `28`, and `ADC`
- `SCL`, `SDA`, `TX`, `RX`
- `BAT`, `RST`, `PWR`, `3V3`, and ground
- helper-controller labels `E8` through `E15`

These labels establish available connector functions, not the complete internal routing. In particular, the UART connector confirms that GPS must remain an available capability, but the ESP32 GPIO numbers for TX/RX must be taken from the exact C5 schematic/BSP or measured on Jim's board. WS-C5-28's GPIO11/GPIO12 mapping must not be copied by assumption.

## Evidence collected from vendor BSP

Pin definitions, CH32V006 protocol, ST7796 init, and FT6336 touch were taken from the vendor ESP-IDF BSP repo (commit `04e6134cf3e37309b2bec9915189efeace1161bc`). The following are now resolved:

1. ST7796 SPI pins: MOSI=7, MISO=2, SCK=6, CS=8, DC=5, RST via IO expander (PIN_1), PCLK=60 MHz.
2. FT6336 I2C address 0x38, INT=GPIO3, RST via IO expander (PIN_0).
3. AXP2101 I2C address 0x34.
4. CH32V006 IO expander at I2C 0x24 (16-bit LE register protocol).
5. TF-card SPI CS=GPIO9, sharing SPI2_HOST with LCD.
6. I2C bus: SDA=GPIO27, SCL=GPIO26.

Still pending physical hardware validation:

1. PCB revision confirmation on Jim's SKU 35419 unit.
2. UART TX/RX GPIO assignment for the external GPS connector.
3. Camera, audio, sensor, USB, and expansion-header pin ownership and conflicts.
4. Whether camera and non-camera SKUs use one electrically identical base PCB.

## CYM architecture (implemented)

- Distinct Kconfig/build target: `CONFIG_BOARD_WS_C5_35` in `ESP32C5/components/board_hal/Kconfig`.
- Dedicated board profile: `ESP32C5/components/board_hal/include/boards/ws_c5_35.h`.
- Dedicated board adapter: `ESP32C5/main/ws_c5_35_port.c` (display, touch, backlight, IO expander).
- Local FT6336 component: `ESP32C5/components/esp_lcd_touch_ft6336/`.
- Local IDF-6-compatible copy of `espressif/esp_lcd_st7796 1.0.0`, retaining its Apache-2.0 license and vendor initialization table.
- Packaging: `ESP32C5/binaries-ws-c5-35/`, manifest `ESP32C5/docs/manifest.ws-c5-35.json`.
- Web flasher: beta-only entry visible with `?beta=1`.
- Build: `make ws-c5-35` or `scripts/build.sh ws-c5-35`.

## Hardware acceptance checklist

Support is not complete until Jim's SKU 35419 unit passes:

- exact SKU/PCB-revision record and cold-boot baseline
- USB flashing, reset, BOOT, and PWR behavior
- display initialization, colors, clipping, full-screen clears, all four orientations, and bounded redraw timing
- FT6336 touch accuracy and all four orientation transforms
- Classic and Modern navigation, including representative full-screen feature views
- TF-card mount, read, write, remount, and capture-file persistence
- UART GPS input/output at the exposed connector
- 2.4 GHz and 5 GHz Wi-Fi, BLE, IEEE 802.15.4, and ESP-NOW behavior
- AXP2101 battery telemetry, charging, backlight, shutdown, and USB/battery transitions
- RTC, IMU, temperature/humidity, audio, and camera conflict checks before enabling each capability
- repeated reboot/power-cycle and bounded soak with heap, DMA, task, and LVGL timing observations

Compilation alone is never physical qualification.

## Sources

[1] https://www.waveshare.com/esp32-c5-touch-lcd-3.5.htm?sku=35419
[2] https://docs.waveshare.com/ESP32-C5-Touch-LCD-3.5
[3] https://github.com/waveshareteam/ESP32-S3-Touch-LCD-3.5
