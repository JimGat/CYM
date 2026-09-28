# Waveshare ESP32-C5-Touch-LCD-3.5 Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Jim's Waveshare ESP32-C5-Touch-LCD-3.5-C (SKU 35419) as a physically qualified, independently packaged CYM board target without changing the behavior of existing release boards.

**Architecture:** Retain `ESP32C5/main/` as the canonical application and introduce a dedicated `ws-c5-35` board profile. ST7796 display, FT6336 touch, AXP2101 power, CH32V006 helper-controller, SD, GPS, camera, audio, sensors, and pin ownership remain board-scoped behind `board_hal` capabilities. Packaging and the web flasher are added only after physical qualification.

**Tech Stack:** C/CMake, ESP-IDF, LVGL 8, Espressif LCD/I2C/SPI/UART/ADC APIs, Python 3 contract tests, GNU Make, Bash packaging, ESP Web Tools, GitHub Actions.

## Global Constraints

- Execute all source edits, tests, builds, packaging, commits, and pushes on ESP32-Dev as `dev`; JARVIS remains an orchestration console.
- Work on `Jimgat_Dev`; do not merge or push `main`, create a tag, publish a release, or trigger a production web-flasher release without explicit release authorization.
- Preserve unrelated `.hermes/`, `docs/feedback/`, `docs/prompts/`, caches, and concurrent work; never reset, clean, stash, overwrite, or stage them.
- Use a dedicated `ws-c5-35` target. Never alias it to `ws-c5-28` or transfer WS-C5-28/S3 pin assignments by resemblance.
- Source GPIOs, addresses, initialization, and helper-controller protocol from the exact C5 schematic/BSP and reconcile them against SKU 35419 hardware.
- Keep UART GPS enabled through this board's exposed TX/RX header using a board-specific verified pin map.
- Keep camera, audio, battery, sensors, and other optional functions capability-gated until individually verified.
- Preserve Classic and Modern as separate navigation/layout contracts.
- Keep display/touch/power/peripheral changes board-specific; shared feature changes require all affected release boards to build green.
- Follow the canonical shared-cycle patch-version rule; do not increment minor or major versions automatically.
- Never add AI attribution trailers or comments to commits. Preserve legitimate human co-developer credit.
- Compilation is not hardware qualification. Do not describe the board as supported or add it to the public flasher until the physical acceptance gate passes.

---

### Task 1: Freeze exact hardware evidence when SKU 35419 arrives

**Files:**
- Modify: `docs/hardware/waveshare-c5-touch-lcd-35.md`
- Create: `docs/hardware/waveshare-c5-35/README.md`
- Add under: `docs/hardware/waveshare-c5-35/` only the authoritative schematic, pin table, initialization data, and license-permitted vendor references needed for maintenance

**Interfaces:**
- Produces a cited board-evidence record consumed by every later task.
- Produces no GPIO constants or firmware behavior until the evidence gate passes.

- [ ] **Step 1: Record the received hardware identity**

Photograph both PCB faces and record the order SKU, printed part number, PCB revision, fitted camera, battery connector, antenna arrangement, and any assembly/revision markings in `docs/hardware/waveshare-c5-35/README.md`.

- [ ] **Step 2: Acquire the C5-specific vendor resources**

Download the schematic and C5 ESP-IDF/Arduino examples from Waveshare's official resource page. Record each source URL, retrieval date, upstream filename, and SHA-256 in the hardware README.

- [ ] **Step 3: Build a conflict-free ownership table**

List every ESP32-C5 GPIO, CH32V006 expander channel, AXP2101 rail, I2C address, SPI host/device, UART, camera signal, and external-header signal. Explicitly identify shared pins and functions unavailable when the BF3901 camera is fitted.

- [ ] **Step 4: Verify the evidence gate**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('docs/hardware/waveshare-c5-35/README.md')
s = p.read_text()
required = ['SKU 35419', 'PCB revision', 'SHA-256', 'ST7796', 'FT6336',
            'AXP2101', 'CH32V006', 'UART GPS', 'TF card', 'BF3901']
missing = [item for item in required if item not in s]
assert not missing, missing
print('WS-C5-35 evidence record: complete')
PY
git diff --check
```

Expected: the evidence record names the exact board and every required subsystem; no source pin constant has been introduced without a citation.

- [ ] **Step 5: Commit the evidence record**

```bash
git add docs/hardware/waveshare-c5-touch-lcd-35.md docs/hardware/waveshare-c5-35/
git commit -m "docs(hardware): capture WS-C5-35 bring-up evidence"
```

---

### Task 2: Add failing contracts for a fifth board target

**Files:**
- Create: `tests/test_ws_c5_35_support_contract.py`
- Modify: none

**Interfaces:**
- Consumes tracked build, board-HAL, packaging, flasher, and documentation files.
- Produces deterministic gates for board identity, isolation, capabilities, build entry points, packaging, and public-support wording.

- [ ] **Step 1: Write the initial RED contract**

Create a `unittest` suite with repository-root-relative helpers and these assertions:

```python
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

class WaveshareC535Contract(unittest.TestCase):
    def test_board_is_distinct(self):
        profile = text('ESP32C5/components/board_hal/include/boards/ws_c5_35.h')
        self.assertIn('BOARD_NAME', profile)
        self.assertIn('Waveshare ESP32-C5-Touch-LCD-3.5', profile)
        self.assertNotEqual(profile, text('ESP32C5/components/board_hal/include/boards/ws_c5_28.h'))

    def test_selection_and_build_target_exist(self):
        self.assertIn('config BOARD_WS_C5_35', text('ESP32C5/components/board_hal/Kconfig'))
        self.assertIn('CONFIG_BOARD_WS_C5_35', text('ESP32C5/components/board_hal/include/board_hal.h'))
        self.assertIn('ws-c5-35:', text('Makefile'))
        self.assertIn('ws-c5-35)', text('scripts/build.sh'))

    def test_required_capabilities_are_declared(self):
        profile = text('ESP32C5/components/board_hal/include/boards/ws_c5_35.h')
        for token in ('BOARD_HAS_GPS', 'BOARD_GPS_TX', 'BOARD_GPS_RX',
                      'BOARD_HAS_SD', 'BOARD_LCD_H_RES', 'BOARD_LCD_V_RES'):
            self.assertIn(token, profile)
        self.assertIn('320', profile)
        self.assertIn('480', profile)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the focused suite and verify RED**

Run: `python3 -m unittest -v tests.test_ws_c5_35_support_contract`

Expected: file-not-found failures for the new board profile and failures for missing Kconfig/build target entries.

- [ ] **Step 3: Commit only the RED contract**

```bash
git add tests/test_ws_c5_35_support_contract.py
git commit -m "test(board): define WS-C5-35 support contracts"
```

---

### Task 3: Introduce board selection and the evidence-backed pin profile

**Files:**
- Create: `ESP32C5/components/board_hal/include/boards/ws_c5_35.h`
- Modify: `ESP32C5/components/board_hal/include/board_hal.h`
- Modify: `ESP32C5/components/board_hal/Kconfig`
- Create: `ESP32C5/sdkconfig.defaults.ws-c5-35`
- Modify: `Makefile`
- Modify: `scripts/build.sh`
- Test: `tests/test_ws_c5_35_support_contract.py`

**Interfaces:**
- Produces `CONFIG_BOARD_WS_C5_35` and normalized `BOARD_*` capabilities.
- Consumes only constants established in Task 1's C5 ownership table.

- [ ] **Step 1: Extend the contract with every verified constant**

For each evidence-backed LCD, touch, SD, UART/GPS, I2C, button, battery, audio, camera, and helper-controller value, add an exact assertion to `test_ws_c5_35_support_contract.py`. Add negative assertions proving WS-C5-28's CH32V003-specific driver and pin map are not selected.

- [ ] **Step 2: Run the suite and verify RED on the new constants**

Run: `python3 -m unittest -v tests.test_ws_c5_35_support_contract`

Expected: the selection test may begin passing while exact profile and capability assertions remain red.

- [ ] **Step 3: Implement the minimum board profile and build plumbing**

Add `BOARD_WS_C5_35` to Kconfig and dispatch it in `board_hal.h`. Add `ws-c5-35` to `scripts/build.sh` using its own sdkconfig defaults and build directory. Add a Make target, but do not add it to the release `all-boards` gate yet.

The profile must define 320×480 geometry, verified UART GPS pins, SD presence, PSRAM, 5 GHz, BLE, and IEEE 802.15.4. Camera/audio/sensor/battery capabilities remain false until their task passes hardware acceptance.

- [ ] **Step 4: Verify the configuration boundary**

Run:

```bash
python3 -m unittest -v tests.test_ws_c5_35_support_contract
git diff --check
git diff -- ESP32C5/components/board_hal ESP32C5/sdkconfig.defaults.ws-c5-35 Makefile scripts/build.sh tests/test_ws_c5_35_support_contract.py
```

Expected: the focused contract passes and the diff contains no change to existing board pin values.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ws_c5_35_support_contract.py ESP32C5/components/board_hal ESP32C5/sdkconfig.defaults.ws-c5-35 Makefile scripts/build.sh
git commit -m "feat(board): add WS-C5-35 target profile"
```

---

### Task 4: Integrate ST7796 display and 320×480 LVGL transport

**Files:**
- Create or add a managed component for the evidence-matched ST7796 panel driver under `ESP32C5/components/`
- Modify: `ESP32C5/main/main.c` only at the existing board-dispatch/geometry boundaries
- Modify: `ESP32C5/main/CMakeLists.txt`
- Modify: `tests/test_ws_c5_35_support_contract.py`

**Interfaces:**
- Produces an `esp_lcd_panel_handle_t` compatible with the existing CYM LVGL flush path.
- Uses board-scoped SPI rate, reset/backlight ownership, inversion, color order, offsets, and initialization table.

- [ ] **Step 1: Add source contracts for the verified ST7796 invariants**

Assert the exact initialization-table identity or hash, native 320×480 geometry, SPI clock, color order, inversion mode, rotation transform, offsets, and reset/backlight owner from Task 1.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.test_ws_c5_35_support_contract`

- [ ] **Step 3: Implement the minimum board-scoped panel backend**

Use partial DMA-capable LVGL draw buffers. Do not allocate two 307,200-byte full-screen RGB565 buffers. Keep all WS-C5-28 ST7789 behavior unchanged and isolate ST7796 initialization behind `CONFIG_BOARD_WS_C5_35` or a driver selected by the board profile.

- [ ] **Step 4: Build WS-C5-35 and existing ESP32-C5 boards**

Run:

```bash
. /home/dev/esp/esp-idf/export.sh
make ws-c5-35
make nm-cyd-c5
make ws-c5-28
```

Expected: all three builds exit zero; this proves compilation only, not display correctness.

- [ ] **Step 5: Physically qualify the display**

On SKU 35419, test cold boot, full-screen solid colors, clipping boundaries, bitmap color fidelity, all four rotations, repeated screen transitions, and redraw timing. Capture serial evidence and record the qualified SPI rate and LVGL timing in the hardware README.

- [ ] **Step 6: Commit after physical display acceptance**

Stage only the ST7796 component, board-scoped `main.c`/CMake changes, tests, and updated evidence record.

---

### Task 5: Integrate FT6336 touch and both navigation contracts

**Files:**
- Create or add a managed FT6336 component under `ESP32C5/components/`
- Modify: `ESP32C5/main/main.c` at the existing touch-dispatch boundary
- Modify: `tests/test_ws_c5_35_support_contract.py`
- Modify: `docs/hardware/waveshare-c5-touch-lcd-35.md`

**Interfaces:**
- Produces LVGL pointer input in display coordinates.
- Consumes verified FT6336 address, reset, interrupt, native coordinate range, and per-rotation transform.

- [ ] **Step 1: Add RED contracts for address and transforms**

Assert the C5-specific FT6336 address/reset/interrupt values and four explicit coordinate transforms derived from physical corner tests.

- [ ] **Step 2: Implement the board-scoped touch backend**

Initialize FT6336 over the verified I2C bus, preserve interrupt/reset ownership, and feed the existing LVGL input device. Do not alter CST3530 or XPT2046 paths.

- [ ] **Step 3: Build the affected boards**

Run the focused contract followed by `make ws-c5-35`, `make nm-cyd-c5`, and `make ws-c5-28`.

- [ ] **Step 4: Physically qualify touch and layouts**

Exercise corners, edges, press/release, repeated gestures, and all rotations. Inspect both Classic and Modern home/navigation contracts and representative full-screen feature views at 320×480. Record any screen-specific geometry fixes as shared resolution-aware behavior unless the issue is truly panel-specific.

- [ ] **Step 5: Commit only after the touch and layout evidence is recorded**

---

### Task 6: Integrate CH32V006 and AXP2101 board control

**Files:**
- Create board-scoped CH32V006 and AXP2101 components or adapters under `ESP32C5/components/`
- Modify: `ESP32C5/main/main.c` only through board-control interfaces
- Modify: `ESP32C5/components/board_hal/`
- Modify: `tests/test_ws_c5_35_support_contract.py`

**Interfaces:**
- Produces safe reset, backlight, power-rail, battery, PWR-button, charge-state, and shutdown operations.
- Does not reuse CH32V003 commands unless the C5 vendor protocol proves byte-for-byte compatibility.

- [ ] **Step 1: Write protocol/rail contracts from vendor source**

Assert exact I2C addresses, register/command values, rail enable order, safe defaults, and error behavior. Add a negative contract preventing the existing `custom_io_expander_ch32v003` component from being selected for WS-C5-35 without documented compatibility.

- [ ] **Step 2: Implement fail-safe initialization**

If helper-controller or PMIC communication fails, preserve USB-powered operation where electrically safe, prevent uncontrolled rail toggles, log the exact failure, and keep unsupported capability flags disabled.

- [ ] **Step 3: Build all affected release boards plus WS-C5-35**

Run the complete Python contract suite and the canonical all-release-board build gate, then build `ws-c5-35`.

- [ ] **Step 4: Physically qualify power behavior**

Test USB-only, battery-only, charging, cable transitions, PWR short/long press, software shutdown, backlight range/off, battery telemetry plausibility, cold boot, and repeated full power removal.

- [ ] **Step 5: Commit after the power evidence is recorded**

---

### Task 7: Qualify SD, UART GPS, radios, sensors, audio, and camera coexistence

**Files:**
- Modify: `ESP32C5/components/board_hal/include/boards/ws_c5_35.h`
- Modify shared consumers only where a normalized `BOARD_*` capability is missing
- Modify: `tests/test_ws_c5_35_support_contract.py`
- Modify: `docs/hardware/waveshare-c5-touch-lcd-35.md`

**Interfaces:**
- Enables one capability at a time only after its physical test passes.
- UART header remains the board's GPS transport.

- [ ] **Step 1: Qualify TF-card storage**

Test FAT32 mount, read, write, unmount/remount, capture creation, and power-cycle persistence at the board-scoped vendor/default SPI rate. Reduce speed only if hardware evidence shows instability, and keep any reduction specific to WS-C5-35.

- [ ] **Step 2: Qualify external UART GPS**

Wire the GPS module cross-over (`GPS TX → board RX`, `GPS RX → board TX`) using the verified header map. Confirm boot-time NMEA reception, 9600-baud operation, optional high-speed mode where supported, GPS Info, and wardrive coordinates.

- [ ] **Step 3: Qualify radios**

Exercise 2.4 GHz and 5 GHz Wi-Fi, BLE, IEEE 802.15.4, and ESP-NOW without camera/audio initialization. Record coexistence limitations rather than inferring parity from the ESP32-C5 SoC alone.

- [ ] **Step 4: Qualify optional peripherals independently**

Verify RTC, IMU, SHTC3, audio input/output, and BF3901 camera pin coexistence. Enable each `BOARD_HAS_*` flag only after its own test passes. Camera support is not required for the first CYM board release, but camera pin ownership must be conflict-free.

- [ ] **Step 5: Run bounded stability testing**

Perform repeated reboot/power cycles and a bounded soak while watching internal heap, PSRAM, DMA-capable memory, LVGL timing, SD operations, and radio transitions. Record duration and observed minima in the hardware README.

- [ ] **Step 6: Commit each coherent, independently qualified capability**

Do not combine an unverified audio or camera path into the commit that proves SD or GPS.

---

### Task 8: Promote packaging, release gate, documentation, and web flasher

**Files:**
- Modify: `Makefile`
- Modify: `scripts/build.sh`
- Create: `ESP32C5/docs/manifest.ws-c5-35.json`
- Create: `ESP32C5/binaries-ws-c5-35/README.md` and generated package set
- Modify: `ESP32C5/docs/index.html`
- Modify: `.github/workflows/deploy-flasher.yml`
- Modify: `README.md`
- Modify: `docs/hardware/waveshare-c5-touch-lcd-35.md`
- Modify the separate CYM wiki checkout
- Modify: `tests/test_ws_c5_35_support_contract.py`

**Interfaces:**
- Promotes `ws-c5-35` from planned/experimental to the fifth released board only after Tasks 1–7 pass.
- Produces a board-specific manifest and merged full image at offset `0x0000`.

- [ ] **Step 1: Extend packaging/flasher contracts and verify RED**

Assert a dedicated export directory, manifest, board selector, Pages workflow copy path, fifth-board `all-boards` membership, and removal of “Coming Soon” wording only after qualification evidence exists.

- [ ] **Step 2: Apply the shared patch-version bump**

Set all authoritative release-board `PROJECT_VER` values and manifests to the next patch version according to the canonical workflow. Do not increment minor or major versions automatically.

- [ ] **Step 3: Add dedicated package and web-flasher entries**

Use `manifest.ws-c5-35.json` and `binaries-ws-c5-35/`; never point the new selector at WS-C5-28 assets.

- [ ] **Step 4: Run the complete release-candidate verification**

Run:

```bash
python3 -m unittest discover -s tests -v
make all-boards
git diff --check
git status --short
```

Expected: every contract passes and all five release boards build and package successfully. Independently verify the version embedded in each board's application binary and each manifest.

- [ ] **Step 5: Commit and push only `Jimgat_Dev`**

Stage explicit files, use the canonical version-first commit subject for firmware/package changes, push `Jimgat_Dev`, and read back the remote branch SHA. Do not merge or push `main` without Jim's explicit release authorization.

- [ ] **Step 6: Release only when explicitly authorized**

For an authorized release, verify the raw manifest and full-image URLs, SHA-256, HTTP 200, GitHub Actions status, release assets, and public web-flasher selector. Report the direct raw full-image URL, SHA-256, and flash offset `0x0000`.
