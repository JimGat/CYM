# Isolated native presentation candidate

Task8 is activated by Jim's physical v2.15.89 rejection (reported .3fps) and the
supplied cycle90 trace. Jim accepted normal .89 responsiveness; this candidate
PRESERVES it. No normal transport/menu/service tuning or new emulator/partition.
This is a Development/Beta candidate, not physical acceptance or a measured FPS
improvement. Parent reviews, publishes and supplies immutable packages; worker
never commits, pushes, deploys, flashes or sends Telegram.

## Owner and transport

Normal CYM, selector/license and initial validation/hash/init UI remain LVGL.
Only WS-C5-28/35 same-image isolated boot can enter native RUNNING. Main completes
its current lv_timer_handler and synchronous flush, leaves the LVGL mutex, checks
no pending display token, then deletes the now-inactive game update timer. It
stops the isolated LVGL tick source and never invokes another handler. There is
NO live return to LVGL. Retained LVGL objects/buffers are freed only on orderly
Exit after the engine's cleanup acknowledgement AND actual suspended-task join.

Engine keeps priority2 and its existing vTaskDelay(1) after tick. PCM stays3.
ONLY isolated native main changes from1 to3, equal to PCM and above engine.
NATIVE_OWNER logs its actual sampled effective priority at takeover. Installed
FreeRTOS time slicing shares ready equal-priority tasks; accepted DMA semaphore
waits block main. Every main loop uses a strictly positive one-tick delay (10ms
on the installed100Hz WS configs), including no-frame/cleanup loops. Viewport
attempts are capped by a50ms cooldown measured AFTER completion/failure return;
this is a CPU fairness policy, NOT an asserted achieved frame rate. No sleep
holds the frame or SD mutex. Input runs while waiting between presentations.

The independently allocated aligned internal-DMA4096-byte boot stage is reused
by the sole native owner only AFTER previous LVGL transfers drained. No engine,
mailbox or palette pointer reaches DMA. Main copies the latest320x200 index frame
AND palette under frame_lock; conversion occurs after release into <=2048-pixel
native stripes. Nearest-neighbour maps, explicit rotation270 and high-byte-first
RGB565 replace canvas composition/software rotation. Existing BGR panel settings
and normal color/rotation paths are unchanged. Controls/status raster once with
fixed2x5x7 glyphs: FWD, BACK, <, >, FIRE, USE, MENU, OK, EXIT. The frame never
covers these targets. On rejected static-control stripes, the full static region
is retried; on partial viewport failures the next attempt rewrites the whole
viewport using the latest safely copied publication (or the retained snapshot).

Each native stripe performs ONE shared SD mutex take of at most10ms, then one
bounded <=4096-byte draw. Bus release occurs only after matching ISR token plus
real completion semaphore. Pending/cancel input is polled between stripes and
on20ms wait failures, but accepted DMA is never released early. Missing matched
completion after100 waits triggers fail-closed reboot with stage/bus retained;
no timeout-then-free and no invented acknowledgement. ST7796 still discards
underlying command/color errors: no vendor change. Real matching completions
prove color payload completion, not independent command correctness, panel
scanout/tearing or a human-observed frame. Driver errors with no completion reset
fail closed as before. This caveat remains a parent review/physical gate.

Direct native two-point board-adapter reads use the SAME270 inverse mapping and
doom_game_touch_keys. Polls are bounded to one read per10ms and independent of
frame production/SD admission/LVGL input callbacks. Read faults supply zero
contacts, partial releases retain the other contact, movement+Fire are ORed,
BOOT Fire retains20ms debounce and touch deadman250ms. No normal BOOT remapping.
Exit queues cancellation/keys0, PCM stop/audio-DMA release and engine-owned0
cleanup, then the actual task join and UI release, then reboot with consumed
intent to normal CYM. Native worker errors follow cleanup/join then orderly
normal reboot rather than reopening LVGL. Startup validation/init errors retain
the existing readable Return CYM LVGL UI before native takeover.

## Counters (actual elapsed denominators)

NATIVE_TAKEOVER: rotation, intended local priority, minimum period, drain proof.
NATIVE_OWNER: sampled effective priority after local set, not an inference.
NATIVE_PRESENT (task log, no more often than5s): interval_ms,
completed_viewports, failed_viewports, completed_total, owner_priority,
block_ticks. completed_viewports increments ONLY after the final matching real
stripe completion; rejected, missing, cancelled or partially sent frames never
increment it. It counts completed game VIEWPORT payloads, not controls repaint,
full physical LCD refresh, panel scanout or a human-observed FPS guarantee.
Rate = sum(completed_viewports)*1000/sum(interval_ms) across complete steady
windows. Do not average unweighted samples, include startup or infer FPS from
published/stripes/canvas. Host fake-clock tests are NOT hardware measurements.

Existing PERF fields remain. In native mode displayed now counts completed
viewports (old .89 counted canvas scale/invalidation); scale_us is native
conversion+presentation wall time including polling/admission/completion, NOT
CPU-only scaling. published and overwritten remain mailbox publication/consumption
counters; consuming a snapshot is NOT displaying it. panel_flushes counts
completed stripe-helper calls, including static controls; never complete frames.
DISPLAY_DIAG isolated now includes native stripe timing after takeover; handlers
stop increasing then. ENGINE_IO_DIAG, PERF and AUDIO_DIAG are retained. Nonzero
PCM and SFX starts are NOT proof of audible output.
Jim explicitly reported hearing nothing during .89 gameplay. Audible SFX
acceptance is FAILED, not merely untested. This candidate does not change the
audio/codec implementation and does not claim to repair that failure.

Startup admission/owned-file fairness is NOT changed in this candidate: existing
isolated LVGL100x20ms retries and the previously observed long hash/init waits
remain. Native RUNNING does not claim to repair startup time or loading Exit
latency. Normal helper remains byte-identical to .89, including its waits.

## Operator procedure after parent publication only

Use the parent-verified immutable full image/hash for your exact WS board,
offset0x0000, primary USB-C. Do not flash a different board's package.
Start serial capture BEFORE boot at the actual configured baud/device:

    python3 -m serial.tools.miniterm /dev/ttyACM0 115200 --raw 2>&1 | tee cym-native-serial.log

Ask: "Verify normal CYM still behaves like .89: both Classic/Modern Home,
Deauth Monitor start/stop/save/Back, Settings/Hardware, orientations, SD consent,
battery/calibration and clock." Expected: no functional or responsiveness
regression. Those normal paths were not tuned by this candidate.

Ask: "Enter the existing selector/license and Continue. Capture full boot,
hash/init and60s steady native gameplay, then movement+Fire, two contacts,
partial release, BOOT+movement, all visible buttons, audible SFX and Exit."
Expected serial boundaries: MODE_CONSUMED, ISOLATED_BOOT normal_services=0,
ENGINE_STARTED, NATIVE_TAKEOVER drained=1, NATIVE_OWNER, NATIVE_PRESENT complete
windows; then EXIT_REQUESTED, ENGINE_JOIN_READY owned=0, UI_RELEASED, GAME_EXIT
and a normal boot. Verify physical correct colors/orientation, readable controls,
no stuck keys, responsive Exit and no seconds-long steady stalls. Send complete
serial/video evidence, including failures; no additional design approval needed.

The >=10 completed visibleFPS/60s target is aspirational, NOT achieved by host
or build tests. WS35 and WS28 physical speed/input/color, PCM audible SFX,
startup loading Exit latency, dynamic internal heap and tearing still need Jim's
hardware acceptance. Parent independently reviews/tests/packages/publishes and
verifies Beta/CI before CLI+Telegram delivery. No stable/main promotion implied.
