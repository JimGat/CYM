# Display / engine-I/O observational diagnostic candidate

This candidate measures boundaries only. It is NOT a responsiveness/performance
repair and is NOT physically qualified. Normal CYM remains LVGL; no game-only
native rendering fallback is implemented. .86 transport ownership, 4096-byte
staging, bus/wait budgets, SPI/SD clocks, tick/priorities, audio, touch, orientation,
isolation, startup SD consent and watchdog-subscription guards are unchanged.

## DISPLAY_DIAG

Main emits a task-context summary after LVGL/shared-bus release, no more often
than once per 5000 ms (up to one line for each active mode). `mode=normal` and
`mode=isolated` have independent fixed internal-RAM aggregates. `interval_ms` is
the actual monotonic elapsed reporting interval, not a nominal five seconds;
main stalls delay it. The first interval starts at boot so early clear/flush
counters have the same denominator as their reporting window. No per-stripe or ISR serial output is added.

All `_us` values are wall-time microseconds, NOT CPU usage. Counter/timing deltas
use unsigned 32-bit subtraction (modulo 2^32); sum wrap is possible in long runs.
Maxima ending `_max_us` are since boot, not interval maxima. A single boundary
must be shorter than one microsecond-clock wrap (~71 minutes); early detection
assumes less than half that range. Timer cost and preemption are included.

Exact fields:
- `callbacks`, `accepted`, `rejected`: shared transport-helper invocations and
  successful/error returns. Includes isolated startup clear, not just LVGL.
- `planned`: geometrically planned stripes, including callbacks rejected before
  any draw. `accepted_draws` counts ESP_OK draw returns; `draw_errors` counts
  non-OK returns. Neither proves a color transaction reached the panel.
- `sem_completions`: successful completion semaphore takes. `completed`: takes
  with a matching stable ISR token/time sample; `uncorrelated`: successful takes
  without such a sample. `isr_events_total`: all callback ISR events since boot
  across modes (includes unarmed events). None counts complete displayed frames.
- `admit_attempts`, `admit_rejects`: shared-mutex attempts and failed attempts,
  distinct from callback rejection or completion wait. `admission_us` measures
  the entire admission loop (zero attempts if no mutex); `admission_max_us`.
- `copy_us`, `copy_max_us`: memcpy into owned staging. `draw_us`, `draw_max_us`:
  panel API call, including command/acquire/drain/preemption overhead.
- `wait_us`, `wait_max_us`: post-draw-return completion wait through successful
  task resumption. Missing completion retains bus/buffer and restarts as before;
  no successful interval summary is fabricated for this reset path.
- `draw_to_isr_us`, `draw_to_isr_max_us`: immediately-before-draw timestamp to
  callback ISR timestamp. This is the observable enqueue boundary UPPER WINDOW,
  not exact driver enqueue time or isolated wire time: it includes command work
  before actual color enqueue. No vendor driver instrumentation is added.
- `resume_us`, `resume_max_us`: ISR stamp to owner after successful take, including
  scheduler effects. `early`: ISR arrived at/before draw return. These windows
  overlap `draw_us` and `wait_us`; NEVER sum them as independent CPU shares.
- `callback_us`, `callback_max_us`: transport-helper wall time including admission,
  rejected callbacks and diagnostic overhead. `handlers`, `handler_us`,
  `handler_max_us`: normal main/dialog and isolated main LVGL handlers.
  `residual_us` subtracts helper time inside that handler, clamped at zero;
  render/rotation/callback bookkeeping/preemption wall-time, NOT CPU accounting.
- `g0`..`g3`: first four distinct native helper geometries since boot,
  `widthxheight/payloadB/planned_stripes`; bounded examples, not interval
  histograms. They describe the panel API coordinates after LVGL rotation.
  Typical production logical 480x10 rotates to native 10x480, 9600 bytes,
  three 4096-capacity stripes. Odd widths send exact RGB565 pixels, no padding.

The shared SPI helper is measured on its six consumer profiles. Hosyond S3-35
and WS-S3-5B retain their separate adapters: handler times remain observable,
but shared-helper counters/geometry/completion are NOT adapter timing coverage.
All eight profiles are still mandatory native-build/package gates.

## ENGINE_IO_DIAG

Task-context reporter accompanies existing PERF at most once per 5000 ms; actual
`interval_ms` is printed. `phase` is 0 VALIDATION, 1 INIT, 2 RUNNING, 3 CLEANUP.
Each labeled tuple `VALIDATION=`, `INIT=`, `RUNNING=`, `CLEANUP=` has these EXACT
ordered fields:

    opens,closes,reads,seeks,tells,stats,bytes,failures,admission_us,hold_us,admission_max_us,hold_max_us

The first ten are interval deltas; last two are since session start maxima.
Per-field lock-free snapshots can straddle a worker update; no claim of a
transaction-consistent whole struct. Reports use the same captured snapshot as
next interval baseline, avoiding dropped increments during serial formatting.

Engine wrappers count each fopen/fclose/fread/fseek/ftell/stat operation attempt,
including mutex admission failures, under phase sampled at admission entry.
`bytes` counts fread elements returned * element size; a short EOF read is not
an error unless ferror is set. `failures` includes admission failure or VFS error.
Admission is entry-before-take through take return; hold is take return through
immediately BEFORE give. Diagnostic aggregate updates happen after release;
post-give preemption is NOT misclassified as held time. Original 2000 ms mutex
policy and operation/ownership/cancellation order are retained.

Validation is deliberately bounded transaction accounting: its opens bucket is
initial stat+conditional fopen; reads are seek+read bundles (actual bytes even
on short reads); close is file close. Failed validation admission is counted in
stats; bundled validation seeks/stat are not separate operation counts. Existing
STRUCTURE_BEGIN/END and HASH_BEGIN/END identify validation subphases; INIT_BEGIN,
INIT_END and ENGINE_STARTED identify engine transition. Phase-separated buckets
preserve mixed intervals rather than calling all loading work steady gameplay.

Existing PERF names are unchanged: `displayed`/UI fps are canvas scaling and
invalidation, NOT completed LCD frames; `panel_flushes` is successful helper
callbacks, NOT full LCD frames; `panel_us` includes failed admission. `sd_us`
starts after lock, is fread-only and includes post-release scheduling/metric
work; it is not the new complete admission/hold accounting. `audio_us` is wall
time around blocking I2S writes, not CPU usage; it overlaps other task windows.
No effective-priority sampling is added: base priorities (main1/engine2/PCM3)
are not evidence of effective priority during mutex inheritance. ISR already
yields; no compulsory 20 ms sleep per stripe is inferred.

## Safety, overhead and remaining concerns

ISR only reads installed esp_timer_get_time, publishes lock-free 32-bit stamps
and sequence words in DRAM_ATTR internal RAM, then gives the existing semaphore
and uses the existing yield. No added heap, locks, I2C or logging. Pending token
is published before draw; stale semaphore drain precedes token publication;
early completion remains correlated. A bounded single-attempt seqlock reader
can decline a racing sample; counters never authorize ownership/reuse. No
atomic64 helper is introduced. The S3 IDF S32C1I/PSRAM workaround disables
hardware RMW globally, so GCC always_lock_free is false even for internal
words; the diagnostic channel uses ONLY aligned 32-bit loads/stores. Actual
production-flags probes emit l32i/s32i plus memw without helper calls. The
workaround build checks word size/alignment; other builds retain the lock-free
assertion. Native disassembly, not a removed safety check alone, is the gate. Timer implementations in installed IDF use
IRAM-attributed aliases (systimer on C5/S3, LAC on classic ESP32); LAC register
coherency/retry and hardware-read latency remain an ISR overhead concern.
Native ELF placement/disassembly evidence belongs in the cycle handoff.

Fixed aggregates/geometry/stamp words add a small bounded internal-RAM cost;
clock reads and atomic barriers add per-boundary work. Task serial summaries
also have cost (especially at slow baud). These are diagnostics, not zero-cost
benchmarks. Physical serial/input/panel proof and dynamic internal heap headroom
remain acceptance gates even after host/native gates pass.

ST7796 currently discards underlying tx_param/tx_color errors and returns ESP_OK.
It is intentionally NOT repaired in this observational candidate. Therefore
accepted_draws cannot substitute for true completion; a lying success with no
completion still follows .86 fail-closed reset. Review driver error propagation
separately before selecting a transport repair. Do not classify stripes or canvas
invalidations as full displayed frames, bypass safety, or treat a build as proof
of improved performance.

## Copy-paste operator capture (after parent review/publication only)

Use the parent-approved immutable diagnostic full image/hash at offset 0x0000,
primary USB-C and matching board profile. This worker does not flash or publish.
With the board connected, choose its actual serial device and capture at the
configured console baud (normally 115200), starting BEFORE boot:

    python3 -m serial.tools.miniterm /dev/ttyACM0 115200 --raw 2>&1 | tee cym-diagnostic-serial.log

If USB enumerates differently, replace /dev/ttyACM0 with that device. Preserve
complete logs including boot, DISPLAY_DIAG, ENGINE_IO_DIAG, PERF and reset/error
markers; share no credentials or private capture payloads. Record board/version,
orientation, layout, assets and operator action times separately. Video is useful
for touch-to-visible latency, not a substitute for logs.

1. WS-C5-35 first, then WS-C5-28: quiet normal menu 15 s with no game/storage
   worker; expect normal DISPLAY_DIAG with actual elapsed interval and native
   geometry if flushes occur. Run the same Classic AND Modern navigation:
   Home -> Detect & Defend -> Deauth Monitor -> start -> stop -> save -> Back ->
   Settings/Hardware. Verify capture/Back and touch-to-visible behavior in all
   supported orientations. Idle/no-dirty callbacks are not a panel FPS test.
2. Enter isolated mode through the existing consent path. Capture startup clear,
   structure/hash and engine initialization. Expect phase-labeled ENGINE_IO_DIAG
   alongside existing hash/init markers; compare accepted_draws to completed and
   admission to hold. Do not average mixed init/running into steady FPS.
3. After ENGINE_STARTED, collect 60 s stationary then steady movement/firing,
   including BOOT plus touch and two-contact controls; Exit and observe normal
   reboot. Record lost input, repaint, sound, watchdog and reset symptoms.
4. Keep complete intervals; compute weighted totals using actual interval_ms.
   Maxima are since boot/session, not interval percentiles. Wait for physical
   evidence before any Task6–8 repair/fallback selection. This candidate alone
   does not restore or prove responsiveness.

## Examples

A real HOST synthetic reporter execution is saved in cycle87/host/reporter.log
and full-suite-89.log: it printed `DISPLAY_DIAG mode=normal interval_ms=9500`
with `g0=10x480/9600B/3`, `rejected=1`, `completed=0`. These were controlled
TEST inputs, NOT board timing measurements. An ENGINE_IO_DIAG example is
SCHEMATIC ONLY: `ENGINE_IO_DIAG interval_ms=5000 phase=1 VALIDATION=... INIT=... RUNNING=... CLEANUP=...`.
