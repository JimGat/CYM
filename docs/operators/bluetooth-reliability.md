# Bluetooth reliability candidate v3.0.31

Development candidate only. Stable remains v3.0.27. Host/build success is not hardware acceptance or recovered RF reception.

## v3.0.31 repair and diagnostic candidate

The higher-priority scan worker waits at least one RTOS tick for handle publication (not a 1 ms conversion that becomes zero ticks at 100 Hz). Dynamic internal 4096-byte scan stack, priorities, affinity and global tick rates are unchanged. Reproductions execute actual creator and worker functions with immediate/deferred preemption, create failure, early cancel, start error and cancel retry at 100/1000 Hz. A same-core immediate schedule is the starvation worst case on single- and multi-core targets, not an emulation of FreeRTOS/SMP.

Failed host creation/sync now releases only the not-yet-admitted Chameleon token, then cooperatively joins or retains the host while keeping transition admission closed. A later acquisition cleans a retained port before publishing a token. Active scans, Wardrive direct-GAP lifetime, other transitions and terminal deinit failures reject admission. A live Chameleon token still spans discovery through disconnect drain. Host timeout or SDK deinit failure never authorizes freeing a live resource. No intentional background is disabled to make a retry pass.

Scan and Select has an outcome independent of result count/selection: explicit start failure and cancellation stay visible even with stale rows. Successful empty completion still says `No devices found`; a failed start is not an empty successful scan. A completed scan may retain normal selection details. Busy/pending operations remain stop-and-retry UX. Initialization/admission errors are screen-local, survive a queued refresh, and cannot be hidden by a background scan outcome; Rescan retries BLE initialization before starting a worker.

The earlier v3.0.29 capture's USB reset precedes its fresh boot and BLE launch. No post-launch panic/reset tail was supplied. The publication wait defect was introduced later; it cannot explain that older event. A missing next line does not prove a heap query hung. These corrections do not establish a physical root cause.

### Copy-paste diagnostic capture

Use only the board's accepted primary USB console. Never reroute to GPS/JST UART. Check the Hardware page's console status. Classic/HackerBox USB Debug remains a separate opt-in with its physical GPS-unplug interlock; if the console is unavailable, use the Hardware Debug setting rather than changing pins or routing. Two USB connectors are not a reason to connect both simultaneously.

With a working primary console, enter each line followed by Enter:

```
debug status
debug on
debug query
```

These commands are registered in `debug_console.c` and handled by the existing persistent debug setting. Expect `Debug ON persisted; applied immediately` from `debug on`, then `Debug ON` from `debug query`. A persistence failure explicitly reports unchanged state; do not continue as if ON. Enabling/disabling writes the existing debug setting once; stages do not write NVS. Start a complete serial capture before entering Bluetooth -> Scan and Select. Include version/board, startup, the entire scan, operator press times, cancel/return, and any reset plus the NEXT boot. Do not truncate at the last heap line. Keep a locally retained unedited capture; redact device identifiers before sharing publicly. A Web Serial `requestPort` cancellation is a browser event, not proof of a firmware reset.

Expected marker FORMAT (values vary; these are not captured device results):

```
BLE_STAGE: gen=<generation> seq=<sequence> stage=<stage-number> rc=<integer>
BLE_STAGE: previous gen=<generation> seq=<sequence> stage=<stage-number> rc=<integer>
BLE_STAGE: previous=<valid|corrupt|stale-or-unavailable|unavailable> reset=<reason-number> retention=best-effort
```

The existing ESP log prefix contains `BLE_STAGE`; exact timestamp/prefix differs by console. Markers are numeric, contain no advertising/MAC/GPS payload, and are written without logging/allocation in the boundary callback. The main loop prints at most eight retained entries per snapshot, no more than twice per second, outside LVGL. Fast bursts overwrite older entries. A stalled main loop may print nothing until a later boot. Sequence numbers establish order (boot slot dump need not be sorted).

The 140-byte RTC/noinit record has a format tag, generation and per-slot validation. `valid` means compatible checksums and a potentially retaining reset, NOT proof of crash cause or freshness in wall-clock time. Corrupt/stale/unavailable data is not a diagnosis. Power-on, brownout and unknown reset are treated as unavailable. No promise is made that RTC survives power removal, flashing, every watchdog/reset type, or a board-specific reset. Debug OFF neither records nor emits these markers; changing debug generation clears older slots on the next boundary/main-loop poll. Boot consumes/reset-initializes the prior record. Other pre-existing errors/logs may still print with Debug OFF.

Stage map:

| Number | Boundary |
|---|---|
| 1 | Scan and Select UI entry |
| 2 / 4 | Heap diagnostic enter / exit |
| 3 | Heap query: positive rc=before, negative rc=after; absolute ID 1 free, 2 minimum, 3 internal free, 4 internal minimum, 5 PSRAM free, 6 PSRAM minimum, 7 DMA free |
| 5 / 6 | WiFi stop call / return |
| 7 / 8 | WiFi deinit call / return |
| 9 / 10 | NimBLE port init call / return |
| 11 / 12 | NimBLE host task create / return |
| 13 / 14 | Host sync (rc=1 if ignored after stop) / sync timeout |
| 15 / 16 | Scan task create / return |
| 17 / 18 | Worker entry (rc indicates publication pending) / publication observed |
| 19 / 20 | Shared GAP scan start / return |
| 21 / 22 | GAP cancel call / return |
| 23 / 24 | Host stop request / host exit |
| 25 / 26 | Port deinit call / return |
| 27 | Scan and Select UI construction return (not proof of a rendered frame) |

Return codes use the called SDK's convention (FreeRTOS task creation returns `pdPASS`, whereas ESP/GAP success is zero). A before without a matching after narrows the boundary only; capture reset diagnostics before attributing causation. If no earlier slot remains, report that limitation rather than guessing.

When finished, enter:

```
debug off
debug status
```

Confirm OFF; allow the main loop to run. Separately disable Classic USB Debug through its existing Hardware control if enabled for this test. Restore no pins, clocks, partitions or NVS by erasing them.

### Candidate regression matrix

Run the hardware procedures below in Debug OFF and ON, on both Classic and Modern navigation (and both supported display orientations). Record repeated scan/rescan/Back/Home/radio-transition outcomes, not only first entry. Keep a known stable advertiser nearby; repeated zero-report reception remains unresolved even if there is no crash.

| Area | Required acceptance evidence |
|---|---|
| Scan and Select | Ten normal scans; rapid Rescan; error/empty/stale rows; retry; countdown, late names, selection, page and scroll |
| Navigation | Back and Home during scan and after completion, ten reentries each; Classic/Modern and portrait/landscape |
| Radio/neighboring tools | WiFi -> BLE -> WiFi; Locator tracking, Observer, intentional Lookout (explicitly stop it to release ownership), AirTag; Wardrive BLE-only start/stop and pending cleanup; OT dwells |
| Ultra | Discovery vs selection vs deferred connect vs pairing/security vs services vs READY/handshake distinguished; Back/Home/disconnect/reconnect at each stage, preserved bonds |
| Boards/memory | All eight release builds; physical C5 2.8/3.5, Classic/HackerBox legacy BLE 4.2, Pancake and supported S3 variants; no-PSRAM stress |
| Preserved systems | GPS/timekeeping/NTP-first, primary console, WS35 BOOT/GPIO28 GPS, SD 20 MHz, RTA, pins/partitions/display buffers unchanged |

Use the existing Chameleon status and `[CHAM]` diagnostics to distinguish Ultra stages; the shared `BLE_STAGE` ring is not a packet trace or pairing success proof. Host fault tests cover delayed sync/host exit, true deinit failure, competing owners and repeated retries without manually resetting production state. Supported extended and legacy branches are executed. Native LVGL/SDK stubs cannot prove touch geometry, RF, controller pools, SMP timing, USB reset retention or real Ultra interoperability.

Additional executable checks: `python3 -B tests/run_ble_scan_scheduling_host.py`, `python3 -B tests/run_ble_scan_status_host.py`, `python3 -B tests/run_ble_stage_diag_host.py`, plus the existing integration and neighboring suites. Set owned `CYM_TEST_OUT`/`TMPDIR` and `PYTHONDONTWRITEBYTECODE=1` as for the checks below.

## Implemented scope

The worker owns GAP cancellation. A delayed/cancel-failed worker retains its reservation; Rescan cannot clear its results or start a successor before quiescence. Pending stops ask for a retry rather than forcibly deleting a task. Scan and shared Locator, Observer, Lookout, AirTag and OT dwell consumers respect ownership. Tracking retains selected-device results. AirTag retains a 4096-byte stack but uses internal dynamic RTOS allocation instead of freeing a live static task's external stack on timeout.

Unchanged Scan and Select countdown updates no longer rebuild rows. New devices, late scan-response names, selection, pages, reset and geometry invalidate the list; data/name rebuilds retain scroll. This is NOT a fix for general Home/menu repaint or missed taps. Intentional Settings opening behaviour is unchanged.

Debug ON enables allocation-failure capture starting at NimBLE initialization, not exclusively scanning. Boundary output adds allocation-failure counts/capabilities/size and application report-rejection counts; scan deltas exclude earlier init failures. The allocation-failure hook only updates atomic counters: no allocation, logging, locks or payload persistence. Debug OFF adds no boundary output. Last-allocation metadata is lifetime state, potentially from an earlier failure; deltas describe the scan window.

## Unresolved RF/memory evidence

Zero application callbacks cannot be explained by list rendering or parsing. Low DMA heap correlated with zero-report scans but does not prove a failed allocation. No controller buffers were moved, pools resized, stacks shrunk, NVS erased, partitions changed or SD assets modified.

IDF v6.0.2 C5 controller allocation requests INTERNAL|8BIT|DMA; selected NimBLE allocation requests INTERNAL|8BIT. Capability budgets overlap; free-DMA and internal depletion are not independent quantities to add. C5 uses ESP IPC transport and controller-managed event buffers. Legacy VHCI silently skips advertising reports when its discardable pool returns NULL, but that path is NOT proof of C5's runtime path. Controller flow-control/discard implementation is prebuilt. `upstream_drops=unavailable` explicitly means neither zero heap-failure deltas nor zero application rejections excludes upstream pool/flow-control loss. Reception/root cause remains unproven.

## Hardware acceptance procedure

Required: Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35), Waveshare ESP32-C5-Touch-LCD-2.8 (WS-C5-28), affected Classic CYD and HackerBox. Install only the matching board's reviewed Development candidate. Only the matching merged `full.bin` uses offset `0x0000`; individual parts retain manifest offsets. Do not select a bootloader as a full image; do not erase NVS or substitute another board's package.

1. Debug OFF: Bluetooth -> Scan and Select. Complete ten scans without leaving. Record totals. Variability alone is not a failure; repeated zero-report scans near a known stable advertiser remain unresolved failures.
2. Repeat Debug ON with primary USB logs. Retain `[BLE_SCAN]`, heap boundaries, start errors and stop-pending messages. Classic/HackerBox USB Debug is separate and defaults OFF: physically unplug GPS before acknowledging enable; preserve that interlock.
3. Press Rescan during an active scan, then repeat rapid presses. Expect one admitted worker, no stale cancellation, crash or premature result wipe. If `Scan stopping; retry Rescan` appears, retry after exit. Persistent pending stop is a failure to investigate, not a passed rescan.
4. During scan press Back and reenter; repeat Home and reentry, ten times per route. Exercise both portrait and landscape navigation layouts. Expect no stale UI access and safe teardown/reentry.
5. Complete WiFi scan, enter BLE, return WiFi, reenter BLE. Check Locator selection/tracking, Observer, Lookout, AirTag/Found Tags return and OT BLE dwells if used. No feature may cancel a successor or free a live host.
6. Check unchanged empty/nonempty countdowns for absence of periodic row rebuilds. Verify late names, highlight, paging, scroll, final results and reopen/rotation. Repeat on no-PSRAM Classic.
7. Report board/version, Debug/USB Debug state, press/navigation sequence, completed/cancelled boundary and callback/heap/counter output. A cancel-return without operator timing does not prove spontaneous cancellation.

## Host checks

Set `PYTHONDONTWRITEBYTECODE=1`, owned `TMPDIR` and `CYM_TEST_OUT`. Run `python3 -B tests/run_ble_scan_lifecycle_host.py`, `tests/run_ble_scan_list_host.py`, `tests/run_ble_scan_session_host.py`, `tests/run_ble_scan_reports_host.py`, `tests/run_ble_scan_diag_host.py`. These execute extracted production code against faulted SDK/RTOS boundaries; they do not emulate RF or both physical LCD layouts. Hardware acceptance above remains mandatory.

## Chameleon integration follow-up (Development candidate, hardware acceptance pending)

The radio reservation starts before initialization and spans discovery, checked scan cancellation, the 250 ms deferred connection, pairing/services, the live connection and disconnect callback drain. The deferred operation now runs on the UI-owner lifecycle pump, which continues cleanup after screen exit. Stale scan/link/GATT generations cannot release successors. Pairing, bonds, security, protocol and Classic BLE 4.2 legacy fallback remain unchanged.

A pending generic worker or retained shared consumer produces `BLE busy: stop other scan/Lookout; retry` on the idle/error screen. Lookout deliberately stays active after leaving its screen: explicitly stop it there, return and retry Scan. Admission never disables intended background features or cancels foreign discovery; foreign EALREADY is failure, not own scan success. Cancellation failures retain ownership and expose pending/retry status rather than freeing a live port or publishing idle.

Jim reports inability to connect Ultra, but board and discovery-versus-connect/pairing/services/handshake stage are unknown. Verified integration defects are not a proven explanation of that report or proof of recovered reception.

### Chameleon hardware acceptance

1. Record board/package, Ultra firmware, pairing mode, Debug/USB Debug and primary USB logs. Preserve bonds/NVS. Identify whether Ultra is absent from discovery, found but cannot connect, or fails later; record exact displayed status.
2. Leave Lookout active, open Chameleon and Scan. Expect visible busy/retry with no implicit Lookout shutdown. Explicitly stop Lookout, return and retry. Repeat with a generic scan starting/stopping.
3. Discover/select Ultra. Cancel, Back and Home during deferred connect, pairing and READY; reenter/retry. No stale connection may start and scanner/WiFi transitions must not tear down a retained connection.
4. Reach READY/read device info, navigate to child and back without unwanted disconnect, then explicitly disconnect/reconnect with preserved bonds. Verify existing safe protocol operations on test tags.
5. Repeat Debug OFF/ON on affected C5 and Classic BLE 4.2. Persistent pending stop remains a failure. No host test proves RF, security/ATT, bonds or real LCD geometry.

Additional host check: `python3 -B tests/run_ble_chameleon_integration_host.py`. Actual arbiter/lifecycle, callback admission/parser, Home/Back event handlers plus main-loop dispatch, and status poll are extracted. SDK/RTOS, security payload handler and LVGL rendering remain boundary stubs, not physical acceptance.

### Chameleon reentry correction (v3.0.30 Development candidate)

Successful BLE deinit leaves the host stop-request flag set until fresh initialization. Chameleon admission now treats that flag as busy only while a port remains retained; it does not clear live-host flags. In-flight cleanup remains independently blocked by the cleanup/API reservation gates. Stop timeout and SDK deinit failure still retain the port and reject a claim.

The integration runner now has nine scenarios with Debug OFF/ON. The added reentry scenario extracts the actual cleanup, AirTag exit, acquisition, initialization and sync helpers, with no manual lifecycle-flag reset between successful teardown and reentry. It also probes admission during real cleanup, retained-port stop timeout/retry and failed SDK deinit. SDK/RTOS/host-exit events are fault boundaries, not a hardware simulator. The prior eight scenarios retain their existing init boundary stub.

Hardware addition: explicitly stop AirTag/another BLE feature, then open Chameleon and Scan without opening another BLE tool first. Repeat after BLE-to-WiFi transition and return. Expect fresh initialization/discovery, or a truthful busy/pending error when teardown is incomplete. Record exact board, stage and primary USB log; Ultra connectivity and reception remain unaccepted.
