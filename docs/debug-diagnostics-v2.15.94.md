# Persisted debug diagnostics — v2.15.94

## Approved design and implementation checklist

- One NVS bool (`settings/debug_diag`, u8), default OFF on absent namespace/key,
  malformed bool, NVS read error or settings allocation failure. Do not erase or
  change the game one-shot intent keys. Load before optional diagnostics in both
  normal and isolated boot. Existing non-WS NVS repair policy is unchanged.
- Shared `cym_debug_enabled/load/set/generation` API. Setters serialize with a
  250ms semaphore wait, check open/set/commit, publish the combined atomic
  state/generation only after commit. Failed saves retain runtime state.
- Both Classic and Modern route Settings -> Hardware to the same production
  Hardware screen. Debug switch uses that API. A 200ms LVGL owner timer observes
  serial changes; serial never accesses LVGL. Stop hook deletes its owned timer
  and clears all pointers before object destruction/recreation. Timer allocation
  failure is displayed; reopening the screen refreshes the current shared state.
- Primary physical USB only: native USB Serial/JTAG when enabled (including
  configurations with secondary USB output); otherwise existing default UART0
  USB-bridge console only. Never select GPS/JST/custom UART. No console/pin
  configuration changes or radio/storage command registration.
- On secondary USB, the installed IDF convenience USB REPL API is not compiled.
  Use its underlying installed linenoise + esp_console parser with explicit
  `/dev/usbserjtag` task-local input/output and a priority-1, 4096-byte worker.
  No private line parser, log interception or global log level changes. The same
  debug-only worker remains available in isolated mode; no normal services are
  started by the isolated console.
- Shared diagnostics gate controls optional game initialization/hash progress,
  gameplay PERF/ENGINE_IO_DIAG/AUDIO_DIAG, UI_DIAG/UI_WORK/DISPLAY_DIAG, optional
  memory/heap output and high-volume screen/SD debug-tag chatter. Formatting,
  snapshots and selected optional timing/nonzero scans are skipped while OFF.
- Keep transfer/completion/ownership counters, DMA correlation, watchdogs,
  readiness/hash/codec checks, failure handling, radio teardown, touch/BOOT Fire,
  native renderer timing, saved orientation and orderly same-image Exit intact.
- ES8311 shared game constant only: -15dB -> -3dB, with matching AUDIO_STARTED
  detail. No PCM scale, music, I2S clock/pin/rate, PA, queue or priority change.
  Additional explicit output/stop failure messages are retained while OFF.

## Operator manual — copy/paste commands and expected response

Use the physical USB console at its existing serial settings. Enter commands
with Return (CR or CRLF). Do not use the GPS/JST connection.

    debug status
    Debug OFF

    debug on
    Debug ON persisted; applied immediately

    debug status
    Debug ON

    debug off
    Debug OFF persisted; applied immediately

`debug` and `debug query` also return status. State queries respond while OFF.
Unknown arguments, wrong case and extra arguments print usage without mutation:

    debug on extra
    Usage: debug [on|off|status|query]

A save failure prints `Debug persistence failed: <error>; unchanged ON/OFF`;
never treat this as a saved change. The Hardware switch reverts to the active
state and reports `Save failed - setting unchanged`

In Classic or Modern: Settings -> Hardware -> Debug diagnostics. The initial
switch state comes from the shared API, not a separate UI setting. Successful
UI changes persist without reboot. An already-open screen tracks serial changes
at its 200ms owner update. Leave and reopen to test pointer/timer recreation.

With debug ON, existing bounded game performance batches and main/engine-owned
memory reports run at about five seconds. Memory reports include free internal
RAM/PSRAM, largest free blocks and self-owned stack high-water marks. No live
retiring-task walk or foreign task deletion is used. Diagnostic report windows
restart on changes; lifetime/functional counters are not reset behind producers.
Warning/error/launch/Exit/readiness status stays visible with debug OFF.

### Explicit board constraint

The existing Classic ESP32 console configurations (`cyd-2432s028`,
`hackerbox-cyd`) have CONFIG_ESP_CONSOLE_NONE enabled. This disables the new
interactive debug-command path in this implementation; it does NOT prove that
existing physical USB-C debug output is absent. Jim reports existing USB-C debug
output and working GPS on the Classic hardware, and explicitly directed that
console configurations remain unchanged for this test candidate. The shared
persisted Hardware switch is available on both profiles. Test existing output
with the switch OFF/ON; do not claim interactive commands work until physically
verified. Preserve the working GPS and primary USB-C routes; do not redirect
logs or commands onto GPS/JST pins. Native USB support on capable profiles is
compiled/exercised in host fixtures and all8 build gates; physical command I/O
and isolated-mode responsiveness remain hardware checks.

## Scoped diagnostic inventory — gated versus retained

The evidence directory contains machine-readable `diagnostic-inventory.json`
and `engine-inventory.json` with source paths/line anchors. Lines can shift.

Gated:
- Main high-volume ESP_LOGD screen, scan and SD detail, explicit DIAG,
  SD_TREE_DEBUG and FLUSH-PROV info sites. Arguments are not evaluated while OFF.
- Normal UI timing/work hooks return a zero clock sentinel and skip recording;
  reports return before formatting and snapshots. Owner-only windows reset.
- Optional game engine stdout startup banners, lump/cache/init progress,
  screenshot/save confirmations and repetitive gameplay detail at individually
  selected call sites. No global printf/ESP_LOG override.
- Hash/structure elapsed detail and heap snapshots; validation and progress UI
  still execute. Game performance/readback detail and sample nonzero scans are
  optional. I/O timing clock returns zero while OFF; admission/completion/error
  counters continue. Current-task memory report uses its own state.
- DISPLAY_DIAG reporter skips periodic formatting/snapshots while OFF; report
  baselines reset, but transport/ISR counters and associated timestamp collection
  are retained because they share completion correlation and fail-closed DMA
  ownership bookkeeping. No resets of ISR/audio/engine producer state occur.

Retained:
- All existing ESP_LOGE/ESP_LOGW and engine stderr/fatal output, selected stdout
  warnings/refusals/failures, launch/start/Exit meaningful state transitions.
- Functional SHA/readiness/codec readback gates, errors, native takeover, pending
  DMA ownership token/ack, watchdog feed, transfer counters, input and cleanup.
- Explicit serial responses, save failures and console availability messages.
- Existing separate GPS debug toggle and its five-second GPS heartbeat policy;
  no unrelated GPS refactor.

## Verification and hardware boundary

Focused tests execute production settings/command functions with fault-injected
NVS, the installed IDF split parser, production owner synchronization/stop/event
functions, optional UI/display recording/reporting functions and site-scoped
engine formatting macros. A pinned real-LVGL fixture executes the production
Hardware screen, tiles, owner timer/event and stop hook across six geometries,
36 recreations and shared Classic/Modern frame styles; frame setup and NVS are
mocked, not hardware. Full host tests exercise production engine/render,
DMA, input, codec and boot contracts with their documented HAL mocks.

Physical acceptance is still required: both UI layouts/rotations and smallest
240px display, serial OFF/ON/status/malformed/reboot while normal and isolated,
NVS power-loss/fault behavior, repeated screen recreation and Exit, hardware
watchdog/input/DMA behavior, codec readback and adequate speaker output at -3dB.
The .93 report was audible only with speaker against the ear and was NOT adequate
output. Neither audibility nor improved/subsecond response is claimed here.
