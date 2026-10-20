# v3.0.32 radio repair candidate — operator acceptance

Development candidate pending review and physical acceptance. No reception result is claimed by a host test or successful build. Stable remains v3.0.27. Do not publish raw MAC/name/SSID/location captures.

## What changed and what did not

- Two decoded IR signal copies are task-only and now use existing external BSS support on PSRAM boards. Raw RMT RX/TX staging, GPIO interrupt rings, queues, controller buffers and RTOS objects remain internal. No-PSRAM storage stays internal; the decoded replay scratch copy is allocated only during its task invocation and released on completion/stop. Allocation failure is an explicit error, not a successful sequence. Check IR capture and replay as a neighboring feature.
- BLE discovery preserves the one-tick publication wait, serialized/reentrant task-owned transitions, failed-init retry, legacy BLE 4.2 fallback, worker-owned cancellation and 4096-byte stack. A failed allocation during its active window stops the scan with `Scan incomplete: memory pressure; retry`, even with old result rows or Debug OFF. This deliberately reports global memory pressure, not a proven controller-only failure. Other applications may be responsible for a failure in that window.
- Debug ON adds `allocator_first=<public allocator name>` and `attribution=global-scan-window` to the bounded summary. The first function name and last allocation size/caps need not describe the same call. Prebuilt controller event/pool drops remain unavailable. A hook count is not a count of advertising packets lost.
- Shared full scans restore AUTO on C5 and propagate band-selection, scan-start, SDK completion and record-read errors. Completion is published after records; Channelizer checks its ticket and takes an admission-gated copy. Country policy, channel permissions and group/display limits are unchanged. A scan requested from an earlier 2G-only state is a confirmed source issue; the exact physical missing-5GHz cause is still to be tested.
- Scope's worker owns tuning and teardown. Successful set-channel AND matching channel readback are required. Callbacks with a different RX channel, closed acceptance window or old band epoch are rejected. UI consumes a separate completed-sweep snapshot; band changes discard old work. Setup errors and rejected channels are visible. A delayed/failed cleanup retains ownership and blocks radio successors instead of deleting a task or disabling a successor's radio.
- Scope listens 120 ms after verified tuning (twelve yielding 10 ms slices), spanning a common 102.4 ms beacon interval. Contention/loss, nonstandard beacon intervals and regulatory restrictions still cause misses. This is sampled packet RSSI, not continuous RF power/noise. No persistence trick is used to simulate reception. Both layouts use the same unchanged canvas dimensions/geometry.

GPS/timekeeping/battery/console backgrounds, USB-primary-only console, GPIO28 GPS, WS35 BOOT disable, SD 20 MHz, display buffers/pins, NVS/partitions/assets, audio and RTA controls are not changed. No controller PSRAM placement, external task stacks, stack shrinking, display safety bypass or sdkconfig placement switch is introduced.

## Installation and baseline

1. Use only the matching board package after parent review. Prefer settings-preserving Quick Flash/application update using the existing matching partition layout and Erase OFF. Do not use a merged full image for a settings-preserving update: it can overwrite NVS even without erase-all. No card formatting or asset copying is required.
2. Record board/version v3.0.32 and previous v3.0.31 result. Keep known stable 2.4 GHz and 5 GHz access points and a known BLE advertiser nearby. Use locally legal channels. Test a permitted non-DFS channel first, then separately document DFS behavior; do not widen country settings to make a test pass.
3. Use the existing accepted primary USB console only. Never reroute through GPS/JST UART. Classic/HackerBox USB Debug remains its separate opt-in physical-GPS-unplug interlock. Never connect two USB paths simultaneously as a workaround.

## Copy-paste diagnostic commands

Enter one command at a time on the existing console:

```
debug status
debug off
debug status
```

Expect `Debug OFF` after successful persistence. Test normal performance first. Then collect one uninterrupted session:

```
debug on
debug query
```

Expect `Debug ON`. Open Bluetooth -> Scan and Select; capture full startup, complete scan, counts, rescan, stop and subsequent radio transition. Record internal/DMA free AND largest block before/after init/scan. Compare allocation deltas and callback/report counts with v3.0.31. A larger heap alone is not acceptance: require real reports from the known advertiser, useful selection and repeated successful scans, no starvation/reset, and an explicit error rather than empty success when memory is exhausted. Do not infer a controller call site from allocator/capability fields.

For Channelizer, repeat from cold WiFi and after Clock/NTP, a 2.4 GHz tool, and Scope. Capture `acquisition country_rc=... cc=... policy=... 2g=... mask5=... band_rc=... mode=... bitmap=default-regulatory` (C5), followed by `Scan done: generation=... status=... driver_records=... retained=... 2g=... 5g=...`. These are expected FORMAT strings, not hardware output. Inspect both the shared scan and Channelizer list for the known 5 GHz AP. A successful empty SDK scan does not prove RF absence. If the SDK reports 5 GHz but the list does not, retain the whole sequence/ticket for review; do not raise grouping caps to conceal it.

For Scope, select each supported band. Wait for a complete sweep: status `2.4G sampled <n> pkts; skip <n>/<total>` or `5G ...`. A skip is a rejected/readback-failed channel, not a silent zero-power channel. Toggle band midway through a sweep ten times; old-band traces must not be attributed to the new band. Back/Home during dwell, immediately reenter, then start a different radio tool. There must be no late teardown of the successor, crash or false completed sweep. An SDK failure must show `Scope failed; Back and retry`; retained cleanup can require another retry. Do not repeatedly force entry or reboot as proof of success.

Return to normal operation:

```
debug off
debug status
```

Confirm OFF. Retain the unedited capture privately and redact identifiers before sharing.

## Required physical matrix (pending)

Perform in Debug OFF and ON, Classic and Modern navigation, portrait and landscape where supported:

- Ten BLE scan/rescan cycles with an advertiser; early cancel, Back/Home, immediate reentry and existing/stale selections. Legacy Classic/HackerBox BLE 4.2 and no-PSRAM paths must still work.
- WiFi Scan and Select, Channelizer active scan, passive scanner consumers, Wardrive start/stop (WiFi and BLE), sniffer and Observer; no unrelated completion or delayed worker cleanup may replace the new owner's data/radio.
- Scope 2.4/5 GHz, mid-sweep toggles, rejected/DFS channels, all-channel rejection, entry during pending SDK scan, exit/reentry and transition to BLE/WiFi. On no-5GHz boards the 5 GHz control remains disabled.
- Chameleon discovery/selection/connect/security/services/READY separately; Bluetooth Locator, Observer, AirTag and deliberate Lookout ownership stop. These changes do not claim Ultra interoperability.
- Clock Display Only stays network-silent; AP/client NTP, timekeeper, GPS continuity and battery continue intentionally. Check navigation into/out of Scope without disturbing a reserved Clock session.
- IR capture and replay after BLE use (PSRAM and no-PSRAM); raw RMT operation is still internal. Verify normal SD, audio/RTA gain/freeze/resume and board display/touch behavior.

All eight board builds and synthetic SDK/RTOS host fault tests are software gates only. They cannot certify RF reception, physical display geometry, controller heap fragmentation, on-device scheduling, DFS availability or long-soak stability. Stop acceptance on repeated zero BLE callbacks, missing known 5 GHz acquisition, resource errors, resets or ownership regressions; return full private evidence for review.
