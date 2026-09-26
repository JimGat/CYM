# ES3C35P Shared CYM Promotion Design

**Date:** 2026-09-25
**Status:** Approved
**Target:** Hosyond/LCDWiki ES3C35P 3.5-inch ESP32-S3 board

## Purpose

Promote the physically qualified ES3C35P display/touch target from a standalone bring-up image to a fully supported CYM release board that runs the canonical current application. The board must participate in the same version, build, packaging, manifest, documentation, and web-flasher lifecycle as the three existing release boards without introducing a separate S3 application fork or changing proven behavior on those boards.

Only the 3.5-inch ES3C35P is promoted. The Hosyond 2.8-inch and 4.0-inch targets remain experimental and outside normal release gates until independently qualified.

## Architectural Decision

`ESP32C5/main/` remains the sole canonical CYM application source tree. `ESP32S3/main/CMakeLists.txt` will follow the established `ESP32/main/CMakeLists.txt` reuse pattern and compile those canonical sources directly. The existing diagnostic `ESP32S3/main/main.c` will stop being the application entry point.

There will be no S3-specific copy of CYM features. WiFi, BLE, scans, attacks, storage workflows, screens, settings, file formats, tasks, and PSRAM-backed features remain shared code. Board uniqueness is expressed through:

1. board-profile constants in `board_hal`;
2. compile-time capability flags; and
3. thin hardware adapters selected only for controllers or buses that physically differ.

If a future feature appears to require a large ES3C35P implementation, the correct change is to create or extend a shared interface and keep only the hardware operation board-specific. A parallel feature implementation or copied application path is not acceptable.

## Board-Specific Hardware Boundary

The ES3C35P-specific low-level boundary is limited to:

- ST77922 QSPI panel creation and transport at 40 MHz;
- the physically qualified 63-entry 320x480 initialization sequence;
- four-pixel horizontal draw rounding;
- interrupt-to-task flush completion;
- integrated capacitive touch reads at I2C address `0x55`;
- direct GPIO41 backlight control;
- SPI3 SD configuration;
- GPIO40 WS2812 transport; and
- GPIO8 battery ADC conversion; and
- external GPS through the board's four-pin UART connector.

These adapters expose the behavior expected by shared CYM code. They do not own screens, menus, feature state, storage formats, network behavior, or alternate application task flows.

The qualified display/touch contract remains:

- 320x480 native portrait;
- ST77922 QSPI, 40 MHz panel bus;
- 63-entry ES3C35P factory initialization;
- CASET end `0x013f`, RASET end `0x01df`;
- four-pixel X alignment;
- no X or Y mirroring, MADCTL `0x00`;
- RGB element order with big-endian RGB565 transport and inversion enabled;
- touch SDA38, SCL39, RST48, INT47, address `0x55`; and
- panel reset tied to EN/CHIP_PU, requiring complete USB-C power removal when replacing panel firmware state.

Flash and OPI PSRAM remain at 80 MHz. The display's internal-SRAM DMA buffer rule remains unchanged.

## Capability Contract

Enabled on ES3C35P:

- 8 MB OPI PSRAM;
- dual-core ESP32-S3 execution;
- 2.4 GHz WiFi;
- Bluetooth LE;
- QSPI LCD;
- I2C capacitive touch;
- SD storage;
- one WS2812-compatible RGB LED; and
- battery voltage ADC; and
- external GPS support through the UART connector.

Disabled because the hardware is absent or intentionally deferred:

- 5 GHz WiFi;
- IEEE 802.15.4;
- audio codec/speaker features;
- vibrator;
- RF-HAT; and
- ES3C35P expansion-interface features other than the dedicated UART GPS connection.

Unavailable C5-only APIs and menus must be excluded by capability or target guards. The S3 binary must contain no callable 5 GHz or IEEE 802.15.4 execution path.

## Peripheral Behavior

### SD

SD uses SPI3 with CS3, SCK5, MOSI4, MISO6 at 20 MHz. Successful mount feeds the existing shared CYM storage workflows. Mount failure uses the existing SD error handling and must not crash or block the rest of CYM.

### RGB LED

The shared LED behavior uses a narrow GPIO40 WS2812 adapter. Driver initialization failure is logged and treated as nonfatal.

### Battery ADC

The existing hard-disabled, hardcoded battery path will be converted to use board capability/profile values. ES3C35P uses GPIO8 / ESP32-S3 ADC1 channel 7, calibrated one-shot ADC sampling, an averaged reading, and the schematic's 100 kOhm / 100 kOhm divider ratio. The result feeds the existing shared top-bar voltage display.

ADC initialization or calibration failure hides the voltage and logs the error. Firmware must not display an invented or uncalibrated value as trustworthy battery data.

### UART GPS

The board's four-pin P2 UART connector is a supported optional GPS connection with this board-specific map:

- P2 pin 1: 3.3 V;
- P2 pin 2: GND;
- P2 pin 3: board TXD0, ESP32-S3 GPIO43, connected to GPS RX; and
- P2 pin 4: board RXD0, ESP32-S3 GPIO44, connected to GPS TX.

CYM will use `UART_NUM_1` through the ESP32-S3 GPIO matrix with MCU TX on GPIO43 and MCU RX on GPIO44, matching the shared GPS driver's TX/RX convention. The existing board profile's reversed GPIO43/GPIO44 UART definitions must be corrected. Application logging will use native USB Serial/JTAG only so UART0 console traffic does not contend with the GPS connector. ROM download behavior remains available before application startup. With no GPS attached, CYM retains its existing no-module behavior and hides GPS status rather than treating absence as an error.

The same shared-feature/board-pin-map rule applies to WS-C5-28. Its existing board profile and schematic define its UART connector as MCU TX on GPIO11 and MCU RX on GPIO12. WS-C5-28 continues to use the canonical GPS implementation with that board-specific map; it must not receive a separate GPS feature implementation.

### PSRAM

Shared PSRAM-gated features may use the board's 8 MB OPI PSRAM at 80 MHz. Large allocations must retain feature-level fail-closed behavior and must not silently consume internal DMA memory. LCD DMA buffers stay in internal SRAM.

## Version and Release-Board Policy

ES3C35P becomes the fourth supported release board. The promotion cycle version is `v2.15.27` for:

- NM-CYD-C5;
- WS-C5-28;
- CYD-2432S028; and
- Hosyond ES3C35P.

`ESP32S3/CMakeLists.txt` joins the synchronized release-cycle version contract. All four board manifests must report the same source and packaged version. The 2.8-inch and 4.0-inch S3 targets retain experimental status and do not inherit the release version/build requirement.

## Build and Packaging Rules

`make all-boards` becomes the four-release-board gate. Shared application or shared-component changes must build all four release boards successfully before push. A board-isolated change may use an affected-board build only when the dependency boundary proves that other release binaries cannot change.

The ES3C35P package contains:

- `ESP32S3/binaries-hosyond-s3-35/CYM-hosyond-s3-35.bin`;
- `bootloader.bin`;
- `partition-table.bin`; and
- `CYM-hosyond-s3-35-full.bin`, flashed at offset `0x0000`.

A board manifest will identify `ESP32-S3`, use the correct ESP32-S3 offsets, and reference the board-specific package. Each packaged application must be checked independently for `v2.15.27`; source `PROJECT_VER` alone is not artifact proof.

## Web Flasher

The shared flasher at `ESP32C5/docs/index.html` will receive a complete `hosyond-s3-35` board definition, not merely a downloadable binary. The definition will use:

- label `Hosyond ES3C35P 3.5`;
- chip family `ESP32-S3`;
- source directory `ESP32S3`;
- binary directory `binaries-hosyond-s3-35`;
- application binary `CYM-hosyond-s3-35.bin`;
- manifest `docs/manifest.hosyond-s3-35.json`;
- bootloader offset `0x0000`; and
- `beta: false`.

`hosyond-s3-35` will be added to `DEFAULT_BOARD_IDS`, making it a normal visible selector alongside the other supported boards. The page version will be incremented. Existing ESP32-S3 chip-family normalization and mismatch refusal will prevent flashing this image to a non-S3 chip. The direct-download area will expose the application, bootloader, partition table, full merged image, and manifest from the selected Stable or Dev branch.

`ESP32S3/docs/manifest.hosyond-s3-35.json` will declare the three-part ESP32-S3 flash layout: bootloader at `0x0000`, partition table at `0x8000`, and application at `0x10000`. Its version/build must match the other three release manifests.

`.github/workflows/deploy-flasher.yml` will watch the ES3C35P manifest, binary directory, and shared flasher source. Its site-build step will stage all four supported manifests and all four board binary directories, including `_site/manifest.hosyond-s3-35.json` and `_site/binaries-hosyond-s3-35/`. A static verification step will fail if the selector, manifest, required binaries, chip family, or offsets are missing from the generated Pages artifact.

This development request authorizes work on `Jimgat_Dev`, not a merge or release to `main`. The source, development manifest, selector, workflow, and binaries will be pushed to `Jimgat_Dev`. The stable Pages deployment receives the new selector and stable artifacts only through a separately authorized release merge.

## Failure Handling

- Display/touch initialization failures produce explicit logs and must not be misreported as successful initialization.
- SD failure is nonfatal and routes through shared SD error handling.
- RGB initialization failure is nonfatal and disables LED behavior.
- Battery ADC/calibration failure hides battery output.
- GPS UART initialization or module-detection failure is nonfatal and preserves the shared no-module behavior.
- Missing PSRAM or failed large allocations must fail closed at the affected feature, never corrupt memory or force large buffers into DMA-constrained internal RAM.
- C5-only features are absent at compile time rather than allowed to fail at runtime.

## Verification

Implementation follows test-first contract development:

1. Add contract tests and run them before implementation to prove they fail for the missing promotion behavior.
2. Verify S3 compiles canonical sources and no longer compiles its diagnostic application.
3. Verify C5-only APIs are enclosed by capability or target guards.
4. Verify the ES3C35P profile and capability values.
5. Verify all four release boards are in the normal build gate and the two unqualified S3 targets are not.
6. Verify the ES3C35P manifest and non-beta flasher selector.
7. Build all four release boards in isolated build directories.
8. Independently inspect each packaged application and manifest for `v2.15.27`.
9. Validate manifest paths, offsets, chip families, merged images, and SHA-256 values.
10. Generate and inspect the Pages artifact layout.
11. Inspect the final diff for unintended changes to the three proven board paths.
12. Push only after the four-board gate passes, then fetch exact raw GitHub files and binaries to verify publication.

## Physical Acceptance

The development image will be delivered with its raw GitHub URL, SHA-256, and flash offset `0x0000`. Physical acceptance requires:

- flash followed by complete USB-C power removal and reconnection;
- normal CYM home screen and correct touch;
- PSRAM detection;
- 2.4 GHz WiFi and BLE operation;
- SD mount/read/write;
- RGB LED behavior;
- plausible battery voltage;
- optional UART GPS detection and NMEA reception using GPIO43/GPIO44 when a module is connected;
- normal operation with the GPS connector empty;
- 5 GHz, IEEE 802.15.4, audio, and RF-HAT absent; and
- no panic or reboot during a bounded soak.

If SD, RGB, or battery fails physical testing, only its adapter/profile is corrected unless evidence proves a shared defect. Build success alone is not hardware qualification.

## Non-Goals

- Promoting the Hosyond 2.8-inch or 4.0-inch boards.
- Adding audio support.
- Adding RF-HAT support.
- Adding GPS through any connection other than each board's dedicated UART connector.
- Implementing 5 GHz or IEEE 802.15.4 on ESP32-S3.
- Refactoring the entire application into a new top-level component.
- Copying the canonical application into an S3-specific fork.
- Merging to `main`, tagging, publishing a release, or flashing hardware from the development host.
