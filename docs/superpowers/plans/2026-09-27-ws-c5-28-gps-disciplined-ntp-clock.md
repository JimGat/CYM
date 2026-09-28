# WS-C5-28 GPS-Disciplined NTP Clock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a WS-C5-28-only functional clock that continuously disciplines UTC from GPS, maintains the PCF85063A RTC, serves NTP over DHCP Wi-Fi, and displays the assigned IP and timing state without automatic dimming.

**Architecture:** Add a focused `cym_timekeeper` ESP-IDF component containing PCF85063A access, source-state discipline, and an isolated UDP NTP responder. Integrate it with the existing GPS parser and WS-C5-28 I2C bus, then add board-gated Clock Settings and NTP Clock LVGL screens in `main.c`. Classic launches from WiFi; Modern launches from Tools & System; both share the same screen and bounded teardown.

**Tech Stack:** ESP-IDF C, FreeRTOS, new I2C master driver, lwIP sockets, mDNS, NVS, LVGL 8, Python `unittest` source contracts, ESP-IDF multi-board build scripts.

## Global Constraints

- All source edits, tests, builds, packages, commits, and pushes execute on ESP32-Dev as `dev`; the JARVIS VM is orchestration only.
- Work only in `/home/dev/projects/CYM-NM28C5-jarvis-ws35-docs` on `Jimgat_Dev`; preserve unrelated and untracked work.
- Scope source behavior to `CONFIG_BOARD_WS_C5_28` or `CONFIG_BOARD_HAS_RTC`; do not change released behavior on other boards.
- RTC, GPS, system wall clock, and NTP remain UTC. Display offset never affects served time.
- NTP Clock is exclusive, serves until Exit, and never automatically dims.
- Version one supports UART-only GPS. Do not assign or expose a PPS GPIO.
- No hardware-success or accuracy claim may be made from compilation alone.
- Classic and Modern navigation are independent contracts.
- Do not add AI attribution trailers to commits.
- Use one shared cycle version. Bump `v2.15.34` to `v2.15.35` only after implementation tests are green, then build all released boards before pushing the cycle.

---

### Task 1: Add failing NTP Clock contracts

**Files:**
- Create: `tests/test_ws_c5_28_ntp_clock_contract.py`
- Read: `docs/superpowers/specs/2026-09-27-ws-c5-28-gps-disciplined-ntp-clock-design.md`

**Interfaces:**
- Consumes: board header, component headers, `ESP32C5/main/main.c`, and main/component CMake files as text.
- Produces: regression tests that require the exact component API and board-gated navigation/UI strings used by later tasks.

- [ ] **Step 1: Write source contracts before implementation**

Create tests requiring:

```python
self.assertIn("#define BOARD_RTC_I2C_ADDR 0x51", WS_BOARD)
self.assertIn("cym_timekeeper_observe_gps_utc", MAIN)
self.assertIn("cym_ntp_server_start", MAIN)
self.assertIn('"NTP\\nClock"', MAIN)
self.assertIn('"Clock"', MAIN)
self.assertRegex(MAIN, r"#if defined\(CONFIG_BOARD_WS_C5_28\).*?NTP\\nClock")
self.assertIn("DHCP IP", MAIN)
self.assertIn("cym-ntp", MAIN)
self.assertIn("s_ntp_clock_active", MAIN)
self.assertIn("cym_timekeeper", MAIN_CMAKE)
```

Also assert the component header contains:

```c
typedef enum { CYM_TIME_UNSYNCED, CYM_TIME_GPS_ACQUIRING,
               CYM_TIME_GPS_LOCKED, CYM_TIME_RTC_HOLDOVER } cym_time_source_t;
esp_err_t cym_timekeeper_init(i2c_master_bus_handle_t bus);
esp_err_t cym_timekeeper_observe_gps_utc(time_t epoch, int64_t rx_monotonic_us);
bool cym_timekeeper_snapshot(cym_time_snapshot_t *out);
esp_err_t cym_ntp_server_start(void);
void cym_ntp_server_stop(void);
```

- [ ] **Step 2: Run the focused contract and verify RED**

Run:

```bash
python3 -m unittest -v tests.test_ws_c5_28_ntp_clock_contract
```

Expected: failures because the component, board address, navigation, and UI do not exist.

- [ ] **Step 3: Commit the failing contract**

```bash
git add tests/test_ws_c5_28_ntp_clock_contract.py
git commit -m "test: define WS-C5-28 NTP clock contracts"
```

### Task 2: Implement PCF85063A RTC and shared timekeeper

**Files:**
- Create: `ESP32C5/components/cym_timekeeper/CMakeLists.txt`
- Create: `ESP32C5/components/cym_timekeeper/include/cym_timekeeper.h`
- Create: `ESP32C5/components/cym_timekeeper/cym_timekeeper.c`
- Create: `ESP32C5/components/cym_timekeeper/pcf85063.c`
- Create: `ESP32C5/components/cym_timekeeper/pcf85063.h`
- Modify: `ESP32C5/components/board_hal/include/boards/ws_c5_28.h`
- Modify: `ESP32C5/main/CMakeLists.txt`
- Modify: `ESP32C5/main/main.c` around the I2C initialization and RMC parser

**Interfaces:**
- Consumes: `i2c_master_bus_handle_t s_i2c_bus`, validated RMC epoch and parse-completion monotonic timestamp.
- Produces:

```c
esp_err_t cym_timekeeper_init(i2c_master_bus_handle_t bus);
esp_err_t cym_timekeeper_observe_gps_utc(time_t epoch, int64_t rx_monotonic_us);
void cym_timekeeper_note_gps_present(bool present);
bool cym_timekeeper_snapshot(cym_time_snapshot_t *out);
const char *cym_timekeeper_source_name(cym_time_source_t source);
```

- [ ] **Step 1: Add the board RTC contract and component registration**

Add to `ws_c5_28.h`:

```c
#define BOARD_RTC_I2C_ADDR 0x51
```

Register `cym_timekeeper` with `REQUIRES driver esp_timer nvs_flash lwip` and add it to main's `PRIV_REQUIRES`.

- [ ] **Step 2: Implement PCF85063A register access**

Implement bounded `i2c_master_bus_add_device`, register reads/writes, BCD conversion, calendar validation, oscillator-stop rejection, and UTC read/write. Use the new I2C master API and a component mutex. Return errors rather than aborting.

- [ ] **Step 3: Implement the timekeeper state machine**

Use a mutex-protected state containing the exact snapshot fields in the approved spec. Require three consecutive valid one-second RMC samples for GPS lock. Initialize GPS uncertainty to 500,000 us before hardware characterization. Grow holdover uncertainty at 50 ppm. Persist `rtc_trusted` plus `last_gps_epoch` on first lock and no more than every six hours.

- [ ] **Step 4: Implement step/slew discipline**

When wall time is invalid or initial error exceeds two seconds, call `settimeofday`. While locked, use `adjtime` for smaller corrections and reject discontinuities until five consecutive consistent samples reacquire. Write RTC after initial stable lock and every ten minutes thereafter.

- [ ] **Step 5: Integrate boot and GPS observations**

After WS-C5-28 I2C bus creation, call:

```c
ESP_ERROR_CHECK_WITHOUT_ABORT(cym_timekeeper_init(s_i2c_bus));
```

Replace the RMC one-shot `s_gps_synced` block with a checksum-validated epoch conversion and:

```c
cym_timekeeper_note_gps_present(true);
cym_timekeeper_observe_gps_utc(epoch, esp_timer_get_time());
```

Do not change location/speed handling for other features.

- [ ] **Step 6: Run focused contract and compile WS-C5-28**

```bash
python3 -m unittest -v tests.test_ws_c5_28_ntp_clock_contract
. /home/dev/esp/esp-idf/export.sh
./scripts/build.sh ws-c5-28
```

Expected: component compiles; UI-specific contract assertions remain RED until later tasks.

- [ ] **Step 7: Commit the timekeeper**

```bash
git add ESP32C5/components/cym_timekeeper ESP32C5/components/board_hal/include/boards/ws_c5_28.h ESP32C5/main/CMakeLists.txt ESP32C5/main/main.c
git commit -m "feat(ws-c5-28): discipline RTC from GPS"
```

### Task 3: Implement the isolated NTP responder

**Files:**
- Create: `ESP32C5/components/cym_timekeeper/include/cym_ntp_server.h`
- Create: `ESP32C5/components/cym_timekeeper/cym_ntp_server.c`
- Modify: `ESP32C5/components/cym_timekeeper/CMakeLists.txt`
- Modify: `tests/test_ws_c5_28_ntp_clock_contract.py`

**Interfaces:**
- Consumes: `cym_timekeeper_snapshot()`.
- Produces:

```c
typedef struct {
    bool running;
    uint32_t valid_requests;
    uint32_t malformed_requests;
    uint32_t rate_limited_requests;
    uint32_t send_failures;
} cym_ntp_server_stats_t;

esp_err_t cym_ntp_server_start(void);
void cym_ntp_server_stop(void);
void cym_ntp_server_get_stats(cym_ntp_server_stats_t *out);
```

- [ ] **Step 1: Extend tests with exact packet requirements**

Require a packed 48-byte packet, NTP epoch offset `2208988800UL`, client mode 3 validation, server mode 4 response, originate echo, network byte order, stratum 1 for GPS/RTC, and leap 3 plus stratum 16 for unsynchronized state.

- [ ] **Step 2: Run the focused test and verify RED**

```bash
python3 -m unittest -v tests.test_ws_c5_28_ntp_clock_contract
```

Expected: NTP packet assertions fail.

- [ ] **Step 3: Implement UDP/123 request/response task**

Use a fixed 48-byte request/response buffer, `recvfrom`, immediate receive timestamp, snapshot read, response population, immediate transmit timestamp, and `sendto`. Bind IPv4 `INADDR_ANY:123`. Support NTP versions 3 and 4 in client mode.

- [ ] **Step 4: Implement quality and rate limiting**

Map GPS to LI 0/stratum 1/`GPS`, trusted RTC holdover to LI 0/stratum 1/`RTC`, and unsynchronized to LI 3/stratum 16/`INIT`. Convert uncertainty to 16.16 root dispersion. Implement a global 8 requests/s bucket with burst 32 and an eight-entry per-source LRU bucket at 2 requests/s with burst 4.

- [ ] **Step 5: Implement bounded lifecycle**

`start` is idempotent, creates one task, and returns bind/task errors. `stop` sets the stop flag, shuts down/closes the socket to wake `recvfrom`, waits boundedly for task exit, and is safe when already stopped.

- [ ] **Step 6: Run test and compile**

```bash
python3 -m unittest -v tests.test_ws_c5_28_ntp_clock_contract
. /home/dev/esp/esp-idf/export.sh
./scripts/build.sh ws-c5-28
```

- [ ] **Step 7: Commit the NTP responder**

```bash
git add ESP32C5/components/cym_timekeeper tests/test_ws_c5_28_ntp_clock_contract.py
git commit -m "feat(ws-c5-28): add bounded NTP responder"
```

### Task 4: Add persistent Clock Settings

**Files:**
- Modify: `ESP32C5/main/main.c` NVS keys/load/save, settings callback, and Settings tile grid
- Modify: `tests/test_ws_c5_28_ntp_clock_contract.py`

**Interfaces:**
- Consumes: `cym_timekeeper_snapshot()`.
- Produces: `g_clock_offset_minutes` (`int16_t`, -720 to +840) and `g_ntp_clock_brightness_pct` (`uint8_t`, 10 to 100), persisted under `clk_offset` and `clk_bright`.

- [ ] **Step 1: Extend tests for board-gated Clock Settings**

Require the tile and callback to be inside `CONFIG_BOARD_WS_C5_28`, exact NVS keys, 15-minute offset range validation, 10-100 brightness validation, Save/Cancel controls, and no PPS GPIO selector.

- [ ] **Step 2: Run the focused test and verify RED**

```bash
python3 -m unittest -v tests.test_ws_c5_28_ntp_clock_contract
```

- [ ] **Step 3: Add NVS defaults and persistence**

Load offset default 0 and brightness default 100. Reject invalid persisted values. Save both in one open/commit/close operation and report errors to the settings screen.

- [ ] **Step 4: Build the Clock Settings screen**

Use `create_function_page_base("Clock Settings")`. Add display offset controls in 15-minute steps, a 10-100 brightness slider, read-only source/RTC/last-sync labels, and Save/Cancel. Do not add a PPS selector in version one.

- [ ] **Step 5: Add the board-gated Settings tile**

Add `Clock` under `#if defined(CONFIG_BOARD_WS_C5_28)` in `show_settings_screen` and dispatch it in `settings_tile_event_cb`.

- [ ] **Step 6: Run tests and compile all C5 boards**

```bash
python3 -m unittest -v tests.test_ws_c5_28_ntp_clock_contract
. /home/dev/esp/esp-idf/export.sh
./scripts/build.sh ws-c5-28
./scripts/build.sh nm-cyd-c5
```

- [ ] **Step 7: Commit Clock Settings**

```bash
git add ESP32C5/main/main.c tests/test_ws_c5_28_ntp_clock_contract.py
git commit -m "feat(ws-c5-28): add Clock settings"
```

### Task 5: Build the exclusive NTP Clock dashboard and network lifecycle

**Files:**
- Modify: `ESP32C5/main/main.c`
- Modify: `ESP32C5/main/CMakeLists.txt`
- Modify: `tests/test_ws_c5_28_ntp_clock_contract.py`

**Interfaces:**
- Consumes: saved Wi-Fi credentials, `cym_timekeeper_snapshot`, `cym_ntp_server_*`, `set_backlight_percent`, and existing screen stop hooks.
- Produces: `show_ntp_clock_screen()` and idempotent `ntp_clock_stop()`.

- [ ] **Step 1: Extend contracts for lifecycle and visible dashboard fields**

Require `g_screen_stop_fn = ntp_clock_stop`, 1 Hz UI timer, `DHCP IP`, `cym-ntp.local`, `UDP/123`, source/age/uncertainty/request labels, an Exit control, no dashboard offset/brightness controls, and no auto-dim while `s_ntp_clock_active`.

- [ ] **Step 2: Run the focused test and verify RED**

```bash
python3 -m unittest -v tests.test_ws_c5_28_ntp_clock_contract
```

- [ ] **Step 3: Add the dashboard UI**

Create one LVGL object tree for the 240x320 portrait dashboard. Update labels at 1 Hz without rebuilding. Format display time by adding `g_clock_offset_minutes` to a copy of UTC; never change `TZ`, RTC, system time, or NTP output.

- [ ] **Step 4: Add bounded Wi-Fi startup task**

Copy saved credentials into task-owned fixed buffers, acquire STA mode through `ensure_wifi_mode`, call `esp_wifi_connect`, and poll DHCP for at most 15 seconds. Communicate status to LVGL through shared flags/state only; the worker does not call LVGL.

- [ ] **Step 5: Start mDNS and NTP after DHCP**

Initialize mDNS, set hostname `cym-ntp`, add `_ntp._udp` service on port 123, then call `cym_ntp_server_start`. Treat mDNS failure as nonfatal and UDP bind failure as offline.

- [ ] **Step 6: Disable automatic dimming only while active**

In the screen idle timer, return without dimming while `s_ntp_clock_active`. On entry save general brightness and apply NTP brightness. On stop restore general brightness and normal idle behavior.

- [ ] **Step 7: Implement idempotent teardown**

Delete UI timer, request startup-task cancellation, stop NTP, remove/free mDNS state, disconnect Wi-Fi, clear LVGL pointers/flags, restore brightness, and tolerate repeated stop calls.

- [ ] **Step 8: Run tests and compile WS-C5-28**

```bash
python3 -m unittest -v tests.test_ws_c5_28_ntp_clock_contract
. /home/dev/esp/esp-idf/export.sh
./scripts/build.sh ws-c5-28
```

- [ ] **Step 9: Commit the dashboard**

```bash
git add ESP32C5/main/main.c ESP32C5/main/CMakeLists.txt tests/test_ws_c5_28_ntp_clock_contract.py
git commit -m "feat(ws-c5-28): add NTP Clock dashboard"
```

### Task 6: Wire Classic and Modern navigation and documentation

**Files:**
- Modify: `ESP32C5/main/main.c`
- Modify: `README.md`
- Create: `docs/features/ws-c5-28-ntp-clock.md`
- Modify: `tests/test_ws_c5_28_ntp_clock_contract.py`

**Interfaces:**
- Consumes: `show_ntp_clock_screen()` and `show_clock_settings_screen()`.
- Produces: Classic `WiFi -> NTP Clock`, Modern `Tools & System -> NTP Clock`, and `Settings -> Clock` documentation.

- [ ] **Step 1: Extend navigation contracts**

Require one Classic tile in `show_wifi_menu_screen`, one Modern tile in `show_cat_tools`, both under `CONFIG_BOARD_WS_C5_28`, and Back returning to their distinct parent screens through the existing nav stack.

- [ ] **Step 2: Run the focused test and verify RED**

```bash
python3 -m unittest -v tests.test_ws_c5_28_ntp_clock_contract
```

- [ ] **Step 3: Add both operating-tool entries**

Classic uses `main_tile_event_cb` key `NTP Clock` from the WiFi menu. Modern uses a small callback that launches the same screen and sets the Back target to `show_cat_tools` if required by the current stack behavior.

- [ ] **Step 4: Document operation and honesty boundary**

Document saved Wi-Fi prerequisites, DHCP IP display, `cym-ntp.local`, client configuration, UTC-only NTP/RTC behavior, display offset, no automatic dimming, RTC holdover, UART-only uncertainty, and deferred PPS.

- [ ] **Step 5: Run all Python contracts**

```bash
python3 -m unittest discover -s tests -v
```

Expected: all existing and new contracts pass.

- [ ] **Step 6: Commit navigation and docs**

```bash
git add ESP32C5/main/main.c README.md docs/features/ws-c5-28-ntp-clock.md tests/test_ws_c5_28_ntp_clock_contract.py
git commit -m "docs(ws-c5-28): document NTP Clock operation"
```

### Task 7: Version, build, package, verify, and push the development cycle

**Files:**
- Modify: `ESP32C5/CMakeLists.txt`
- Modify: generated board memory-budget/package outputs produced by the canonical build
- Verify: all tracked implementation and documentation files

**Interfaces:**
- Consumes: completed Tasks 1-6.
- Produces: green `v2.15.35` packages for every released board and a pushed `Jimgat_Dev` cycle.

- [ ] **Step 1: Run pre-version verification**

```bash
git diff --check
python3 -m unittest discover -s tests -v
```

- [ ] **Step 2: Bump only the canonical project version**

Change:

```cmake
set(PROJECT_VER "v2.15.34")
```

to:

```cmake
set(PROJECT_VER "v2.15.35")
```

- [ ] **Step 3: Run the canonical all-board build gate**

```bash
. /home/dev/esp/esp-idf/export.sh
make all-boards
```

Expected green boards:

- NM-CYD-C5
- WS-C5-28
- CYD-2432S028
- Hosyond ES3C35P

- [ ] **Step 4: Re-run contracts after generated-output changes**

```bash
python3 -m unittest discover -s tests -v
git diff --check
```

- [ ] **Step 5: Verify packaged versions and hashes programmatically**

Read each built app descriptor or build log to prove `v2.15.35`, then run:

```bash
sha256sum ESP32C5/binaries-esp32c5/*full.bin \
          ESP32C5/binaries-ws-c5-28/*full.bin \
          ESP32/binaries-cyd2usb/*full.bin \
          ESP32S3/binaries-hosyond-s3-35/*full.bin
```

Record exact package paths and hashes.

- [ ] **Step 6: Commit the cycle without AI attribution**

```bash
git add ESP32C5/CMakeLists.txt ESP32C5/binaries-esp32c5 ESP32C5/binaries-ws-c5-28 ESP32/binaries-cyd2usb ESP32S3/binaries-hosyond-s3-35 ESP32C5/docs ESP32/docs ESP32S3/docs
git commit -m "feat(ws-c5-28): add GPS-disciplined NTP Clock"
```

- [ ] **Step 7: Push and verify the exact remote head**

```bash
git push origin Jimgat_Dev
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git ls-remote origin refs/heads/Jimgat_Dev | cut -f1)
test "$LOCAL" = "$REMOTE"
```

- [ ] **Step 8: Prepare the morning hardware-test handoff**

Report:

- development commit;
- direct raw URL for the WS-C5-28 full image;
- SHA-256;
- flash offset `0x0000`;
- exact menu paths;
- expected screen states and NTP client query commands; and
- explicit statement that physical timing accuracy remains unqualified until Jim tests it.
