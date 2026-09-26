# ES3C35P Shared CYM Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the Hosyond/LCDWiki ES3C35P 3.5-inch ESP32-S3 board to a supported CYM v2.15.27 release target using the canonical application, four-board release gates, complete packaging, and the shared web flasher.

**Architecture:** `ESP32C5/main/` remains the only canonical CYM application source tree. `ESP32S3/main/CMakeLists.txt` compiles those sources directly and adds one narrow ES3C35P hardware adapter; board capability and pin differences remain in `board_hal`. Shared application behavior, GPS parsing, storage formats, settings, screens, Wi-Fi, BLE, and menus are never forked for S3.

**Tech Stack:** C/CMake, ESP-IDF 6.0.2, LVGL 8.4, Espressif LCD/touch APIs, Python 3 contract tests, GNU Make, Bash packaging scripts, Web Serial/ESP Web Tools, GitHub Actions.

## Global Constraints

- Execute every source edit, test, build, package, commit, and push on ESP32-Dev as `dev` in `/home/dev/projects/CYM-NM28C5`.
- Keep `ESP32C5/main/` canonical; do not copy the CYM application into `ESP32S3/main/`.
- Promote only `hosyond-s3-35`; keep Hosyond 2.8-inch and 4.0-inch experimental and outside release gates.
- Preserve NM-CYD-C5, WS-C5-28, and CYD-2432S028 behavior.
- Keep ES3C35P-only LCD constraints board-scoped: ST77922 QSPI 40 MHz, 320x480, exact 63-entry initialization, four-pixel X alignment, ISR-to-task flush completion, address `0x55` capacitive touch, GPIO41 active-high backlight, no mirror, and physically confirmed RGB565 ordering.
- Enable ES3C35P 8 MB OPI PSRAM, 2.4 GHz Wi-Fi, BLE, SD on SPI3 at 20 MHz, WS2812 RGB on GPIO40, battery ADC on GPIO8 with a 100 kOhm/100 kOhm divider, and external GPS through UART1 TX GPIO43/RX GPIO44.
- Route WS-C5-28 external GPS through its board map using UART1 TX GPIO11/RX GPIO12.
- Use native USB Serial/JTAG for ES3C35P application logs so GPS owns connector UART pins 43/44.
- Gate 5 GHz, IEEE 802.15.4, audio, vibrator, and RF-HAT on ES3C35P.
- Use one shared release version: `v2.15.27`.
- Build all four release boards green before pushing an affected-code cycle.
- Preserve unrelated `.hermes/`, `docs/feedback/`, and `docs/prompts/` files; never reset, clean, stash, overwrite, or stage them.
- Do not flash hardware, force-push, merge or push `main`, create tags, or publish a release.
- Never add AI attribution trailers or comments to commits. Human co-developer credit remains allowed.
- Compilation is not hardware qualification. Final handoff must request a full USB-C power removal/reconnection before ES3C35P physical testing because LCD reset is tied to EN/`CHIP_PU`.

---

### Task 1: Add executable promotion contracts before implementation

**Files:**
- Create: `tests/test_es3c35p_promotion_contract.py`
- Modify: none

**Interfaces:**
- Consumes: tracked repository files and packaged artifacts.
- Produces: a deterministic Python contract suite used after every implementation task.

- [ ] **Step 1: Write the failing contract suite**

Create a `unittest` suite with repository-root-relative helpers:

```python
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

class PromotionContract(unittest.TestCase):
    def test_shared_source_and_adapter_boundary(self):
        cmake = text("ESP32S3/main/CMakeLists.txt")
        self.assertIn('set(C5_MAIN "${CMAKE_CURRENT_SOURCE_DIR}/../../ESP32C5/main")', cmake)
        self.assertIn('"${C5_MAIN}/main.c"', cmake)
        self.assertIn('"hosyond_s3_35_port.c"', cmake)
        self.assertNotRegex(cmake, r'(?m)^\s*"main\.c"\s*$')

    def test_es3c35p_profile(self):
        profile = text("ESP32C5/components/board_hal/include/boards/hosyond_s3_35.h")
        required = {
            "BOARD_HAS_PSRAM": "1", "BOARD_HAS_SD": "1",
            "BOARD_HAS_RGB_LED": "1", "BOARD_HAS_BATTERY_ADC": "1",
            "BOARD_HAS_GPS": "1", "BOARD_GPS_UART_NUM": "1",
            "BOARD_GPS_TX": "43", "BOARD_GPS_RX": "44",
            "BOARD_RGB_PIN": "40", "BOARD_BATTERY_ADC_GPIO": "8",
        }
        for macro, value in required.items():
            self.assertRegex(profile, rf"#define\s+{macro}\s+{value}\b")
        for macro in ("BOARD_HAS_5GHZ", "BOARD_HAS_IEEE802154", "BOARD_HAS_AUDIO",
                      "BOARD_HAS_VIBRATOR", "BOARD_HAS_RF_HAT"):
            self.assertRegex(profile, rf"#define\s+{macro}\s+0\b")

    def test_ws_c5_28_gps_profile(self):
        profile = text("ESP32C5/components/board_hal/include/boards/ws_c5_28.h")
        for macro, value in {"BOARD_HAS_GPS":"1", "BOARD_GPS_UART_NUM":"1",
                             "BOARD_GPS_TX":"11", "BOARD_GPS_RX":"12"}.items():
            self.assertRegex(profile, rf"#define\s+{macro}\s+{value}\b")

    def test_release_version_and_four_board_gate(self):
        for project in ("ESP32C5/CMakeLists.txt", "ESP32/CMakeLists.txt", "ESP32S3/CMakeLists.txt"):
            self.assertIn('set(PROJECT_VER "v2.15.27")', text(project))
        makefile = text("Makefile")
        for target in ("esp32c5", "ws-c5-28", "cyd-2432s028", "hosyond-s3-35"):
            self.assertIn(target, makefile)

    def test_manifest_and_flasher(self):
        manifest_path = ROOT / "ESP32S3/docs/manifest.hosyond-s3-35.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["name"], "CYM Hosyond ES3C35P 3.5 v2.15.27")
        parts = {item["offset"]: item["path"] for item in manifest["builds"][0]["parts"]}
        self.assertIn(0, parts)
        self.assertIn(0x8000, parts)
        self.assertIn(0x10000, parts)
        flasher = text("ESP32C5/docs/index.html")
        self.assertIn("hosyond-s3-35", flasher)
        self.assertIn("ESP32-S3", flasher)
        self.assertIn("binaries-hosyond-s3-35", flasher)
        workflow = text(".github/workflows/deploy-flasher.yml")
        self.assertIn("ESP32S3/docs/manifest.hosyond-s3-35.json", workflow)
        self.assertIn("ESP32S3/binaries-hosyond-s3-35", workflow)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract and verify RED**

Run: `python3 -m unittest -v tests.test_es3c35p_promotion_contract`

Expected: failures for canonical S3 source reuse, GPS macros, `v2.15.27`, the new S3 manifest, and the flasher entry.

- [ ] **Step 3: Record the baseline without staging unrelated work**

Run:

```bash
git status --short
git diff --check
git add tests/test_es3c35p_promotion_contract.py
git commit -m "test: define ES3C35P promotion contracts"
```

Expected: only the new contract test is committed; existing untracked files remain untouched.

---

### Task 2: Lock board capabilities, UART/GPS maps, and S3 console ownership

**Files:**
- Modify: `ESP32C5/components/board_hal/include/boards/hosyond_s3_35.h`
- Modify: `ESP32C5/components/board_hal/include/boards/ws_c5_28.h`
- Modify: `ESP32C5/components/board_hal/board_hal.h`
- Modify: `ESP32C5/components/board_hal/board_hal.c`
- Modify: `ESP32C5/components/board_hal/Kconfig`
- Modify: `ESP32S3/sdkconfig.defaults.hosyond-s3-35`
- Test: `tests/test_es3c35p_promotion_contract.py`

**Interfaces:**
- Produces profile macros `BOARD_HAS_GPS`, `BOARD_GPS_UART_NUM`, `BOARD_GPS_TX`, `BOARD_GPS_RX`, `BOARD_HAS_BATTERY_ADC`, `BOARD_BATTERY_ADC_GPIO`, `BOARD_BATTERY_DIVIDER_NUM`, `BOARD_BATTERY_DIVIDER_DEN`, `BOARD_HAS_RGB_LED`, and `BOARD_RGB_PIN`.
- Existing consumers continue using the `BOARD_*` namespace; do not introduce an S3-only GPS parser.

- [ ] **Step 1: Extend the contract with pin ownership assertions**

Assert ES3C35P SD pins and 20 MHz are the schematic/profile values already locked in `hosyond_s3_35.h`, and assert the S3 sdkconfig contains:

```text
CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y
CONFIG_ESP_CONSOLE_UART_NONE=y
# CONFIG_ESP_CONSOLE_UART_DEFAULT is not set
```

- [ ] **Step 2: Run the focused contract and verify RED**

Run: `python3 -m unittest -v tests.test_es3c35p_promotion_contract.PromotionContract.test_es3c35p_profile tests.test_es3c35p_promotion_contract.PromotionContract.test_ws_c5_28_gps_profile`

Expected: missing GPS/capability declarations fail.

- [ ] **Step 3: Add the board-scoped macros**

Use the following semantic values in `hosyond_s3_35.h`:

```c
#define BOARD_HAS_PSRAM              1
#define BOARD_HAS_SD                 1
#define BOARD_SD_SPI_FREQ_HZ         20000000
#define BOARD_HAS_RGB_LED            1
#define BOARD_RGB_PIN                40
#define BOARD_HAS_BATTERY_ADC        1
#define BOARD_BATTERY_ADC_GPIO       8
#define BOARD_BATTERY_DIVIDER_NUM    2
#define BOARD_BATTERY_DIVIDER_DEN    1
#define BOARD_HAS_GPS                1
#define BOARD_GPS_UART_NUM           1
#define BOARD_GPS_TX                 43
#define BOARD_GPS_RX                 44
#define BOARD_HAS_5GHZ               0
#define BOARD_HAS_IEEE802154         0
#define BOARD_HAS_AUDIO              0
#define BOARD_HAS_VIBRATOR           0
#define BOARD_HAS_RF_HAT             0
```

Use the following GPS values in `ws_c5_28.h`:

```c
#define BOARD_HAS_GPS                1
#define BOARD_GPS_UART_NUM           1
#define BOARD_GPS_TX                 11
#define BOARD_GPS_RX                 12
```

Expose safe zero/default fallbacks in `board_hal.h` for boards that omit a capability. Keep board selection in `board_hal.c` and Kconfig consistent with the current pattern; no runtime board probing is added.

- [ ] **Step 4: Move logs off UART0 for ES3C35P**

Set native USB Serial/JTAG as the sole application console in `ESP32S3/sdkconfig.defaults.hosyond-s3-35`; do not disable UART1 and do not assign 43/44 to the console.

- [ ] **Step 5: Run tests and configuration verification**

Run:

```bash
python3 -m unittest -v tests.test_es3c35p_promotion_contract
git diff --check
git diff -- ESP32C5/components/board_hal ESP32S3/sdkconfig.defaults.hosyond-s3-35 tests/test_es3c35p_promotion_contract.py
```

Expected: profile tests pass; unrelated board constants are unchanged.

- [ ] **Step 6: Commit**

```bash
git add tests/test_es3c35p_promotion_contract.py ESP32C5/components/board_hal ESP32S3/sdkconfig.defaults.hosyond-s3-35
git commit -m "feat(board): expose ES3C35P and WS-C5-28 UART capabilities"
```

---

### Task 3: Extract the qualified ES3C35P display/touch transport into a thin adapter

**Files:**
- Create: `ESP32S3/main/hosyond_s3_35_port.h`
- Create: `ESP32S3/main/hosyond_s3_35_port.c`
- Preserve: `ESP32S3/main/hosyond_s3_35_lcd_init.h`
- Modify: `tests/test_es3c35p_promotion_contract.py`

**Interfaces:**
- Produces:

```c
typedef struct {
    esp_lcd_panel_handle_t panel;
    SemaphoreHandle_t flush_done;
} hosyond_s3_35_display_t;

esp_err_t hosyond_s3_35_display_init(hosyond_s3_35_display_t *display);
esp_err_t hosyond_s3_35_draw(hosyond_s3_35_display_t *display,
                             int x1, int y1, int x2, int y2,
                             const void *pixels);
void hosyond_s3_35_round_area(lv_area_t *area);
esp_err_t hosyond_s3_35_touch_init(void);
bool hosyond_s3_35_touch_read(uint16_t *x, uint16_t *y, bool *pressed);
```

- Consumes the exact 63-entry initialization table already stored in `hosyond_s3_35_lcd_init.h`.

- [ ] **Step 1: Add source-contract tests for qualified invariants**

Assert the adapter contains `40000000`, `CONFIG_BOARD_HOSYOND_S3_35`, `xSemaphoreGiveFromISR`, `xSemaphoreTake`, GPIO41, I2C address `0x55`, and four-pixel X rounding. Assert `hosyond_s3_35_lcd_init.h` still has 63 initialization entries, `0x013F` CASET end, `0x01DF` RASET end, and MADCTL `0x00`.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.test_es3c35p_promotion_contract`

Expected: the new adapter paths do not exist.

- [ ] **Step 3: Move, do not redesign, the physically qualified transport**

Extract the ST77922 panel IO creation, panel reset/init, inversion, backlight, QSPI completion callback, binary semaphore, four-pixel rounder, and capacitive touch transaction code from the qualified diagnostic `ESP32S3/main/main.c` into the adapter. Preserve:

```c
#define HOSYOND_PANEL_PCLK_HZ 40000000
#define HOSYOND_TOUCH_ADDR    0x55
#define HOSYOND_BACKLIGHT     41
```

The ISR callback must only signal `flush_done` with `xSemaphoreGiveFromISR`; `hosyond_s3_35_draw()` waits in task context before returning. Do not call `lv_disp_flush_ready()` from ISR context. Do not add X/Y mirror or an RGB565 byte/channel swap.

- [ ] **Step 4: Verify adapter contracts**

Run:

```bash
python3 -m unittest -v tests.test_es3c35p_promotion_contract
git diff --check
git diff -- ESP32S3/main/hosyond_s3_35_port.c ESP32S3/main/hosyond_s3_35_port.h ESP32S3/main/hosyond_s3_35_lcd_init.h
```

Expected: qualified invariants pass and the initialization header remains byte-for-byte unchanged.

- [ ] **Step 5: Commit**

```bash
git add tests/test_es3c35p_promotion_contract.py ESP32S3/main/hosyond_s3_35_port.c ESP32S3/main/hosyond_s3_35_port.h
git commit -m "feat(s3): extract qualified ES3C35P display port"
```

---

### Task 4: Compile the canonical CYM application for S3 and gate unsupported silicon paths

**Files:**
- Modify: `ESP32S3/main/CMakeLists.txt`
- Modify: `ESP32S3/main/idf_component.yml`
- Modify: `ESP32C5/main/main.c`
- Modify: `ESP32C5/main/wifi_common.h`
- Modify: other `ESP32C5/main/*` files only where the compiler proves an ESP32-C5-only API is unguarded
- Stop compiling: `ESP32S3/main/main.c`
- Test: `tests/test_es3c35p_promotion_contract.py`

**Interfaces:**
- Consumes the Task 3 adapter only inside `#if CONFIG_BOARD_HOSYOND_S3_35` branches.
- Produces the same `app_main()` and shared CYM UI/feature implementation used by existing boards.

- [ ] **Step 1: Add CMake and guard assertions**

Assert `ESP32S3/main/CMakeLists.txt` sets `C5_MAIN`, lists every source from `ESP32/main/CMakeLists.txt`, adds `hosyond_s3_35_port.c`, includes `${C5_MAIN}`, and does not compile the local diagnostic `main.c`. Assert the canonical source uses `CONFIG_BOARD_HOSYOND_S3_35` only for hardware transport, not duplicate screens or menus.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.test_es3c35p_promotion_contract.PromotionContract.test_shared_source_and_adapter_boundary`

Expected: current S3 CMake still compiles the diagnostic entry point.

- [ ] **Step 3: Rebuild the S3 main component definition**

Copy the canonical source inventory and component requirements from `ESP32/main/CMakeLists.txt`, then add `hosyond_s3_35_port.c` and the S3 LCD/touch component requirement. Keep `ieee802154` excluded on S3. Use:

```cmake
set(C5_MAIN "${CMAKE_CURRENT_SOURCE_DIR}/../../ESP32C5/main")

idf_component_register(
    SRCS
        "${C5_MAIN}/attack_handshake.c"
        "${C5_MAIN}/xpt2046.c"
        "${C5_MAIN}/lvgl_memory.c"
        "${C5_MAIN}/main.c"
        "${C5_MAIN}/dexter_img.c"
        "${C5_MAIN}/lv_extra_symbols.c"
        "${C5_MAIN}/lab_bg.c"
        "${C5_MAIN}/deedee_img.c"
        "${C5_MAIN}/bt_lookout.c"
        "${C5_MAIN}/oui_lookup.c"
        "${C5_MAIN}/gatt_walker.c"
        "${C5_MAIN}/ble_honeypair.c"
        "${C5_MAIN}/ble_blueduck.c"
        "${C5_MAIN}/ble_whisperpair.c"
        "${C5_MAIN}/sd_error_handler.c"
        "${C5_MAIN}/chameleon_ble.c"
        "hosyond_s3_35_port.c"
    INCLUDE_DIRS "${C5_MAIN}" "."
)
```

Merge the current S3 LCD dependencies with the complete `REQUIRES` and `PRIV_REQUIRES` lists from the working ESP32 canonical-source reuse target. Do not add `ieee802154`.

- [ ] **Step 4: Wire shared callbacks to the adapter**

In the existing canonical display initialization and LVGL flush/touch callbacks, add board-guarded calls to the Task 3 API. The LVGL callback remains shared:

```c
#if CONFIG_BOARD_HOSYOND_S3_35
    esp_err_t err = hosyond_s3_35_draw(&s_hosyond_display,
                                       area->x1, area->y1,
                                       area->x2 + 1, area->y2 + 1,
                                       color_map);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ES3C35P flush failed: %s", esp_err_to_name(err));
    }
    lv_disp_flush_ready(drv);
    return;
#endif
```

Set the LVGL rounder callback to `hosyond_s3_35_round_area` only on ES3C35P. Use `hosyond_s3_35_touch_read()` only in the shared input callback’s ES3C35P branch. Existing C5 and classic ESP32 branches remain unchanged.

- [ ] **Step 5: Compile once and use errors as the only scope for compatibility guards**

Run: `make build-hosyond-s3-35`

Expected first result: compiler errors identify any C5-only APIs or component dependencies still reachable on ESP32-S3.

For each error, add the smallest capability or SoC guard around only the unavailable operation. Do not remove shared UI code. Explicitly gate IEEE 802.15.4 and 5 GHz operations behind their existing capability checks, and compile audio/vibrator/RF-HAT code out for ES3C35P.

- [ ] **Step 6: Repeat until S3 canonical build is green**

Run:

```bash
python3 -m unittest -v tests.test_es3c35p_promotion_contract
make build-hosyond-s3-35
git diff --check
```

Expected: canonical CYM links for ESP32-S3 and produces application, bootloader, partition table, and merged-image binaries. This is compilation proof only.

- [ ] **Step 7: Commit**

```bash
git add tests/test_es3c35p_promotion_contract.py ESP32S3/main/CMakeLists.txt ESP32S3/main/idf_component.yml ESP32S3/main/hosyond_s3_35_port.c ESP32S3/main/hosyond_s3_35_port.h ESP32C5/main
git commit -m "feat(s3): run canonical CYM application on ES3C35P"
```

---

### Task 5: Connect SD, RGB, battery, and GPS to existing shared feature paths

**Files:**
- Modify: `ESP32C5/main/main.c`
- Modify: canonical shared peripheral modules selected by existing call sites
- Modify: `ESP32C5/components/board_hal/include/boards/hosyond_s3_35.h`
- Modify: `ESP32C5/components/board_hal/include/boards/ws_c5_28.h`
- Test: `tests/test_es3c35p_promotion_contract.py`

**Interfaces:**
- GPS continues to use the existing canonical parser/queue and reads `BOARD_GPS_UART_NUM`, `BOARD_GPS_TX`, and `BOARD_GPS_RX`.
- SD continues to use the existing shared FAT/VFS code and board SPI pins/frequency.
- Battery reporting consumes raw ADC through board profile scaling; 100 kOhm/100 kOhm means a 2:1 voltage scale.
- RGB calls the existing shared LED UI/status behavior through a one-pixel WS2812 transport on GPIO40.

- [ ] **Step 1: Add source contracts for shared paths**

Assert no `gps_*`, screen, settings, or storage implementation is created under `ESP32S3/`. Assert canonical GPS UART setup references board macros, SD clock references `BOARD_SD_SPI_FREQ_HZ`, battery scaling references board divider macros, and RGB initialization is capability-gated.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.test_es3c35p_promotion_contract`

Expected: at least GPS, battery, or RGB shared-path assertions fail.

- [ ] **Step 3: Parameterize existing peripheral initialization**

Replace hard-coded UART/pin assumptions in the existing GPS initializer with:

```c
uart_config_t gps_uart_config = {
    .baud_rate = 9600,
    .data_bits = UART_DATA_8_BITS,
    .parity = UART_PARITY_DISABLE,
    .stop_bits = UART_STOP_BITS_1,
    .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
    .source_clk = UART_SCLK_DEFAULT,
};
uart_param_config((uart_port_t)BOARD_GPS_UART_NUM, &gps_uart_config);
uart_set_pin((uart_port_t)BOARD_GPS_UART_NUM,
             BOARD_GPS_TX, BOARD_GPS_RX,
             UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
```

Guard this initializer with `#if BOARD_HAS_GPS`. Keep the parser and UI unchanged.

Use the existing SD mount and file APIs with ES3C35P profile pins on SPI3 and exactly 20 MHz. Do not lower other boards’ SPI frequencies.

Use a shared ADC conversion function whose board-specific scaling is:

```c
millivolts = millivolts * BOARD_BATTERY_DIVIDER_NUM / BOARD_BATTERY_DIVIDER_DEN;
```

Initialize a one-pixel WS2812/RMT device only when `BOARD_HAS_RGB_LED` is true; existing non-addressable RGB implementations remain unchanged.

- [ ] **Step 4: Build the S3 target and run contracts**

Run:

```bash
python3 -m unittest -v tests.test_es3c35p_promotion_contract
make build-hosyond-s3-35
git diff --check
```

Expected: build and contracts pass. Logs may state peripherals are configured; do not claim physical function.

- [ ] **Step 5: Commit**

```bash
git add tests/test_es3c35p_promotion_contract.py ESP32C5/main ESP32C5/components/board_hal/include/boards/hosyond_s3_35.h ESP32C5/components/board_hal/include/boards/ws_c5_28.h
git commit -m "feat(board): route shared CYM peripherals through board profiles"
```

---

### Task 6: Add v2.15.27 build gates, packaging, and the S3 manifest

**Files:**
- Modify: `ESP32C5/CMakeLists.txt`
- Modify: `ESP32/CMakeLists.txt`
- Modify: `ESP32S3/CMakeLists.txt`
- Modify: `Makefile`
- Modify: `scripts/build.sh`
- Create: `ESP32S3/docs/manifest.hosyond-s3-35.json`
- Modify: `.gitignore` only if `git check-ignore -v` proves the new packaged binaries are excluded
- Test: `tests/test_es3c35p_promotion_contract.py`

**Interfaces:**
- `make all-boards` builds and packages NM-CYD-C5, WS-C5-28, CYD-2432S028, and hosyond-s3-35.
- ES3C35P package names are `CYM-hosyond-s3-35.bin`, `CYM-hosyond-s3-35-full.bin`, `bootloader.bin`, and `partition-table.bin` under `ESP32S3/binaries-hosyond-s3-35/`.
- Manifest offsets are bootloader `0x0000`, partition table `0x8000`, application `0x10000`.

- [ ] **Step 1: Extend contracts for exact package names and offsets**

Assert all three project versions are `v2.15.27`, `make all-boards` includes all four target recipes, `scripts/build.sh` recognizes `hosyond-s3-35`, and the manifest points at the exact package names and offsets above.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.test_es3c35p_promotion_contract`

Expected: version, four-board gate, and manifest assertions fail.

- [ ] **Step 3: Implement version and gate changes**

Change only each source `PROJECT_VER` line to `v2.15.27`. Add ES3C35P to the same code-update build/package path as the three existing release boards. Keep experimental S3 variants out.

- [ ] **Step 4: Create the S3 manifest**

Use the existing manifest schema with:

```json
{
  "name": "CYM Hosyond ES3C35P 3.5 v2.15.27",
  "version": "v2.15.27",
  "builds": [{
    "chipFamily": "ESP32-S3",
    "parts": [
      {"path": "../binaries-hosyond-s3-35/bootloader.bin", "offset": 0},
      {"path": "../binaries-hosyond-s3-35/partition-table.bin", "offset": 32768},
      {"path": "../binaries-hosyond-s3-35/CYM-hosyond-s3-35.bin", "offset": 65536}
    ]
  }]
}
```

Match any additional required schema keys from the three tracked release manifests without changing their semantics.

- [ ] **Step 5: Build/package ES3C35P and verify tracked inclusion**

Run:

```bash
make build-hosyond-s3-35
python3 -m json.tool ESP32S3/docs/manifest.hosyond-s3-35.json >/dev/null
git check-ignore -v ESP32S3/binaries-hosyond-s3-35/*.bin || true
git status --short ESP32S3/binaries-hosyond-s3-35 ESP32S3/docs/manifest.hosyond-s3-35.json
```

If an existing broad ignore rule excludes release binaries, add a narrowly scoped exception for `ESP32S3/binaries-hosyond-s3-35/*.bin`; do not unignore build directories.

- [ ] **Step 6: Run contracts and commit source-side release integration**

```bash
python3 -m unittest -v tests.test_es3c35p_promotion_contract
git diff --check
git add tests/test_es3c35p_promotion_contract.py ESP32C5/CMakeLists.txt ESP32/CMakeLists.txt ESP32S3/CMakeLists.txt Makefile scripts/build.sh ESP32S3/docs/manifest.hosyond-s3-35.json .gitignore
git commit -m "build: add ES3C35P to the v2.15.27 release gate"
```

Omit `.gitignore` from `git add` when it did not change.

---

### Task 7: Add ES3C35P to the shared web flasher and Pages deployment

**Files:**
- Modify: `ESP32C5/docs/index.html`
- Modify: `.github/workflows/deploy-flasher.yml`
- Modify: `tests/test_es3c35p_promotion_contract.py`

**Interfaces:**
- Produces default-visible board ID `hosyond-s3-35`, label `Hosyond ES3C35P 3.5`, chip family `ESP32-S3`, manifest `manifest.hosyond-s3-35.json`, binary directory `binaries-hosyond-s3-35`, and `beta: false`.
- Stable/dev branch selection and chip mismatch refusal continue using the shared flasher logic.

- [ ] **Step 1: Add DOM/static-site contract assertions**

Assert `DEFAULT_BOARD_IDS` contains `hosyond-s3-35`, its board definition has `beta: false`, the app and full-image download names are exact, and the workflow stages `_site/manifest.hosyond-s3-35.json` plus `_site/binaries-hosyond-s3-35/`.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.test_es3c35p_promotion_contract.PromotionContract.test_manifest_and_flasher`

Expected: selector/workflow assertions fail.

- [ ] **Step 3: Add the flasher board definition and increment page version**

Add:

```javascript
{
  id: "hosyond-s3-35",
  label: "Hosyond ES3C35P 3.5",
  chipFamily: "ESP32-S3",
  sourceDir: "ESP32S3",
  binaryDir: "binaries-hosyond-s3-35",
  appBinary: "CYM-hosyond-s3-35.bin",
  fullBinary: "CYM-hosyond-s3-35-full.bin",
  manifest: "manifest.hosyond-s3-35.json",
  beta: false
}
```

Add the ID to `DEFAULT_BOARD_IDS`. Keep the current stable/dev branch URL builder and direct-download rendering; do not create a second S3 page.

- [ ] **Step 4: Expand the Pages workflow**

Add path triggers for the S3 manifest, S3 binary directory, and shared flasher source. In the site-build step create and fill all four binary directories, rewrite each manifest’s `../binaries-*` path to its Pages-relative directory, and fail if any manifest or required binary is absent. Preserve existing Pages permissions and deployment behavior.

- [ ] **Step 5: Verify generated site locally**

Run the workflow’s site-build shell commands locally into `_site/`, then run:

```bash
python3 -m unittest -v tests.test_es3c35p_promotion_contract
python3 -m json.tool _site/manifest.hosyond-s3-35.json >/dev/null
test -f _site/binaries-hosyond-s3-35/CYM-hosyond-s3-35-full.bin
test -f _site/binaries-hosyond-s3-35/CYM-hosyond-s3-35.bin
git diff --check
```

Expected: all checks pass. Remove only generated `_site/` after verification if it is untracked; do not clean the repository.

- [ ] **Step 6: Commit**

```bash
git add tests/test_es3c35p_promotion_contract.py ESP32C5/docs/index.html .github/workflows/deploy-flasher.yml
git commit -m "feat(flasher): add supported ES3C35P target"
```

---

### Task 8: Update support documentation without overstating qualification

**Files:**
- Modify: `README.md`
- Modify: `BACKLOG.md`
- Modify: `docs/hardware/hosyond-s3-family.md`
- Modify: `docs/hardware/hosyond-s3-35/README.md`
- Modify: release/build documentation referenced by `Makefile help`

**Interfaces:**
- Produces an accurate supported-board matrix and a physical acceptance checklist.

- [ ] **Step 1: Update status language**

Mark ES3C35P 3.5-inch as a supported software release target at v2.15.27. Keep 2.8-inch and 4.0-inch explicitly experimental. State display and touch were physically qualified during bring-up; SD, RGB, battery voltage, external GPS, Wi-Fi, BLE, and bounded soak remain pending on the shared-CYM image until the user tests them.

- [ ] **Step 2: Document the physical acceptance procedure**

Include:

1. Flash `CYM-hosyond-s3-35-full.bin` at offset `0x0000`.
2. Disconnect USB-C completely.
3. Wait approximately 10 seconds.
4. Reconnect power.
5. Confirm CYM home screen, orientation, colors, touch, 8 MB PSRAM, 2.4 GHz Wi-Fi, BLE, SD read/write, RGB LED, plausible battery voltage, external UART GPS NMEA input, and a bounded no-panic soak.
6. Confirm 5 GHz, IEEE 802.15.4, audio, vibrator, and RF-HAT are not offered.

- [ ] **Step 3: Verify documentation and commit**

Run:

```bash
python3 -m unittest -v tests.test_es3c35p_promotion_contract
git diff --check
git diff -- README.md BACKLOG.md docs/hardware
```

Then:

```bash
git add README.md BACKLOG.md docs/hardware/hosyond-s3-family.md docs/hardware/hosyond-s3-35/README.md
git commit -m "docs: promote qualified ES3C35P software target"
```

Add only any additional release/build documentation file actually changed.

---

### Task 9: Run the complete four-board gate and independently verify packages

**Files:**
- Generated and staged: existing three release binary directories
- Generated and staged: `ESP32S3/binaries-hosyond-s3-35/`
- Generated and staged: release manifests whose embedded version/hash metadata changes

**Interfaces:**
- Produces four green builds and independently verified release packages.

- [ ] **Step 1: Confirm single-writer and clean intended diff**

Run:

```bash
ps -u dev -o pid,ppid,stat,etime,args | grep -E '[i]df.py|[c]make|[n]inja|[c]laude|[c]odex' || true
git status --short
git diff --check
```

Stop if another active writer/build exists. Ignore the known idle historical Claude process only after confirming it has no child and no repository file open.

- [ ] **Step 2: Run the supported-board gate**

Run: `make all-boards`

Expected: NM-CYD-C5, WS-C5-28, CYD-2432S028, and hosyond-s3-35 all configure, compile, link, and package successfully. A failure blocks the push.

- [ ] **Step 3: Verify each package independently**

For each board, verify:

```bash
esptool.py image_info ESP32C5/binaries-esp32c5/CYM-NM28C5.bin
esptool.py image_info ESP32C5/binaries-ws-c5-28/CYM-WS-C5-28.bin
esptool.py image_info ESP32/binaries-cyd-2432s028/CYM-CYD-2432S028.bin
esptool.py image_info ESP32S3/binaries-hosyond-s3-35/CYM-hosyond-s3-35.bin
sha256sum ESP32C5/binaries-esp32c5/*.bin ESP32C5/binaries-ws-c5-28/*.bin ESP32/binaries-cyd-2432s028/*.bin ESP32S3/binaries-hosyond-s3-35/*.bin
python3 -m json.tool ESP32C5/docs/manifest.json >/dev/null
python3 -m json.tool ESP32C5/docs/manifest.ws-c5-28.json >/dev/null
python3 -m json.tool ESP32/docs/manifest.cyd-2432s028.json >/dev/null
python3 -m json.tool ESP32S3/docs/manifest.hosyond-s3-35.json >/dev/null
```

Extract `PROJECT_VER`/app descriptor from each application binary and require `v2.15.27`. Confirm each manifest path exists and each manifest part matches its packaged file. Confirm ES3C35P full image begins at flash offset `0x0000` and contains bootloader, partition table at `0x8000`, and app at `0x10000`.

- [ ] **Step 4: Verify committed-object inclusion before publication**

Stage only intended packages/manifests, then use:

```bash
git diff --cached --name-status
git ls-files ESP32S3/binaries-hosyond-s3-35 ESP32S3/docs/manifest.hosyond-s3-35.json
git check-ignore -v ESP32S3/binaries-hosyond-s3-35/*.bin || true
```

Create a temporary archive of the staged tree or final commit and repeat manifest-path and SHA-256 verification against extracted committed objects, not merely the working tree.

- [ ] **Step 5: Commit generated release artifacts**

```bash
git add ESP32C5/binaries-esp32c5 ESP32C5/binaries-ws-c5-28         ESP32/binaries-cyd-2432s028 ESP32S3/binaries-hosyond-s3-35         ESP32C5/docs/manifest.json ESP32C5/docs/manifest.ws-c5-28.json         ESP32/docs/manifest.cyd-2432s028.json ESP32S3/docs/manifest.hosyond-s3-35.json
git commit -m "build: package CYM v2.15.27 for supported boards"
```

Never use `git add -A` or `git add .`.

- [ ] **Step 6: Run final source and artifact verification**

```bash
python3 -m unittest -v tests.test_es3c35p_promotion_contract
make all-boards
git diff --check
git status --short
```

Expected: all contracts/builds pass; only known unrelated untracked files remain.

---

### Task 10: Push the verified cycle and prepare the hardware handoff

**Files:**
- No source changes expected.

**Interfaces:**
- Produces a verified `origin/Jimgat_Dev` commit and immutable raw artifact URL.

- [ ] **Step 1: Inspect commit history for prohibited attribution and scope**

Run:

```bash
git log --format=fuller origin/Jimgat_Dev..HEAD
git diff --stat origin/Jimgat_Dev..HEAD
git log --format=%B origin/Jimgat_Dev..HEAD | grep -Eai 'co-authored-by:.*(ai|claude|openai|codex)|generated-by|assisted-by' && exit 1 || true
```

Expected: no AI attribution; only planned files and release artifacts changed.

- [ ] **Step 2: Push only the development branch**

Run:

```bash
git fetch origin Jimgat_Dev
test "$(git rev-parse origin/Jimgat_Dev)" = "$(git merge-base HEAD origin/Jimgat_Dev)"
git push origin HEAD:Jimgat_Dev
```

Expected: fast-forward update; no tag or main update.

- [ ] **Step 3: Verify GitHub objects and artifact hash**

Read back `origin/Jimgat_Dev`, download the raw ES3C35P full image from the immutable commit URL, and compare SHA-256 with the local packaged full image. Verify the branch raw URL independently.

Required handoff fields:

```bash
pushed_sha=$(git rev-parse HEAD)
full_image=ESP32S3/binaries-hosyond-s3-35/CYM-hosyond-s3-35-full.bin
full_sha=$(sha256sum "$full_image" | cut -d" " -f1)
printf "Version: v2.15.27\nCommit: %s\nImmutable URL: https://raw.githubusercontent.com/JimGat/CYM/%s/ESP32S3/binaries-hosyond-s3-35/CYM-hosyond-s3-35-full.bin\nBranch URL: https://raw.githubusercontent.com/JimGat/CYM/Jimgat_Dev/ESP32S3/binaries-hosyond-s3-35/CYM-hosyond-s3-35-full.bin\nSHA-256: %s\nFlash offset: 0x0000\n" "$pushed_sha" "$pushed_sha" "$full_sha"
```

- [ ] **Step 4: Request physical acceptance without claiming it**

Tell the user to flash at `0x0000`, physically remove USB-C power, wait approximately 10 seconds, reconnect, and execute the Task 8 checklist. Report build proof separately from pending hardware proof.
