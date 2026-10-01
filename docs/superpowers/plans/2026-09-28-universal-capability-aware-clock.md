# Universal Capability-Aware Clock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the WS-C5-28-only NTP Clock with a universal, capability-aware Clock on all four released CYM boards while preserving truthful source selection, strictly offline Display Only behavior, bounded Client NTP synchronization, honest AP NTP responses, and board-specific reliability estimates.

**Architecture:** Extend the existing `cym_timekeeper` and `cym_ntp_server` shared components rather than creating per-board implementations. Hardware differences are declared once in `board_hal` capability profiles; the shared C5 `main.c` supplies one Clock chooser/dashboard and one network lifecycle to ESP32, ESP32-C5, and ESP32-S3 builds. Timekeeper snapshots carry source, reliability, source age, and estimated uncertainty, while UI code only renders those immutable facts.

**Tech Stack:** ESP-IDF C, FreeRTOS, LVGL, lwIP UDP/SNTP, NVS, ESP-IDF board components, Python `unittest` source/behavior contracts, `scripts/build.sh`, Git/GitHub.

## Global Constraints

- Execute every source edit, test, build, package, commit, and push on ESP32-Dev as `dev` in `/home/dev/projects/CYM-NM28C5-jarvis-ws35-docs`.
- Keep branch `Jimgat_Dev`; fetch and compare `origin/Jimgat_Dev` before implementation.
- Preserve unrelated uncommitted and untracked work; never reset, clean, stash, overwrite, or stage unrelated paths.
- Check active build/editor processes before editing. The known `claude` process in `/home/dev/projects/CYM-NM28C5` is a separate checkout and must not be disturbed.
- The approved design is `docs/superpowers/specs/2026-09-28-universal-capability-aware-clock-design.md` at commit `aca35f94be53108c0660e47703ec954e57f5b747`.
- Use one shared release version: `v2.15.38` (patch follows `v2.15.37`; no automatic minor increment).
- Preserve the completed WS-C5-28 public-NTP, RTC-repair, GPS-discipline, and AP-NTP behavior from `v2.15.37`.
- Do not add AI/model/agent attribution to commits. Preserve legitimate human authorship and human co-developer credit.
- Classic and Modern navigation are separate contracts and must both be tested.
- Do not claim physical timing accuracy, RTC retention, GPS takeover, AP interoperability, or long-duration holdover from compilation.
- Do not push until focused contracts, the full Python suite, `git diff --check`, all four canonical builds, and image-version checks pass.
- Final delivery must include direct GitHub raw full-image URL, SHA-256, size, and offset `0x0000` for WS-C5-28, plus hashes for the other three release images.

## File Map

- `ESP32C5/components/board_hal/include/board_hal.h`: normalized timing-capability fallbacks consumed by shared code.
- `ESP32C5/components/board_hal/include/boards/ws_c5_28.h`: RTC/GPS and WS-C5-28 timing estimates.
- `ESP32C5/components/board_hal/include/boards/nm_cyd_c5.h`: GPS and C5 RTOS timing estimates.
- `ESP32C5/components/board_hal/include/boards/cyd2usb.h`: RTC-less/GPS-less ESP32 timing estimates.
- `ESP32C5/components/board_hal/include/boards/hosyond_s3_35.h`: GPS and S3 RTOS timing estimates.
- `ESP32C5/components/cym_timekeeper/include/cym_timekeeper.h`: source/reliability snapshot API.
- `ESP32C5/components/cym_timekeeper/cym_timekeeper.c`: trust, source transitions, RTOS/RTC holdover, and uncertainty calculations.
- `ESP32C5/components/cym_timekeeper/cym_ntp_server.c`: source-to-NTP quality mapping, including RTOS holdover and honest unsynchronized responses.
- `ESP32C5/main/main.c`: shared initialization, GPS observation, universal navigation, chooser, dashboard, settings, and network lifecycle.
- `ESP32/main/CMakeLists.txt`, `ESP32C5/main/CMakeLists.txt`, `ESP32S3/main/CMakeLists.txt`: make `cym_timekeeper` available to each released SoC application.
- `tests/test_universal_clock_contract.py`: new cross-board contracts.
- `tests/test_ws_c5_28_ntp_clock_contract.py`: preserve/update WS-specific regression contracts and cycle version.
- `docs/hardware/universal-clock.md`: operator-facing behavior, board matrix, and estimate disclaimer.
- `docs/hardware/ws-c5-28-ntp-clock.md`: point WS-specific details to the universal Clock contract without losing RTC wiring/recovery detail.
- Project `CMakeLists.txt` files and four manifest files: shared `v2.15.38` release version.

---

### Task 1: Lock the Approved Cross-Board Contract in Failing Tests

**Files:**
- Create: `tests/test_universal_clock_contract.py`
- Modify: `tests/test_ws_c5_28_ntp_clock_contract.py`
- Modify: `docs/superpowers/specs/2026-09-28-universal-capability-aware-clock-design.md`

**Interfaces:**
- Consumes: approved design and existing `v2.15.37` WS-C5-28 source contracts.
- Produces: named failing contracts for board profiles, timekeeper snapshots, navigation, chooser modes, offline Display Only, network behavior, and release version.

- [ ] **Step 1: Mark the specification approved without changing its technical content**

Change the header to:

```markdown
**Status:** Approved for implementation
**Approved by:** Jim Gatwood
**Date approved:** 2026-09-28
```

- [ ] **Step 2: Add cross-board capability contracts**

Create `tests/test_universal_clock_contract.py` with repository reads for the four board headers, `board_hal.h`, timekeeper header/source, NTP source, shared `main.c`, all three main-component CMake files, and all version/manifests. Assert these exact normalized symbols:

```python
PROFILE_SYMBOLS = (
    "BOARD_TIME_HAS_RTC",
    "BOARD_TIME_HAS_GPS_UART",
    "BOARD_TIME_RTC_DRIFT_PPM",
    "BOARD_TIME_RTOS_DRIFT_PPM",
    "BOARD_TIME_GPS_UNCERTAINTY_US",
    "BOARD_TIME_NTP_UNCERTAINTY_US",
    "BOARD_TIME_ESTIMATE_CHARACTERIZED",
)
```

Assert explicit profiles:

```python
EXPECTED = {
    "ws_c5_28.h": {"rtc": 1, "gps": 1, "rtc_ppm": 50, "rtos_ppm": 100, "gps_us": 500000, "ntp_us": 250000},
    "nm_cyd_c5.h": {"rtc": 0, "gps": 1, "rtc_ppm": 0, "rtos_ppm": 100, "gps_us": 500000, "ntp_us": 250000},
    "cyd2usb.h": {"rtc": 0, "gps": 0, "rtc_ppm": 0, "rtos_ppm": 150, "gps_us": 0, "ntp_us": 250000},
    "hosyond_s3_35.h": {"rtc": 0, "gps": 1, "rtc_ppm": 0, "rtos_ppm": 100, "gps_us": 500000, "ntp_us": 250000},
}
```

Assert all are uncharacterized (`BOARD_TIME_ESTIMATE_CHARACTERIZED 0`), only WS-C5-28 declares `BOARD_RTC_I2C_ADDR`, and CYD2USB retains `BOARD_GPS_TX_GPIO -1` / `BOARD_GPS_RX_GPIO -1`.

- [ ] **Step 3: Add timekeeper and NTP quality contracts**

Assert the public API contains:

```c
typedef enum {
    CYM_TIME_UNSYNCED = 0,
    CYM_TIME_GPS_ACQUIRING,
    CYM_TIME_GPS_LOCKED,
    CYM_TIME_NETWORK_SYNC,
    CYM_TIME_RTC_HOLDOVER,
    CYM_TIME_RTOS_HOLDOVER,
} cym_time_source_t;

typedef enum {
    CYM_TIME_RELIABILITY_UNTRUSTED = 0,
    CYM_TIME_RELIABILITY_DEGRADED,
    CYM_TIME_RELIABILITY_HOLDOVER,
    CYM_TIME_RELIABILITY_GOOD,
    CYM_TIME_RELIABILITY_EXCELLENT,
} cym_time_reliability_t;
```

Assert `cym_time_snapshot_t` adds `reliability`, `has_rtc`, `has_gps_uart`, and `estimate_characterized`; the source includes board-profile drift symbols and monotonic uncertainty growth; `cym_timekeeper_reliability_name()` exists; and the NTP responder maps `CYM_TIME_RTOS_HOLDOVER` to a synchronized response while preserving leap 3/stratum 16 for invalid snapshots.

- [ ] **Step 4: Add navigation, chooser, and offline-mode contracts**

Extract the Classic and Modern menu functions separately and assert each contains an unconditional `Clock` tile without `CONFIG_BOARD_WS_C5_28`. Extract the chooser block and assert `Display Only`, `Client NTP`, `AP NTP`, and `Cancel` occur exactly as visible choices.

Extract `clock_mode_display_cb()` through the next callback and assert it calls only the Clock screen path; specifically reject `esp_wifi_`, `esp_netif_`, `esp_sntp_`, `mdns_`, and `cym_ntp_server_start` from that callback.

Assert the Client path contains `NTP_PUBLIC_SYNC_TIMEOUT_MS 5000`, DHCP credential continuation, and `cym_timekeeper_observe_network_utc`; assert AP mode starts WPA2/AP/UDP service without calling public SNTP; assert no NVS key persists a Clock mode.

- [ ] **Step 5: Add settings/dashboard and build-integration contracts**

Assert Clock settings are no longer wrapped in a WS-only preprocessor guard. Assert dashboard strings include source, reliability, estimated uncertainty, source age, `RTC: not fitted`, `GPS: not supported`, and `estimated (unqualified)`. Assert all three application components require `cym_timekeeper`.

Assert all three project files and four manifests identify `v2.15.38` so the test remains red until the release task.

- [ ] **Step 6: Run focused tests and prove the intended red state**

Run:

```bash
python3 -m unittest -v tests.test_universal_clock_contract \
  tests.test_ws_c5_28_ntp_clock_contract
```

Expected: new universal contracts fail for missing profiles, RTOS holdover/reliability fields, universal navigation, four-way chooser, and `v2.15.38`; existing WS regression contracts continue passing except assertions deliberately generalized by this task.

- [ ] **Step 7: Commit the approved spec and red contracts**

```bash
git add \
  docs/superpowers/specs/2026-09-28-universal-capability-aware-clock-design.md \
  tests/test_universal_clock_contract.py \
  tests/test_ws_c5_28_ntp_clock_contract.py
git commit -m "test(clock): define universal clock contracts"
```

Do not push.

---

### Task 2: Add Board Timing Profiles and Capability-Aware Timekeeper

**Files:**
- Modify: `ESP32C5/components/board_hal/include/board_hal.h`
- Modify: `ESP32C5/components/board_hal/include/boards/ws_c5_28.h`
- Modify: `ESP32C5/components/board_hal/include/boards/nm_cyd_c5.h`
- Modify: `ESP32C5/components/board_hal/include/boards/cyd2usb.h`
- Modify: `ESP32C5/components/board_hal/include/boards/hosyond_s3_35.h`
- Modify: `ESP32C5/components/cym_timekeeper/include/cym_timekeeper.h`
- Modify: `ESP32C5/components/cym_timekeeper/cym_timekeeper.c`
- Modify: `ESP32C5/components/cym_timekeeper/cym_ntp_server.c`

**Interfaces:**
- Consumes: capability symbols and enums fixed by Task 1.
- Produces: `cym_timekeeper_init()`, GPS/network observation, truthful RTC/RTOS holdover, immutable reliability snapshots, and NTP quality mapping for every board.

- [ ] **Step 1: Define explicit timing profiles in each released board header**

Add the seven `BOARD_TIME_*` symbols using the exact Task 1 values. Keep WS-C5-28 as the sole RTC board. Do not alter existing GPIO assignments or GPS UART pin maps.

- [ ] **Step 2: Add safe normalized fallbacks in `board_hal.h`**

After board dispatch, define absent capabilities to zero only when a board header omitted them. Include compile-time checks that reject RTC capability without `BOARD_RTC_I2C_ADDR`, GPS capability without valid GPS pins, negative drift, and a zero public-NTP uncertainty.

- [ ] **Step 3: Extend the snapshot API**

Add `CYM_TIME_RTOS_HOLDOVER`, `cym_time_reliability_t`, snapshot fields, and:

```c
const char *cym_timekeeper_reliability_name(cym_time_reliability_t reliability);
```

Retain all existing APIs so WS-C5-28 callers do not regress.

- [ ] **Step 4: Replace global drift assumptions with board-profile calculations**

Implement a saturating helper:

```c
static uint32_t grow_uncertainty(uint32_t base_us,
                                 uint64_t elapsed_us,
                                 uint32_t drift_ppm);
```

Use RTC drift only for `RTC_HOLDOVER`; use RTOS drift for `NETWORK_SYNC` aging and `RTOS_HOLDOVER`; use GPS base uncertainty for a live qualified GPS source. Never infer trust from `time(NULL)` alone.

- [ ] **Step 5: Preserve disciplined RTOS time as in-boot holdover**

When GPS disappears without a trusted RTC, transition to `CYM_TIME_RTOS_HOLDOVER` instead of `UNSYNCED`. A public-NTP sample establishes RTOS trust for the current boot. `cym_timekeeper_init(NULL)` begins untrusted and must not load RTOS-only trust from NVS.

When a trusted RTC exists, RTC holdover remains preferred over RTOS holdover. A later qualified GPS lock supersedes network or holdover sources. A network sample must continue rejecting displacement of `GPS_LOCKED`.

- [ ] **Step 6: Derive reliability from current source and uncertainty**

Implement one internal pure function using these boundaries:

```c
GPS_LOCKED + RTC present + uncertainty <= 1000000  -> EXCELLENT
GPS_LOCKED without RTC and uncertainty <= 2000000 -> GOOD
NETWORK_SYNC and uncertainty <= 2000000            -> GOOD
RTC_HOLDOVER                                        -> HOLDOVER
RTOS_HOLDOVER or valid source above its threshold  -> DEGRADED
invalid/UNSYNCED/GPS_ACQUIRING without trusted time -> UNTRUSTED
```

Populate board-capability and estimate-characterization fields in every snapshot.

- [ ] **Step 7: Extend NTP source mapping honestly**

Treat a valid `CYM_TIME_RTOS_HOLDOVER` snapshot as synchronized secondary time, with root dispersion from `uncertainty_us`. Keep `NETWORK_SYNC` stratum 2 and GPS stratum 1. Keep invalid/UNSYNCED/GPS-acquiring-without-trust at leap 3, stratum 16.

- [ ] **Step 8: Run focused component contracts**

```bash
python3 -m unittest -v \
  tests.test_universal_clock_contract.BoardProfileContract \
  tests.test_universal_clock_contract.TimekeeperContract \
  tests.test_universal_clock_contract.NTPQualityContract \
  tests.test_ws_c5_28_ntp_clock_contract.TimekeeperComponentContract \
  tests.test_ws_c5_28_ntp_clock_contract.NTPServerComponentContract
```

Expected: PASS.

- [ ] **Step 9: Commit the board profiles and timekeeper**

```bash
git add ESP32C5/components/board_hal ESP32C5/components/cym_timekeeper
git commit -m "feat(clock): add capability-aware time reliability"
```

Do not push.

---

### Task 3: Initialize the Shared Timekeeper and Feed GPS on Every Capable Board

**Files:**
- Modify: `ESP32/main/CMakeLists.txt`
- Modify: `ESP32C5/main/CMakeLists.txt`
- Modify: `ESP32S3/main/CMakeLists.txt`
- Modify: `ESP32C5/main/main.c`

**Interfaces:**
- Consumes: Task 2 timekeeper API and board capabilities.
- Produces: one initialized timekeeper per boot, null-bus operation on RTC-less boards, and GPS observations only on declared GPS UARTs.

- [ ] **Step 1: Link `cym_timekeeper` from all application components**

Add `cym_timekeeper` to the application component dependency list for ESP32, ESP32-C5, and ESP32-S3. Keep `esp_netif` available for the shared Client NTP path.

- [ ] **Step 2: Generalize initialization without probing absent RTC hardware**

Replace the WS-only timekeeper init block with:

```c
#if BOARD_TIME_HAS_RTC
    init_i2c_bus();
    ESP_ERROR_CHECK_WITHOUT_ABORT(cym_timekeeper_init(s_i2c_bus));
#else
    ESP_ERROR_CHECK_WITHOUT_ABORT(cym_timekeeper_init(NULL));
#endif
```

Do not duplicate `init_i2c_bus()` on WS-C5-28. Other board-specific I2C/display initialization remains unchanged.

- [ ] **Step 3: Generalize GPS time observations using capability symbols**

Replace `CONFIG_BOARD_WS_C5_28` guards around `cym_timekeeper_note_gps_present()` and `cym_timekeeper_observe_gps_utc()` with `#if BOARD_TIME_HAS_GPS_UART`. Keep the existing checksum validation and three-sample qualification. CYD2USB originally disabled GPS; the v2.15.48 capability update supersedes that constraint and routes external GPS through its UART expansion JST.

- [ ] **Step 4: Run integration contracts and compile one target per SoC**

```bash
python3 -m unittest -v tests.test_universal_clock_contract.BuildIntegrationContract
./scripts/build.sh nm-cyd-c5
./scripts/build.sh cyd-2432s028
./scripts/build.sh hosyond-s3-35
```

Expected: contracts and all three builds pass. These are compile checks, not timing validation.

- [ ] **Step 5: Commit shared initialization**

```bash
git add ESP32/main/CMakeLists.txt ESP32C5/main/CMakeLists.txt \
  ESP32S3/main/CMakeLists.txt ESP32C5/main/main.c
git commit -m "feat(clock): initialize shared timekeeper on all boards"
```

Do not push.

---

### Task 4: Replace NTP Clock Navigation with the Universal Four-Mode Clock

**Files:**
- Modify: `ESP32C5/main/main.c`
- Modify: `tests/test_ws_c5_28_ntp_clock_contract.py`

**Interfaces:**
- Consumes: existing navigation callbacks and Task 3 initialized timekeeper.
- Produces: unconditional Classic/Modern `Clock` entries and a non-persistent `clock_mode_t` chooser.

- [ ] **Step 1: Define universal mode state**

Use:

```c
typedef enum {
    CLOCK_MODE_NONE = 0,
    CLOCK_MODE_DISPLAY_ONLY,
    CLOCK_MODE_CLIENT_NTP,
    CLOCK_MODE_AP_NTP,
} clock_mode_t;
```

The default and post-exit state are `CLOCK_MODE_NONE`; do not add an NVS key for the mode.

- [ ] **Step 2: Make Classic and Modern Clock tiles unconditional**

Use visible label `Clock` and route keys `Clock Classic` / `Clock Modern`. Remove the WS-only guards from both menu functions and their routing callbacks. Preserve return destinations: Classic returns Home; Modern returns Tools & System.

- [ ] **Step 3: Build the four-option chooser**

Rename the old NTP mode popup to Clock mode terminology, size it for four controls, and wire callbacks in order:

```c
Display Only
Client NTP
AP NTP
Cancel
```

Display Only sets `CLOCK_MODE_DISPLAY_ONLY` and immediately opens the dashboard without invoking Wi-Fi, netif, mDNS, SNTP, or the NTP server. Client NTP retains the existing credential/DHCP continuation. AP NTP retains explicit AP setup. Cancel only deletes the chooser.

- [ ] **Step 4: Eliminate stale network inheritance**

Before opening Display Only, call an idempotent Clock-owned teardown that stops any Clock UDP task/mDNS and removes Clock AP/STA ownership from a prior mode without starting new network work. Keep unrelated global radio lifecycle behavior intact.

- [ ] **Step 5: Generalize pending credential continuation**

Remove WS-only guards around the pending Client NTP continuation in the shared Wi-Fi credential workflow. On DHCP success, resume the Clock screen only when `s_clock_pending_after_wifi` is true.

- [ ] **Step 6: Run navigation and mode tests**

```bash
python3 -m unittest -v \
  tests.test_universal_clock_contract.NavigationContract \
  tests.test_universal_clock_contract.ModeContract \
  tests.test_ws_c5_28_ntp_clock_contract.NTPClockBehaviorContract
```

Expected: PASS after updating WS-specific assertions from `NTP Clock` to universal `Clock` without weakening public-NTP/RTC regression checks.

- [ ] **Step 7: Commit navigation and chooser work**

```bash
git add ESP32C5/main/main.c tests/test_ws_c5_28_ntp_clock_contract.py
git commit -m "feat(clock): add universal four-mode clock entry"
```

Do not push.

---

### Task 5: Generalize the Dashboard and Clock Network Lifecycle

**Files:**
- Modify: `ESP32C5/main/main.c`

**Interfaces:**
- Consumes: `clock_mode_t`, `cym_time_snapshot_t`, existing bounded public SNTP and AP/UDP implementation.
- Produces: one dashboard for Display Only, Client NTP, and AP NTP on all boards.

- [ ] **Step 1: Rename NTP-only UI state to Clock UI state without changing protocol constants**

Rename screen/timer/return/mode variables and functions where their responsibility is now universal. Keep `NTP_PUBLIC_SYNC_TIMEOUT_MS`, `NTP_RTC_REPAIR_THRESHOLD_SEC`, UDP/123, and protocol-specific identifiers named NTP.

- [ ] **Step 2: Render the complete immutable snapshot**

Dashboard update code must display:

```text
Mode
UTC-offset local time and date
Source
Reliability
Estimated uncertainty
Source age
RTC state
GPS state
estimated (unqualified) when applicable
```

Use `cym_timekeeper_source_name()` and `cym_timekeeper_reliability_name()`. Format uncertainty as milliseconds below one second and seconds at/above one second. Apply `g_clock_offset_minutes` only to the displayed timestamp; never feed offset time to the timekeeper or NTP responder.

- [ ] **Step 3: Implement honest capability status**

Render `RTC: not fitted` when `snapshot.has_rtc` is false. Render `GPS: not supported` when `snapshot.has_gps_uart` is false; otherwise distinguish locked, acquiring/present, and not detected. Render `UNSYNCED` and `Untrusted` when no valid snapshot exists.

- [ ] **Step 4: Preserve bounded Client NTP behavior on every board**

After valid DHCP, start local UDP/123 and mDNS, skip public sync only for qualified GPS, wait no longer than approximately five seconds, reject invalid epochs, update the timekeeper/RTOS clock, and request RTC repair only when the snapshot says an RTC exists and it is unavailable/untrusted or at least five seconds wrong.

- [ ] **Step 5: Preserve offline AP NTP behavior on every board**

Start WPA2 AP and local responder without public SNTP. Show SSID, protected password, and `192.168.4.1`. If the timekeeper is untrusted, leave the responder running diagnostically; Task 2 guarantees leap 3/stratum 16 responses.

- [ ] **Step 6: Make teardown mode-aware, bounded, and idempotent**

Display Only teardown removes only the timer/UI brightness override. Client/AP teardown stops UDP and mDNS, bounds worker shutdown, restores radio state, clears mode/pending state, and restores prior brightness. Repeated teardown must be safe.

- [ ] **Step 7: Run focused Clock behavior tests and build WS-C5-28**

```bash
python3 -m unittest -v \
  tests.test_universal_clock_contract.DashboardContract \
  tests.test_universal_clock_contract.NetworkLifecycleContract \
  tests.test_ws_c5_28_ntp_clock_contract
./scripts/build.sh ws-c5-28
```

Expected: all focused tests and the WS-C5-28 build pass.

- [ ] **Step 8: Commit the dashboard and network lifecycle**

```bash
git add ESP32C5/main/main.c
git commit -m "feat(clock): share dashboard and NTP lifecycle"
```

Do not push.

---

### Task 6: Make Clock Settings Universal and Document Operator Behavior

**Files:**
- Modify: `ESP32C5/main/main.c`
- Create: `docs/hardware/universal-clock.md`
- Modify: `docs/hardware/ws-c5-28-ntp-clock.md`

**Interfaces:**
- Consumes: universal dashboard and existing `clk_offset` / `clk_bright` settings.
- Produces: settings access on every released board and source-grounded operator documentation.

- [ ] **Step 1: Remove WS-only guards from Clock settings persistence and navigation**

Load/save `clk_offset` and `clk_bright` on every board. Keep offset bounds `-720..840` minutes and Clock brightness `10..100`. The values affect the Clock display only; `settimeofday()`, RTC writes, and NTP timestamps remain UTC.

- [ ] **Step 2: Keep Clock settings visible for every board**

Expose `Settings -> Clock` unconditionally for released builds. Retain Save and Cancel behavior and existing return destination.

- [ ] **Step 3: Write the universal operator manual**

Document the four choices, expected dashboard output, strict Display Only offline contract, Client credential flow and five-second pool bound, AP address/credentials display, reliability vocabulary, all four board capability profiles, and the exact disclaimer:

```text
Timing values are conservative uncharacterized engineering estimates, not measured accuracy.
```

Include a copy-paste validation section listing what an operator should select and what status should appear for RTC-fitted, GPS-only, NTP-only, and no-source cases.

- [ ] **Step 4: Update the WS-C5-28 hardware document**

Preserve PCF85063A address, GPS pins, UTC handling, five-second RTC correction threshold, and AP behavior. Replace WS-only navigation wording with a link to the universal Clock manual.

- [ ] **Step 5: Run documentation/settings contracts**

```bash
python3 -m unittest -v \
  tests.test_universal_clock_contract.SettingsContract \
  tests.test_universal_clock_contract.DocumentationContract
git diff --check
```

Expected: PASS.

- [ ] **Step 6: Commit settings and documentation**

```bash
git add ESP32C5/main/main.c docs/hardware/universal-clock.md \
  docs/hardware/ws-c5-28-ntp-clock.md
git commit -m "docs(clock): document universal timing behavior"
```

Do not push.

---

### Task 7: Complete the `v2.15.38` Four-Board Release Cycle

**Files:**
- Modify: `ESP32/CMakeLists.txt`
- Modify: `ESP32C5/CMakeLists.txt`
- Modify: `ESP32S3/CMakeLists.txt`
- Modify: `ESP32/docs/manifest.cyd-2432s028.json`
- Modify: `ESP32C5/docs/manifest.json`
- Modify: `ESP32C5/docs/manifest.ws-c5-28.json`
- Modify: `ESP32S3/docs/manifest.hosyond-s3-35.json`
- Modify: generated per-board memory-budget documents produced by canonical builds, if their tracked content changes.

**Interfaces:**
- Consumes: all feature tasks.
- Produces: tested, packaged, committed, pushed, remotely verified `v2.15.38` firmware artifacts.

- [ ] **Step 1: Bump all source and manifest versions together**

Set all three `PROJECT_VER` values and all four manifest versions to `v2.15.38`. Do not change major/minor values.

- [ ] **Step 2: Run focused and complete contract suites**

```bash
python3 -m unittest -v tests.test_universal_clock_contract \
  tests.test_ws_c5_28_ntp_clock_contract
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: every focused and full-suite test passes. Record exact totals from tool output.

- [ ] **Step 3: Run repository hygiene checks**

```bash
git diff --check
git status --short
git diff --stat
```

Verify only intended paths and canonical build-generated tracked files are present. Remove only known generated `tests/__pycache__`; do not touch unrelated work.

- [ ] **Step 4: Build and package all four canonical targets sequentially**

Use the canonical wrapper and separate logs:

```bash
./scripts/build.sh ws-c5-28
./scripts/build.sh nm-cyd-c5
./scripts/build.sh cyd-2432s028
./scripts/build.sh hosyond-s3-35
```

Expected: all four return zero and produce their board-specific application and merged full images. If a command times out, inspect the process and artifacts before retrying.

- [ ] **Step 5: Independently verify versions in application and merged images**

For each board, inspect both packaged application `.bin` and full image for `v2.15.38`; verify expected artifact names and nonzero sizes. Compilation alone is insufficient.

- [ ] **Step 6: Compute local SHA-256 and sizes programmatically**

Use `sha256sum` and `stat -c %s` for:

```text
ESP32C5/binaries-ws-c5-28/CYM-WS-C5-28-full.bin
ESP32C5/binaries-esp32c5/CYM-NM28C5-full.bin
ESP32/binaries-cyd-2432s028/CYM-CYD-2432S028-full.bin
ESP32S3/binaries-hosyond-s3-35/CYM-hosyond-s3-35-full.bin
```

If the actual canonical NM/S3 filename differs, use the filename emitted by `scripts/build.sh` and record it exactly rather than guessing.

- [ ] **Step 7: Commit the release without AI attribution**

```bash
git add <only intended source, tests, docs, manifests, and tracked build outputs>
git diff --cached --check
git commit -m "feat(clock): release universal clock v2.15.38"
```

Inspect `git show --format=fuller --stat HEAD` and ensure no AI/model/agent attribution trailer exists.

- [ ] **Step 8: Push and verify the exact remote commit**

```bash
git push origin Jimgat_Dev
git fetch origin Jimgat_Dev
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/Jimgat_Dev)"
git status --short
```

Expected: local/remote heads match and the worktree is clean.

- [ ] **Step 9: Verify remote raw artifacts byte-for-byte**

Download each GitHub raw full image from branch `Jimgat_Dev`, require HTTP 200, and compare remote SHA-256 and size to the corresponding local artifact. Do not report a release complete if any comparison differs.

- [ ] **Step 10: Deliver exact firmware details**

Report:

```text
Version: v2.15.38
Commit: <verified 40-character commit>
WS-C5-28 raw URL: <verified URL>
SHA-256: <verified hash>
Size: <verified bytes>
Flash offset: 0x0000
NM-CYD-C5 SHA-256: <verified hash>
CYD-2432S028 SHA-256: <verified hash>
Hosyond ES3C35P SHA-256: <verified hash>
```

Also report exact focused/full test totals and four-board build results. State explicitly that build verification did not physically characterize timing accuracy or validate hardware source transitions.
