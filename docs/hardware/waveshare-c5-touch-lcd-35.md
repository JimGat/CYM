# Waveshare ESP32-C5-Touch-LCD-3.5 — Coming Soon

CYM support for the **Waveshare ESP32-C5-Touch-LCD-3.5** is planned as a dedicated board target, provisionally named `ws-c5-35`. It is **not supported yet**, does not have a CYM binary or web-flasher entry, and must not be flashed with the existing WS-C5-28 image.

Jim's ordered unit is **SKU 35419 / ESP32-C5-Touch-LCD-3.5-C**, the version supplied with the BF3901 camera and a 3.7 V lithium battery.[1] Bring-up begins when that exact unit arrives and its PCB revision can be recorded.

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

## Evidence still required before implementation

The public product page currently establishes the component inventory but not the complete C5 pin map or helper-controller command protocol.[1][2] Before coding board constants, collect and preserve:

1. The official ESP32-C5-Touch-LCD-3.5 schematic and PCB revision.
2. Waveshare's C5 ESP-IDF/Arduino example source and any CH32V006 protocol definitions.
3. ST7796 SPI pins, command/data/reset ownership, backlight path, bus rate, and initialization table.
4. FT6336 address, reset, interrupt, orientation, and coordinate range.
5. AXP2101 address, rail configuration, charge state, battery telemetry, PWR-button, and shutdown behavior.
6. TF-card bus pins and safe SPI rate for this board only.
7. UART TX/RX GPIO assignment for the external GPS connector.
8. Camera, audio, sensor, USB, and expansion-header pin ownership and conflicts.
9. Whether camera and non-camera SKUs use one electrically identical base PCB.

The related Waveshare ESP32-S3-Touch-LCD-3.5 repository may be useful for controller-driver patterns,[3] but no S3 GPIO assignment may be transferred to this ESP32-C5 board without C5-specific evidence.

## Planned CYM architecture

- Add a distinct Kconfig/build target: `ws-c5-35`.
- Add a dedicated board profile under `board_hal`; do not alias `ws-c5-28`.
- Keep all shared features in the canonical application source.
- Isolate ST7796, FT6336, AXP2101, CH32V006, pin-map, backlight, SD, GPS, audio, camera, and battery behavior behind board capabilities/backends.
- Treat the UART header as this board's GPS connector once its GPIO map is verified.
- Preserve Classic and Modern as separate navigation/layout contracts at 320×480.
- Add packaging, a manifest, documentation, and a web-flasher selector only after build and physical acceptance gates pass.
- Preserve behavior and build success for NM-CYD-C5, WS-C5-28, Classic CYD, and Hosyond ES3C35P.

The executable implementation sequence and acceptance gates are captured in [`docs/superpowers/plans/2026-09-27-waveshare-c5-touch-lcd-35-support.md`](../superpowers/plans/2026-09-27-waveshare-c5-touch-lcd-35-support.md).

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
