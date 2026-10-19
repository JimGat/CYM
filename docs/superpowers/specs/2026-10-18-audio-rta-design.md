# Audio RTA: WS-C5-35-first design

Date: 2026-10-18
Status: owner-approved direction; detailed design recorded; not implemented in firmware.
Source baseline: `bb0b67286b44ff1db09ee0a29accbc26ad0a93f5` (Development v3.0.20).

## 1. Approved scope

An on-demand **Audio RTA** for Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35),
initially gated to that target only. Jim accepted the recommended 24-band approach
and explicitly requested **landscape as the preferred layout, with full portrait support**.

- 24 equal logarithmic bands covering nominally 20 Hz to 20 kHz.
- Dark instrument plot, green/amber/red bars and contrasting peak-hold markers.
- Fast/Slow averaging, Freeze/Resume, Reset Peaks and manual microphone gain.
- Overall RMS, sample peak, clipping warning and selected-band frequency/level.
- Uncalibrated dBFS, not dB SPL or a certified third-octave instrument.
- No AGC, noise suppression, echo cancellation or speaker output.
- No raw audio recording, SD export, network streaming or telemetry upload.
- No capture outside the screen; no new main-loop polling or broad application refactor.

Hosyond and Waveshare S3 Touch boards follow only after separate microphone path,
pin, clock and lifecycle qualification. A codec or speaker alone is not a microphone
capability. Ultrasonic leak investigation is a later, physically qualified phase.

## 2. Navigation and orientation contracts

Inspected in `ESP32C5/main/main.c`:

- Modern: `show_category_home()` -> `show_cat_tools()`. The existing category is
  named **Tools & System** and includes Settings. Put Audio RTA directly there,
  alongside Settings; do not rename the category or bury RTA inside Settings.
- Classic: add an additional Audio RTA tile in `show_main_tiles()`, preserving all
  existing tiles and their reachability.
- Both routes use one `Audio RTA` dispatch key and the same feature screen.
- Integrate `NAV_SHOW_TABLE` and FSD's supported navigation routes; test real tile
  traversal rather than only direct string-based navigation.
- Back returns to the actual parent: Modern Tools & System or Classic Home. Home
  returns to the selected home layout. No duplicate bottom Back button.
- Register `g_screen_stop_fn` immediately AFTER `create_function_page_base()`;
  stop is idempotent and must not navigate.
- `fsd_ui.inc` is an existing separate UI-include precedent.

WS35 already has `BOARD_DEFAULT_ORIENTATION=3`; valid saved orientation wins.
Landscape preference means layout priority, not forced rotation or changing NVS.
Use existing LVGL software rotation and live horizontal/vertical resolution. Do not
add a second touch transform. Support both landscape rotations and both portrait
rotations. Existing FSD orientation changes go Home: fully stop RTA through that
path, then reopen at the new dimensions. No separate orientation service is needed.

## 3. Dual-orientation screen

One screen/model with two responsive arrangements, not duplicated feature logic.
Keep the existing title bar and navigation controls. Draw bars with LVGL primitives
or lightweight objects, without another full-screen RGB framebuffer. The plot is
dark regardless of menu wallpaper; global theme and unrelated screens are unchanged.

### Landscape: preferred, WS35 480 x 320

- Compact status row: Live/Frozen/Starting/Error, RMS, peak and CLIP.
- Wide 24-bar plot with a fixed -90 to 0 dBFS scale and sparse frequency labels.
- Selected-band detail line with exact lower/upper edges and level.
- One row of controls: Freeze/Resume, Reset Peaks, Fast/Slow, Gain.
- Light peak markers; upper bar colours indicate digital level, not hearing safety.

Height envelope: 34 title + 24 status + 170 plot (including frequency ticks)
+ 24 detail + 48 controls + 20 total padding/gaps = 320 pixels.
This is a fit check, not permission to hardcode an absolute content size: measure
actual title/content geometry and assign remaining height to the plot.

    [Back] Audio RTA                                  [Home]
    LIVE             RMS: ...     Peak: ...          [CLIP]
    0 |          24 bars with peak markers
      |          logarithmic frequency axis
  -90 |___________________________________________________
      20       100       1k        10k                  20k
    Selected: frequency range / band level
    [Freeze]      [Reset Peaks]      [Fast]      [Gain]

### Portrait: WS35 320 x 480

- Same navigation and measurements; bounded status may wrap into a second line.
- All 24 bars remain visible; print fewer axis labels rather than tiny text.
- Selected-band details below the plot.
- Two-by-two controls: Freeze/Resume, Reset Peaks, Fast/Slow, Gain.

Height envelope: 34 title + 32 status + 250 plot (including frequency ticks)
+ 36 detail + 96 controls + 32 total padding/gaps = 480 pixels.

Use readable existing fonts and control targets at least 44 pixels high. Bar edges
come from the current plot bounds with integer remainders distributed. Tap/drag
anywhere in the chart selects the nearest band; narrow bars are not independent
small touch buttons. The detail line always shows exact edges. Normal operation
requires no scrolling; error text and the bounded Gain overlay have vertical
scrolling as a safety net. All controls and overlays must remain reachable in both
orientations. These diagrams are design illustrations, not device measurements.

### Microphone glyph

Inspect the actual `lv_extra_symbols` cmap and fallback chain; a macro name does not
prove a glyph is compiled. Reuse a real microphone glyph if present, otherwise add
one licensed glyph or an original small monochrome asset. Preserve existing glyphs
and record provenance; no wholesale font replacement. Verify rendering in both home
layouts. Use ASCII status text and existing project-blue action buttons.

## 4. Module boundaries and gates

Proposed files under `ESP32C5/main/`:

| File | Responsibility |
| --- | --- |
| `audio_rta_ui.inc` | responsive UI, controls, screen-local refresh and stop hook |
| `audio_rta.h` / `audio_rta.c` | session, capture worker, copied snapshots, lifecycle/errors |
| `audio_rta_dsp.h` / `audio_rta_dsp.c` | host-testable PCM-to-energy processing; no LVGL/SD/radio dependencies |
| `audio_rta_board.h` / `audio_rta_board.c` | WS35 microphone, codec/I2S ownership and cleanup on the existing I2C bus |

Narrow API: start, copied snapshot, update controls, request stop, completion status
and release after completion. Snapshots contain generation, sequence, validity/age,
24 band energies and peaks, RMS, sample peak, clipping and error status. The UI never
borrows a PCM/workspace pointer; the worker never calls LVGL.

Introduce `BOARD_HAS_AUDIO_RTA`, default 0, enabled only for WS35 in the implementation
cycle. Consistently gate include, declarations, dispatch, NAV/FSD route and tile.
Build the backend only on enabled targets or prove compile-time elimination.
Do not broadly enable `BOARD_HAS_AUDIO`. Unsupported targets have no tile, startup,
worker or DSP workspace. main.c gets only narrow integration points, no global tick.

Inactive cost is flash plus small owner state, not literally zero firmware size.
No inactive capture, timer, worker or large retained allocation is allowed.

## 5. Hardware receive path

Reuse the existing WS35 I2C bus and installed codec interfaces. Never create/delete
a second bus or reset shared devices. Prior pinned vendor evidence records BCLK23,
LRCLK10, ESP TX25 and ESP RX24, with BCLK-derived codec clock and no MCLK. These are
reference assignments, not proof of microphone reception in CYM. Verify ADC routing,
mic bias, sample/slot format and supported gain steps against the pinned BSP and
schematic before implementation.

Target mono 48 ksample/s capture. Verify that the requested clock/format is supported;
fail explicitly rather than silently substituting a rate. If RX requires dummy TX
clocks, explicitly own that channel and feed silence. Keep DAC output digitally
muted. Do not copy a speaker-only initializer and assume ADC support follows.

Do not blindly toggle EXIO5: existing WS35 references also associate it with board
power enable. Preserve shared power/expander state and establish the actual amplifier
isolation policy before attempting hardware mute. Refuse a busy audio owner rather
than stealing its channels or resetting its codec.

Preserve display, touch, GPS RX28, camera, SD and reserved RF-HAT pins. WS35 BOOT
remains disabled as an application button. All diagnostics remain primary-USB-C-only;
no PCM payload logs or expansion/JST UART output.

## 6. DSP and measurement semantics

Band edges: `edge[i] = 20 * 1000^(i/24)`, i=0..24. Centres are geometric means of
adjacent edges. Exact edges drive processing/details; rounded labels do not redefine
the bands. Label the feature '24 log bands / uncalibrated'.

The design baseline is multirate FFT, avoiding a coarse FFT bin reused as several
independent bass measurements:

- Full-rate path: 4096-sample Hann window at 48 ksample/s.
- Low-rate path: properly anti-aliased 16:1 decimation to 3 ksample/s, then a
  2048-sample Hann window.
- First nine bands use the low-rate spectrum; remaining fifteen use the full-rate
  spectrum. The crossover is an exact band edge, with no double counting.
- The full-rate window spans about 85 ms; the low-rate window about 683 ms. The
  crossover is approximately 266.7 Hz. These calculated design values are not
  measured performance. Do not disguise bass latency with fast animations;
  snapshots carry validity/age information.

Decimation must be filtered, not just sample dropping. Require <=0.5 dB passband
error across the low-path bands and >=60 dB rejection of tones aliasing into them.
Integrate one-sided, window-energy-normalized power with fractional edge-bin weights;
use identical dBFS conventions on both paths. Validate crossover agreement against
an independent high-resolution reference. If the C5 cannot meet resource/performance
gates, revise the internal algorithm under the same API and tests, not the claimed
band resolution or existing application behavior.

Use overlapped analysis and target 10 UI updates/s. UI reads only the newest complete
small snapshot; no unbounded queues or catch-up drawing. An overrun invalidates
continuity, increments a counter and resets the affected window. Mark warming-up
bands invalid rather than displaying invented silence.

Signed PCM is normalized to full-scale amplitude 1. RMS dBFS is
`10*log10(mean(x*x))`; peak dBFS is `20*log10(max(abs(x)))`. Band dBFS is integrated
mean-square power with the same normalization. Apply documented DC removal for
analysis, but detect clipping from original samples. Silence maps to a finite floor;
no NaN/infinity. Preserve the full-scale sine RMS/peak distinction consistently.

Fast averaging: 125 ms energy time constant. Slow: 1 s. Smooth linear power using
actual elapsed sample time before conversion to dB. These are UI response choices,
not certified sound-level-meter weightings. Peak markers hold maxima until Reset
Peaks, gain change or a new session.

Freeze holds the entire displayed snapshot and peak markers; capture/draining
continues only while this screen stays open. Status clearly says Frozen. Resume
shows current data and resets held history. Back/Home still fully stop capture.
Gain changes invalidate windows/peaks and warm up again. Gain is session-only; no
NVS writes. Start with a conservative documented codec gain validated during input
bring-up, show the actual configured value and expose only supported hardware steps.

Overall RMS/peak describe the captured input, not calibrated SPL or the sum of
asynchronously aged bands. Phase one has no A/C-weighting, calibration offset or
microphone response compensation. A nominal 20 Hz-20 kHz plot is not proof of usable
acoustic response across that range. MEMS package type alone proves no bandwidth.

## 7. Lifecycle and memory

State machine: CLOSED -> STARTING -> RUNNING/FROZEN -> STOPPING -> CLOSED.
Failures unwind acquired resources in reverse order and leave a navigable error
screen. Retry is explicit, never a hidden retry loop.

- Claim audio ownership first; check every allocation.
- Large PCM/history/FFT/filter buffers use PSRAM with no internal fallback.
- DMA and driver/RTOS controls stay in required internal-capability memory.
- Worker stack placement follows installed-IDF/cache-safety evidence, not assumptions
  about free PSRAM. No stack shrink to force admission.
- Allocate only on entry; constants may live in flash. No large mutable static BSS.
- Initial design ceilings: 256 KiB PSRAM workspace and 24 KiB incremental internal
  session footprint, including stack/DMA/controls. These are proposed ceilings, not
  measured usage or a promise that current free heap can accommodate them.
- Allocate/reserve required resources before capture; fail cleanly on insufficient
  memory. Measure internal free/largest block and actual allocation deltas.
- Target DSP/capture processing below half the available wall time in a quiet-menu
  test, with touch remaining responsive. Measure overruns and interaction with
  intended background services; do not disable them or shrink display buffers to fit.

Exit ordering:

1. Invalidate UI generation; delete the screen-local refresh timer and detach widget
   references before navigation deletes widgets. Stop accepting controls.
2. Request worker cancellation. Use bounded I2S reads, never infinite waits.
3. Worker stops capture and releases only its owned channel/codec state, then signals
   completion after its last shared-buffer use. It never needs LVGL or the UI lock.
4. After completion, free buffers and release ownership. An application completion
   signal is not proof that the task has stopped using its own stack/TCB: reclaim
   caller-owned worker storage only after verified RTOS task termination. Duplicate
   stop and partial-start cleanup must be safe.
5. On delayed completion, do not free live memory or force-delete the task. A detached
   non-UI owner finishes cleanup; re-entry returns Audio busy until done. No stale
   widget access and no new main-loop polling. Persistent timeout fails qualification.

Target normal cleanup <=500 ms. Any timeout/failure is visible in diagnostics rather
than hidden. Fully stopped means no RTA task/timer/channel or large buffer remains.
No I2C-wide deinit, radio shutdown, NVS erase, SD formatting or partition changes.

## 8. Verification and acceptance

### Host and build gates

Test actual C DSP against independent reference calculations: silence, DC, impulse,
centre/edge/swept tones, multiple tones, deterministic white/pink noise, clipping,
gain change, filter alias rejection, window normalization, crossover and smoothing.
Require steady-state band energy within 1 dB of reference away from intentional
filter transition boundaries; characterize boundary behavior explicitly.

Test failure at every allocation/initialization stage, partial reads, overruns,
codec failure, busy ownership, stop during startup, duplicate stop, delayed completion,
rapid re-entry and old-generation snapshots. UI must remain navigable on every error.

Test both menu routes and distinct Back parents, Home, reachable FSD traversal and
FSD orientation teardown. Geometry/glyph tests cover both layouts and all four WS35
rotations, long errors, Gain overlay, band details and every control.

Compare inactive linked RAM and settled post-exit heap/DMA/largest internal block,
tasks/timers and channel ownership against baseline. Account separately for SDK
first-use caches; no monotonic loss across repeated cycles. Unsupported targets must
have no RTA workspace/task. Run full regressions and all eight final-source builds,
packaged-version gates and existing resource/concurrency guards before publishing
firmware. Compilation does not qualify microphone reception or teardown on hardware.

### WS35 physical checks

Primary USB-C at 115200 baud; record version, orientation, menu mode and debug state.

1. Landscape Modern -> Tools & System -> Audio RTA: verify live speech and external
   known tones, configured gain and honest clipping indication.
2. Verify bass/mid/treble response with a suitable source. Phone/laptop speakers do
   not establish deep-bass or ultrasonic response. Record source/mic limitations;
   measure actual sample rate/format where possible.
3. Exercise Freeze/Resume, Reset Peaks, Fast/Slow, Gain and band selection.
4. Repeat from Classic; verify Back/Home and all four rotations, including overlays.
   Capture real screenshots for both landscape and portrait.
5. Ten entry/exit cycles per navigation route; measure settled resources, heap
   integrity and actual capture cessation.
6. A 15-minute capture soak with responsive touch, no unexplained overruns, panic or
   watchdog failures; debug ON/OFF coverage.
7. After exit, check Clock AP/mDNS and NTP, Client time, GPS/RTC, SD at unchanged speed,
   display/touch, QR camera, existing audio and radio transitions. Preserve intentional
   background capabilities and report proven interactions rather than suppressing them.

No claims of working hardware input, calibrated SPL, all-board support or ultrasonic
leak detection before the corresponding evidence exists.

## 9. Delivery and future extension

Sequence: input/ownership bring-up with failure tests -> numerical DSP tests ->
dual-orientation UI and both tile routes -> full regression/build gates -> Dev-only
publication -> owner bench qualification. One writer, all CYM work on ESP32-Dev as
dev, no VM source work. Recheck live rules/ownership before implementation.

This documentation commit does not bump firmware, replace binaries, deploy Pages,
promote Stable/main, create a tag/release or flash a device.

Ultrasonic phase must first identify/measure microphone response, codec ADC/filter
bandwidth and supported capture rate. A later mode may reuse the capture/lifecycle
interfaces for high-frequency energy, waterfall and frequency-shifted listening.
No such UI, buffer or background resource is reserved now. If the onboard path is
unsuitable, use a separately designed external ultrasonic front end instead of
claiming MEMS microphones automatically support leak detection.

## 10. References and evidence limits

- [Canonical workflow](../../../.claude/rules/cym-canonical-workflow.md)
- [Landscape rules](../../../.claude/rules/cym-landscape-support.md)
- [Stop-hook rules](../../../.claude/rules/cym-screen-stop-hooks.md)
- [Typography rules](../../../.claude/rules/cym-lvgl-text-rules.md)
- [Board definition](../../../ESP32C5/components/board_hal/include/boards/ws_c5_35.h)
- [Prior audio routing evidence](../../ws-c5-audio-lvgl-v2.15.91.md)
- [WS35 hardware](../../hardware/waveshare-c5-touch-lcd-35.md)
- [Feature index](../../../BACKLOG.md)
- Waveshare product: https://www.waveshare.com/esp32-c5-touch-lcd-3.5.htm
- Pinned vendor BSP: https://github.com/waveshareteam/ESP32-C5-Touch-LCD-3.5/tree/04e6134cf3e37309b2bec9915189efeace1161bc
- Inspiration only, no imported code/art: https://play.google.com/store/apps/details?id=radonsoft.net.rta

The Waveshare Wiki was a placeholder when researched. Vendor specifications are not
CYM hardware acceptance. The reference Android app advertises octave filtering and
calibration; this initial CYM design deliberately claims neither certification nor
acoustic calibration.


## v3.0.26 implementation scheduling amendment

Owner-approved bounded capture/analysis correction after v3.0.25 physical continuity
failure. The session retains its one internally stacked 6144-byte worker. Immutable
preparation remains cancellable before I2S. Runtime DSP now separates all-sample
FIR/history/RMS ingestion from a single-owner 128-operation analysis coroutine:
copy/mean -> window -> bit reverse -> butterflies -> band power -> atomic commit.
After each read, analysis gets a 6 ms elapsed budget (plus at most one slice overrun).
A due 50 ms lower-priority tick block follows drained input WITHOUT another analysis
budget; input drains again before analysis resumes. No taskYIELD-only starvation
workaround, extra task/TCB, DMA growth, ISR DSP or raw DMA pointer borrowing.

Full/bass histories each contain two windows in PSRAM; the second window protects
incremental immutable-copy ownership while capture advances. An exhausted copy
margin increments copy_restarts and abandons only that analysis. Actual capture
gaps reset the entire stream/partial job and clear live validity. Control/lifecycle
ownership, Frozen snapshot retention, Resume/gain fresh windows and kernel-owned
stack reclamation remain unchanged. Existing history_resets identifies continuity
epochs; input_samples includes returned/discarded data but cannot count missing ADC
samples. Source time uses uint64 sample arithmetic, with saturating uint32 band ages.

Pending full/bass hops coalesce to the latest complete window; alternation prevents
bass starvation. Windows/frequency coverage/filter/numeric scaling remain unchanged,
but exact old42.667/85.333ms analysis cadence is intentionally NOT promised under
load. Smoothing uses actual selected-window elapsed samples. A spectrum is committed
only after all bands for its group are complete; its age refers to selected-window
end, not completion. Bands older than 500 ms are invalidated. Higher bands need not
wait for bass warmup. No fake/retained live bars bridge a source gap.

See the v3.0.26 operator-guide section for telemetry, exact bench commands and
acceptance. Host cost regression uses actual production arithmetic and installed
SDK functions, calibrated to the captured AGGREGATE elapsed bound, not measured
per-phase target CPU cost. Deliberate 2x arithmetic overload preserves input but
can expire live validity; this is an explicit throughput qualification limit.
No source/test/build result proves the physical report repaired. Parent owns
independent review, all-eight final-source build/package gates and Dev publication;
Stable/main/tags/releases and hardware acceptance are outside this worker scope.
