# Waveshare ESP32-C5-Touch-LCD-3.5 — Supported display/touch/RTC profile

Vendor Wiki: [Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35)](https://www.waveshare.com/wiki/ESP32-C5-Touch-LCD-3.5).

Owner-tested display/touch, battery acquisition, RTC synchronization/reboot holdover, and GPS LOCK using the WS-C5-35-only GPIO28 receive route. Battery percentage accuracy and additional peripherals remain unqualified.

CYM support for the **Waveshare ESP32-C5-Touch-LCD-3.5** exists as a dedicated board target (`ws-c5-35`). A dedicated binary and web-flasher entry are available in the normal board selector; select Stable for v3.0.0. This build must not be flashed with the existing WS-C5-28 image — and vice versa.

Jim's ordered unit is **SKU 35419 / ESP32-C5-Touch-LCD-3.5-C**, the version supplied with the BF3901 camera and a 3.7 V lithium battery.[1] The unit has arrived and Jim has completed the display/touch and RTC tests described above.

## Vendor BSP reference

The board adapter was implemented from the [Waveshare ESP32-C5-Touch-LCD-3.5](https://github.com/waveshareteam/ESP32-C5-Touch-LCD-3.5) vendor BSP at commit `04e6134cf3e37309b2bec9915189efeace1161bc`. Pin definitions, CH32V006 IO expander protocol, ST7796 display initialization, and FT6336 touch driver were derived from that BSP.


## Important: native routing limitations on the tested assembly

**Owner continuity-tested finding, 2026-10-13:** on Jim's **SKU 35419 / ESP32-C5-Touch-LCD-3.5-C** unit, **GPIO0, GPIO1, GPIO11, GPIO12, GPIO9 and GPIO4 do not connect to the rear J3 expansion connector**. The fitted zero-ohm selection links route these signals to onboard components instead. This supersedes earlier assumptions that the printed GPIO/UART labels guaranteed usable native ESP32 pins at J3.

This is an owner-reported measured finding for the tested assembly, not a claim that every SKU, PCB revision or resistor population is identical. Jim found no noticeable PCB revision marking beyond the generic model identifier; the exact PCB revision remains unknown. The supplied SKU included the camera and battery. Battery installation required disassembly, and the installed battery was secured with double-sided tape; this is an assembly observation, not a recommendation to dismantle a powered device.

**Reported continuity method:** continuity/beep mode, probing the J3 header contact and the unconnected pad on the zero-ohm selection matrix, with the battery disconnected and no USB connection or other power. Meter make/model, resistance values, beep threshold and a numbered endpoint log were not supplied. Do not invent them or treat photographs as electrical proof. Other owners should check their own board's link population and continuity, with power and the battery disconnected, before wiring external hardware.

| ESP32 GPIO | Selection link | Onboard net selected on the tested unit | Alternative net shown by schematic, not a qualified J3 connection |
|---|---|---|---|
| GPIO0 | R55 | CAM_D0 | GPIO0_OUT |
| GPIO1 | R58 | CAM_D1 | GPIO1_OUT |
| GPIO11 | R56 | CAM_PCLK | U0TXD |
| GPIO12 | R59 | CAM_VSYNC2 | U0RXD |
| GPIO9 | R57 | SDCS | GPIO9_OUT |
| GPIO4 | R60 | EXIO_INT | LCD_QSPI_IO3 |

The resistor IDs and alternative net names come from the pinned vendor schematic; physical route selection is established by Jim's continuity test, not by the schematic's colors or the photograph alone. In particular, R60's LCD_QSPI_IO3 alternative must not be advertised as a verified spare GPIO at J3. More precisely, the manufacturer J3 symbol identifies five corresponding native-labelled header positions (GPIO0_OUT, GPIO1_OUT, GPIO9_OUT, U0TXD and U0RXD); GPIO4/R60 is an additional examined onboard selection route, not a sixth numbered spare native GPIO on that symbol. The observation that GPIO4 is not available at J3 does not establish an unlisted header contact.

![Owner's PCB photograph of the selection-link area](https://raw.githubusercontent.com/wiki/JimGat/CYM/images/ws-c5-35-j3-routing-20261013.jpg)

The photograph records the assembly's selection-link area. The image alone does not establish continuity or readable resistor IDs. Public image metadata has been stripped.

### GPS consequence

CYM v2.15.98 includes a receive-only GPS qualification path on UART1/RX GPIO12 at the selected baud (default 9600), with primary USB-C Serial/JTAG logging kept separate. Jim's hardware test still received no GPS data. The missing native J3 route means that software UART selection, GPIO-matrix routing or baud changes cannot connect the module through that header on this assembly. `U0TX`/`U0RX` names do not require use of UART0; the physical connection is the blocker here.

**The GPIO11/12 UART-labelled J3 route does not work on this assembly. The GPIO28 receive-only exception below now has owner-reported GPS LOCK.** An external UART-to-I2C bridge is not required for that confirmed setup. A 3.3V-compatible buffered bridge remains only an unimplemented alternative; no bridge model, wiring or CYM driver has been qualified.

The CH32V006's EXIO pins can provide digital input snapshots, but its documented stock I2C protocol does not provide buffered UART reception. Repeated input-register polling is not a supported reliable 9600-baud GPS transport. Jim reports Waveshare declined to share the onboard helper firmware source, so replacing that firmware is not an available supported recovery path. No resistor relocation, helper reflashing or PCB modification is recommended by this documentation.

### Board-specific GPS exception: GPIO28 receive-only, GPS LOCK confirmed

Since v2.15.99, **only WS-C5-35** uses **UART1 RX=GPIO28, TX=disabled**, with no alternate GPS-pin or EXIO polling. Connect **GPS TX to GPIO28**, connect common **GND**, and select **9600 baud** for the owner-tested **ATGM336H** module. Saved baud selection is retained; 9600 is the default. No GPS configuration commands are transmitted, and GPIO11/12 are not configured for this route.

**Owner hardware result:** after several successful reboots with the GPS attached, Jim reports that his WS-C5-35 **displays GPS LOCK** on v2.15.99. This is owner-observed lock evidence, not merely compilation or successful booting. It qualifies the tested SKU 35419 assembly/module setup; it is not a blanket qualification of all PCB revisions, modules, GPS accuracy, or long-duration stability. Independent raw-UART/NMEA logs were not supplied with this report. GPIO28 is not one of the six disconnected routes above.

GPIO28 also serves as a physical BOOT strapping pin. WS-C5-35 firmware BOOT polling is disabled to prevent serial data from triggering button-associated actions. Physical BOOT/download strapping is unchanged. Touch controls and the five-second screen-hold Go Dark wake remain available. Avoid pressing physical BOOT against an actively connected GPS transmitter. Other boards retain their BOOT and GPS mappings; do not apply this exception to them.

See [the v2.15.99 operator procedure](../operator-cycle-v2.15.99.md) for primary-USB diagnostics and separate reception/fix gates. The previous GPIO12 failure remains historical evidence, not a GPIO28 result.

## Future hardware mod: external antenna and printed rear plate

**IDEA — requested by Jim; not designed or hardware-qualified.** The specimen photos show the ESP32-C5-WROOM-1U module connected by miniature coax to the supplied flexible antenna. [Waveshare's onboard-resource description](https://docs.waveshare.com/ESP32-C5-Touch-LCD-3.5#onboard-resources) identifies an **IPEX Gen 1 antenna connector** and an **FPC dual-band Wi-Fi antenna**. This is the ESP32 radio antenna, not the external ATGM336H GPS antenna.

Explore a 3D-printed back plate with a strain-relieved external-antenna pigtail/bulkhead arrangement replacing or relocating the existing antenna connection. Confirm the exact mating connector and cable, 50-ohm RF path, suitable 2.4/5-GHz coverage, antenna gain/regulatory limits, battery/camera/SD/button clearance, minimum cable bend radius and mechanical protection before selecting parts. Preserve a stock configuration for comparison and qualify actual RF performance; no range improvement is claimed. Do not imply both antennas can be used simultaneously. No CAD, external-antenna parts list or physical modification has been completed. Track this in [BACKLOG.md](../../BACKLOG.md).

## Implementation status

- **Display:** ST7796 320x480 SPI, BGR element order, color-invert, mirror(true, false) - from vendor BSP
- **Touch:** FT6336 capacitive via dedicated `esp_lcd_touch_ft6336` local component (not the Pancake driver)
- **IO expander:** CH32V006 16-bit little-endian I2C protocol (registers 0x02/0x03/0x05) - distinct from WS-C5-28's CH32V003
- **Backlight:** PWM via CH32V006 IO expander register 0x05
- **PMIC:** AXP2101 at I2C 0x34, checked battery-voltage telemetry with measurement enable only; no rail/charging programming
- **GPS:** owner-reported GPS LOCK on v2.15.99 using WS-C5-35-only UART1 RX=GPIO28/TX=disabled at 9600 baud (`BOARD_HAS_GPS=1`, `BOARD_TIME_HAS_GPS_UART=1`). GPIO11/12 J3 routes remain disconnected on the tested assembly. No external bridge is needed for the confirmed GPIO28 setup; bridge support is not implemented.
- **Audio:** disabled (`BOARD_HAS_AUDIO=0`)
- **Battery acquisition:** AXP2101 VBAT enabled; percentage remains voltage-estimated
- **RGB LED:** disabled (`BOARD_HAS_RGB_LED=0`)
- **RTC:** PCF85063 enabled; NTP synchronization and reboot holdover tested

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
| Expansion | 32-pin 2.54 mm female header with GPIO/UART/I2C labels | Six native GPIO routes are not connected to J3 on the continuity-tested assembly; labels are not proof of usable connections |
| Controls | RESET, BOOT, and programmable PWR buttons | Board-specific button and PMIC behavior |

A 320×480 RGB565 full-screen image is 307,200 bytes. The panel has twice the pixels of a 240×320 display, so CYM should retain partial DMA-capable LVGL draw buffers rather than require two full-screen buffers.

## Visible expansion-header labels

Waveshare's order-page board label shows these external signal names:[1]

- `5V`, `G`, `SWD`, several `NC` positions
- ESP-side labels `0`, `1`, `9`, `28`, and `ADC`
- `SCL`, `SDA`, `TX`, `RX`
- `BAT`, `RST`, `PWR`, `3V3`, and ground
- helper-controller labels `E8` through `E15`

These are printed signal labels, not proof of electrical availability. The continuity-tested routing warning above supersedes the earlier assumption that TX/RX labels guaranteed an external GPS connection. Check the exact assembly before using any native-GPIO header position.

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
2. GPS qualification beyond the owner-observed GPIO28 lock: other board revisions/modules, raw-NMEA log capture, sustained reception and long-duration stability. The GPIO11/12 J3 route remains unavailable; the optional I2C/UART bridge is unimplemented.
3. Camera, audio, sensor, USB, and expansion-header pin ownership and conflicts.
4. Whether camera and non-camera SKUs use one electrically identical base PCB.

## CYM architecture (implemented)

- Distinct Kconfig/build target: `CONFIG_BOARD_WS_C5_35` in `ESP32C5/components/board_hal/Kconfig`.
- Dedicated board profile: `ESP32C5/components/board_hal/include/boards/ws_c5_35.h`.
- Dedicated board adapter: `ESP32C5/main/ws_c5_35_port.c` (display, touch, backlight, IO expander).
- Local FT6336 component: `ESP32C5/components/esp_lcd_touch_ft6336/`.
- Local IDF-6-compatible copy of `espressif/esp_lcd_st7796 1.0.0`, retaining its Apache-2.0 license and vendor initialization table.
- Packaging: `ESP32C5/binaries-ws-c5-35/`, manifest `ESP32C5/docs/manifest.ws-c5-35.json`.
- Web flasher: WS-C5-35 is visible in the normal board selector; v3.0.0 is available in the Stable channel.
- Build: `make ws-c5-35` or `scripts/build.sh ws-c5-35`.

## Hardware acceptance checklist

Support is not complete until Jim's SKU 35419 unit passes:

- exact SKU/PCB-revision record and cold-boot baseline
- USB flashing, reset, BOOT, and PWR behavior
- display initialization, colors, clipping, full-screen clears, all four orientations, and bounded redraw timing
- FT6336 touch accuracy and all four orientation transforms
- Classic and Modern navigation, including representative full-screen feature views
- TF-card mount, read, write, remount, and capture-file persistence
- external GPS: owner-reported GPIO28 GPS LOCK is confirmed; extended reception/accuracy/soak qualification and other assemblies remain pending
- 2.4 GHz and 5 GHz Wi-Fi, BLE, IEEE 802.15.4, and ESP-NOW behavior
- AXP2101 battery telemetry, charging, backlight, shutdown, and USB/battery transitions
- RTC, IMU, temperature/humidity, audio, and camera conflict checks before enabling each capability
- repeated reboot/power-cycle and bounded soak with heap, DMA, task, and LVGL timing observations

Compilation alone is never physical qualification.

## Sources

[1] https://www.waveshare.com/esp32-c5-touch-lcd-3.5.htm?sku=35419
[2] https://docs.waveshare.com/ESP32-C5-Touch-LCD-3.5
[3] https://docs.espressif.com/projects/esp-idf/en/stable/esp32c5/api-reference/peripherals/gpio.html
[4] https://docs.espressif.com/projects/esptool/en/latest/esp32c5/advanced-topics/boot-mode-selection.html
