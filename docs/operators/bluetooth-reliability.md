# Bluetooth reliability candidate v3.0.30

Development candidate only. Stable remains v3.0.27. Host/build success is not hardware acceptance or recovered RF reception.

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
