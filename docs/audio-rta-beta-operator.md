# Audio RTA beta operator guide

Development v3.0.27 source cycle, initially enabled only for the **Waveshare
ESP32-C5-Touch-LCD-3.5 (WS-C5-35)**. This is a software-verified beta for owner bench
testing, not hardware-qualified acoustic instrumentation. Existing co-developer
attribution to @birolt29 is preserved.

Independent verification passed 702 unit tests (one private-capture skip), 21 host
runner entries, all eight board builds and 32 packaged firmware artifacts at v3.0.27.
Source/configuration and unrelated-file preservation gates passed. Install only the
exact published image identified by the delivery report and its downloaded hash.
Physical acceptance remains pending; these are software/build results only.

## Install the Development beta

Open https://jimgat.github.io/CYM/beta/?board=ws-c5-35 in desktop Chrome or Edge.
Use the board's primary USB-C data port, select **Development**, and confirm
**WS-C5-35 / v3.0.27** before installing. Leave **Erase OFF** for a normal update.
Do not use a different board image or double-press BOOT. No device was flashed by
the development/verification process; owner flashing and physical checks are separate.

The delivery report supplies the exact immutable full-image URL and downloaded
SHA-256. A full merged image uses offset `0x0000`; the application-only image is a
different file and must not be substituted at that offset. Stable is not changed.

## Open and exit

- Modern Home: Tools & System -> Audio RTA (alongside Settings, not inside Settings).
- Classic Home: additional Audio RTA microphone tile. Other tiles remain present;
  scroll the existing Classic tile container if needed.
- Back returns to Tools & System in Modern, Classic Home in Classic. Home retains
  the selected home layout. Either route detaches the refresh timer and requests
  cancellation before the existing application navigation deletes the widgets.
- Saved Screen Orientation is respected. Landscape 480x320 is preferred; both
  landscape rotations and both 320x480 portrait rotations have the same controls.
  Changing orientation through existing FSD returns Home/stops RTA; reopen normally.

## Expected displays and controls

Dark plot: 24 logarithmic bands nominally20Hz..20kHz, -90..0dBFS; green/amber/red
indicate digital input level, NOT hearing safety. Light markers retain peak levels.
The original small microphone artwork is a feature-local U+E100 font, not a replacement
of the existing symbol font. It is compiled only for WS35.

Starting is honest: full-rate bands need85ms, first9 bass bands need683ms of fresh
input. The selected-band detail shows exact frequency edges and analysis age. Tap or
drag ANYWHERE on the chart to select; bars are not tiny individual buttons. Overall
RMS and sample peak use the latest4096 input samples (85ms), not the sum of stale bass
and newer treble bands. Clip count counts original samples near digital saturation.
No SPL, A/C weighting, microphone calibration or ultrasonic promise is made.

- Freeze/Resume: holds the displayed measurement/peaks while the owned screen keeps
  draining capture. Resume discards stale histories and warms fresh windows.
- Fast/Slow: linear-power time constants125ms/1s, based on input sample time.
- Reset Peaks: clears peak markers, not the input or averaging state.
- Gain: vertically scrollable bounded overlay, supported0,6,12,...42dB codec steps.
  Opening temporarily pauses analysis while capture is still drained. Close or
  selection restores the earlier user Freeze choice, not an unconditional Resume.
  On a running return the analyzer discards old history and warms fresh windows;
  a user-frozen display stays byte-for-byte frozen until Resume.
  Gain is loaded from private NVS `audio_rta/gain_db` before codec/capture startup.
  Default24dB is used only if absent/corrupt/invalid; valid saved0dB is preserved.
  Only supported0,6,...42dB steps are accepted. No erase or unrelated setting edits.
  No AGC/noise suppression/AEC, recording/export/streaming.

The different FFT resolutions create an intentional characterized crossover boundary
at266.70Hz +/-23.44Hz. Host tone sweeps measured up to1.8432dB adjacent-band sum
error there; the <=1dB fidelity criterion excludes this stated boundary. Do not hide
this with animation or interpret it as a certified third-octave instrument.

## v3.0.25 capture correction and retest

The C5 HWv2 default MONO configuration selects BOTH slots. The installed SDK HAL
reduces that selection to one TX DMA slot, but leaves both RX slots enabled.
RX therefore admits two words per LRCLK into a mono-sized DMA ring while the
silent-TX-paced reader drains one. This slot mismatch produces continuous gaps;
the existing safety logic rejects those batches before usable analysis windows form.
The adapter now explicitly selects the ES8311 LEFT ADC slot for RX. TX clocking,
DMA ring size, task priority, internal stack, codec gain and the DSP remain unchanged.

The regression compiles production adapter/session/DSP together with the installed
SDK's actual default macro, HAL/LL slot selection, I2S callbacks and read/write bodies.
Using C5 TRM section35.10.1.1 for enabled-slot FIFO admission, the old configuration
fails with continuous overflows and no valid spectrum. The corrected configuration
passes the same startup/phase/scheduler-gap matrix and produces the known synthetic
1kHz band, measured nonzero PCM RMS/peak, and all24 valid bands after fresh warmup.
This is a source-grounded timing reproduction, not a physical C5 timing measurement.

DMA discontinuity is also separate from the I2S driver return code. Genuine driver
invalid-state/read failures terminate safely rather than being retried as lost PCM.
Real gaps still discard the affected batch, clear live validity and require fresh
contiguous windows; Frozen holds its captured display until Resume.

First retest with `debug on` through primary USB-C, then repeat with `debug off`.
Use speech/music, then known external tones. Expect advancing `sequence`, `frames`
and `history_samples`, non-default RMS, and `valid=ffffff` after uninterrupted bass
warmup. An isolated startup gap may recover; overruns increasing with every read,
permanent zero history or a stationary marker are failures, not valid silence.
Check high bands before bass warmup, Freeze/Resume, Gain, Back/Home, immediate reopen,
both menus/orientations, settled cycles and the soak below. Capture complete
AUDIO_RTA diagnostics if any failure persists; do not log raw PCM or private payloads.
Physical microphone response, frequency accuracy, throughput and leak-free teardown
remain owner-bench acceptance gates, not claims established by the host harness.

## Failures and cleanup

Busy/insufficient PSRAM/internal memory, missing codec, clock/format/read errors and
initialization failures leave Back/Home usable. Long errors can scroll vertically.
There is no hidden startup retry; Back then reopen explicitly after cleanup.
PCM/history/FFT allocations use PSRAM with no internal fallback. Runtime admission
rejects an observed session internal delta over24KiB, including internally allocated
capture worker stack; the configured workspace ceiling is256KiB. Concurrent unrelated
allocations can conservatively reject admission. Compile/host sizes are not measured
hardware free-heap evidence.

A detached non-UI owner finishes bounded-read cancellation; re-entry stays busy until
cleanup ends. The worker closes codec/I2S, releases its owned buffers after their
last use, then self-deletes. FreeRTOS owns its dynamic 6144-byte INTERNAL stack/TCB
and reclaims them on the next idle pass; a closed session is not a kernel-task join.
There is no second cleanup task. Compare heap only after a settled idle interval;
immediate reopen can safely report memory pressure until kernel reclamation finishes. No forced deletion of a running or
blocked capture task or UI callback, no global main-loop polling. Delayed cleanup is
logged on PRIMARY USB-C, and persistent delay fails qualification. No second I2C bus,
shared power toggles, radio-wide shutdown, display-buffer reduction or SD-speed change.

## Read-only USB operator checks

Primary USB-C at115200; do not use expansion/JST UART, flash/reset automation or log
PCM/private payloads. First return Home manually with no RF operation active.

    python3 tools/fsd.py ws-c5-35 path "Tools & System>Audio RTA" --port /dev/ttyACM0
    python3 tools/fsd.py ws-c5-35 path "Audio RTA" --port /dev/ttyACM0

Use the first command in Modern and the second in Classic. Expected: real tile taps,
matching navigation stack, screenshot/heap capture and Back traversal. Paths are
reviewed WS35-only; other boards reject RTA before opening serial. FSD artifacts/raw
console output stay local and may contain privacy-sensitive existing application logs.
No hardware was connected for implementation validation, so these are bench procedures,
not a claimed run. FSD does not qualify signal fidelity or leaked DMA by itself.

## Mandatory physical beta bench (parent/operator)

Record version, debug ON/OFF, menu, orientation and source/microphone limitations.
1. Both menus x all4 rotations: real microphone tile, all4 controls>=44px, readable
   selected-band details, gain overlay/error scrolling; capture real screenshots.
2. Speech and known external bass/mid/treble tones at documented configured gain;
   measure actual LRCLK48kHz/BCLK1.536MHz, channel format and differential mic/bias.
   Laptop/phone speakers do not establish deep bass, full20kHz or ultrasound response.
3. Freeze/Resume, Fast/Slow, gain changes and clipping/Reset Peaks; no capture after
   leaving, no output from speaker (DAC muted/owned silent TX, shared power untouched).
4. Ten settled entry/exit cycles PER menu via Back/Home and FSD orientation changes:
   record free/internal/DMA/largest block, heap integrity, task/timer/channel counts;
   distinguish one-time SDK caches and require no monotonic leak. Normal stop<=500ms.
5. Fifteen-minute capture soak: quiet-menu DSP/capture wall-time<50%, responsive touch,
   no unexplained overruns/watchdog/panic. Overrun must invalidate/warm histories.
6. After exit verify Clock AP/mDNS, NTP-first/Client time, GPS GPIO28/RTC, unchanged
   SD20MHz, display/touch, QR camera, existing audio and radio/background services.

The approved delivery sequence is independent software/build review, Dev beta
publication, then owner bench qualification. These physical checks remain mandatory
before hardware acceptance or any Stable-promotion decision; publication of a test
beta does not establish working microphone input, acoustic calibration, no-leak
teardown or CPU performance.

## v3.0.22 crash correction and first retest

v3.0.21 was physically reported to panic on RTA entry. Its exact ELF decoded the
fault to LVGL's string formatter called by RTA refresh; float formatting is disabled
in the target configuration. RTA now formats floating-point labels through bounded
libc buffers and copies text into LVGL, without globally enabling float formatting.
The same capture showed I2S DMA allocation failure. Removing the unnecessary
3072-byte cleanup-task stack (and its TCB) reduces startup internal demand while
retaining the 6144-byte capture stack, DMA ring, DSP, display and radio settings.
This is a software correction, not proof that hardware now captures successfully.

First retest with debug on via primary USB-C, then repeat with debug off. Expect
AUDIO_RTA stage=before_task, stage=before_i2s and either a live plot or a safe error
with Back/Home usable. Copy the complete AUDIO_RTA/I2S lines and any panic if one
occurs. Startup boundary logs contain heap totals only, never PCM. A memory error
without reboot is safe failure, not successful microphone qualification. Test Back,
Home, immediate re-entry and settled cycles in both menus before the soak above.

Official recorder/BSP references and deliberate differences are in the
[WS-C5-35 board document](hardware/waveshare-c5-touch-lcd-35.md#official-recorder-reference).

## v3.0.23 watchdog correction and retest

The owner's v3.0.22 capture confirms successful audio initialization followed by
main/IDLE watchdog starvation while `audio_rta` ran. The matching ELF placed the
captured return addresses in cosine/table construction called from overrun recovery.
The old recovery rebuilt all windows/twiddles while RX remained active, making
further overruns possible, with no blocking scheduling point in that retry path.
This is distinct from the earlier allocation/formatter failure.

Preparation now builds those tables before opening I2S, with cancellable tick
blocks between bounded table chunks. Overrun, gain change and Resume reset only
stream histories; prepared tables are retained. The worker checks a 50 ms scheduling
budget on every loop path and blocks for one tick when due, including immediately
ready, frozen and overrun reads. This is not a measured 50 ms response guarantee:
one processing operation can extend a check interval. The 30-second watchdog is
unchanged, as are capture stack size, DMA ring, display buffers, radio settings and
all other boards' feature gates. No task-priority change or main-loop polling.

With debug on, expect `before_task`, `before_dsp_prepare`, `before_i2s`, then
`configured48k mono16` or a readable error. Table preparation deliberately takes
cooperative scheduling pauses before input starts; the UI must remain usable.
Try Back/Home during that initial preparation as well as after a live plot appears.
There must not be another long frozen interval followed by a watchdog restart.
Repeat with debug off, both menus, Resume and gain changes, immediate re-entry,
then the settled-cycle and soak checks above. Persistent warmup/overruns or a
nonresponsive plot still fail microphone qualification even without a reboot.

Production-code host tests reproduce the overrun feedback and missing blocking
points, check cancellation before I2S acquisition, and verify history reset against
fresh numerical initialization. Those tests do not measure target CPU load, actual
microphone input, display response, power use or physical teardown reliability.

## v3.0.25 scoped responsiveness repair

The owner's v3.0.23 capture showed approximately 2.69 UI handler calls/second and
99.2% handler wall occupancy, including worker preemption. Audio initialization
succeeded; neither a dead microphone nor a particular overrun rate was proven.
The repair reduces both compute and rendering workload without changing microphone
pins, 48k mono16, the 4x256 DMA ring, display buffers, 6144-byte internal stack,
watchdog, clocks, SD20MHz, NVS or background services. No new task is added.

FIR/FFT hot loops now use integer histories, Q27 FFT values, Q30 coefficients and
64-bit intermediate products; FFT scaling is one half per stage (FFT/N).
Immutable band-bin weights, Hann windows and smoothing coefficients are prepared
before I2S, never rebuilt after a gap. The 193-tap filter and 24 exact logarithmic
bands remain unchanged. RMS uses an exact rolling PCM square sum; sample peak
uses integer comparisons. Floating point remains at preparation and band power/dB
conversion, not the per-sample FIR/FFT butterflies. Both sample windows/hops and
the documented crossover limitation above remain. These are implementation
reductions, NOT measured C5 CPU percentages or proof of microphone response.

The chart's newest scalar snapshot is checked every 50ms (about 20 visual updates/s
is a target, not hardware evidence). Only changed bar/peak rectangles are damaged;
unchanged model data causes no invalidation. Static titles/axes are clipped away
from bar-only draws. Metadata is limited to 250ms except state, validity, gain,
staleness and direct selection changes. Back/Home detaches immediately and requests
cancellation; DSP now checks that request between input/window chunks and FFT stages.
The existing 50ms cooperative scheduling budget does not force a 10ms sleep per
512-sample block. Neither mocks nor this budget guarantee exact touch/stop latency.

Starting means no processed input yet. Warming means no valid bands; Partial means
full-rate bands are ready while bass warms. Live requires all bands valid, not
merely one successful read. No signal means valid windows at the digital floor,
not proof of an absent microphone. Stale means the most recent RUNNING copy is
over 500ms old. Frozen deliberately holds its entire spectrum/peaks, including
when draining reports a gap; Resume resets history. Zero-length successful reads
do not advance sequence, analysis frames or window validity.

### Bounded primary-USB diagnostics

With the existing debug setting ON, `AUDIO_RTA: diag` appears at most once/second
while the worker is actively reading (no catch-up queue). Debug OFF suppresses
these new periodic lines immediately at the next emission check. Existing startup,
error and cleanup logs retain their prior behavior. No PCM, raw payload, file,
network upload or expansion/JST UART output is added. Stop/preparation/errors may
end before a periodic line is due; absence of that line alone is not a mic diagnosis.

Field contract (all counters scoped to generation unless stated otherwise):

- generation: session identity; state: CLOSED=0, STARTING=1, RUNNING=2, FROZEN=3,
  STOPPING=4, ERROR=5. RUNNING alone still does not prove valid bands.
- samples: cumulative PCM samples returned by reads, including Frozen, discarded
  gap data and the final cancelled read. Not total ADC-produced or missing samples.
- history_samples: processed contiguous samples since the last history reset;
  held while Frozen. It is not the lifetime capture count.
- sequence: complete nonempty scalar publications, not reads, FFT frames or UI draws.
  v3.0.27 coalesces publication at >=2400 input samples; every read still ingests.
- frames: cumulative completed full OR bass analyses from published snapshots;
  a partial/cancelled analysis is not published or counted here.
- valid: hexadecimal 24-bit mask; first nine bits are bass. `fffe00` is full-rate
  only, `ffffff` all ready, `000000` warming/no valid windows.
- overruns: reads reporting a discontinuity, NOT the number of raw ISR overflows,
  lost samples or DMA descriptors. resets: actual gap/gain/Resume history resets.
- reads: all completed board reads. read_us/process_us: cumulative elapsed
  read/DSP+snapshot time, with max_read_us/max_process_us maxima.
- max_work_us: maximum one loop body's elapsed work (gain/read/process/publish);
  excludes the top-of-loop scheduling pause and the log's own output time.
- All timing is microseconds of WALL time including preemption, read blocking and
  any in-DSP cooperative pause. It is not exclusive CPU time; do not add overlapping
  maxima, equate read waits to CPU load or treat host simulated time as C5 timing.
- rms_x10/peak_x10: held spectrum's overall input level in tenths of dBFS, not SPL;
  -1200 is the floor. clips counts near-saturated original processed PCM samples
  since history reset, held while Frozen. Never a raw/private signal dump.

Ask for a complete 10-second primary-USB capture with debug ON, then repeat OFF.
Expected healthy interpretation: samples grow at roughly 48000/s under real input,
sequence and frames progress, full bits become valid after 4096 contiguous samples,
bass after 32768, and overruns/resets do not repeatedly clear the windows. The
85/683ms windows are sample requirements, not promised wall-time from tapping.
Increasing samples but history_samples repeatedly low with overruns/resets identifies
a continuity-reset loop. Growing samples/sequence but few frames or large process
maxima suggests compute backlog. Stable valid masks and progressing frames with
no visible motion points toward render/level/gain inspection; correlate existing
UI_DIAG/DISPLAY_DIAG rather than declaring a microphone fault. Valid windows at the
floor suggest zero/very quiet input; positive clipping levels suggest gain/format
inspection. Frozen has growing samples/reads but held history/sequence/levels by
design. samples=0 plus errors or nonprogress requires checking I/O/init first.

### Regression impact and owner retest

Host regression uses production DSP/session and real pinned LVGL under sanitizers:
independent tones/noise/floor/DC/alias/crossover/partition references, cancellation,
no-data/gap readiness, debug gating and delayed kernel reap/reentry. Chart tests
compare partial and forced-full framebuffer output for decreases, peaks, validity
loss, floor/clipping and gain-overlay expose across both menus/all four rotations.
Host pixel/work reductions and numeric references are not target refresh, power,
heap, acoustic or leak measurements. DSP workspace increases slightly to cache
immutable quantities; exact old/new target sizes belong in the delivery handoff.

Parent/operator must run the mandatory physical bench above. Especially retest
Back/Home during preparation AND active FFT, silence/speech/known bass/mid/treble
input, gain/Freeze/Resume/Reset Peaks, debug ON/OFF, visible throughput and 15-minute
continuity. Record diag sample/frame/valid/overrun/reset deltas and elapsed maxima
alongside UI_DIAG; verify settled resources and unchanged Clock AP/mDNS/NTP,
Client time/GPS/RTC, SD20MHz, display/touch, QR camera, audio/radio transitions.
No microphone capture, 20Hz-20kHz acoustic fidelity, 20fps, stop bound or no-leak
endurance is hardware-qualified by the software repair alone.


## v3.0.26 bounded capture/analysis scheduling candidate

The owner's v3.0.25 capture still showed periodic high-band flashes followed by
continuity resets: maximum processing elapsed 66.324 ms versus nominal 21.333 ms of
4x256-sample DMA storage. Those spans include tick sleeps/preemption, not pure CPU.
The previous host clock charged I/O/timer calls but not arithmetic/FFT itself;
its green result did not establish sustainable target throughput or bass readiness.

This candidate keeps ONE owner and its 6144-byte INTERNAL capture stack. No second
worker, task-control placement change, DMA enlargement or lower sample rate is used.
After each input read, the owner ingests all contiguous PCM into FIR/history/RMS.
It services analysis in 128-operation slices with a 6 ms elapsed analysis budget per
read; the last slice may overrun that budget. It drains again before more analysis.
One tick of lower-priority UI/IDLE admission is due every 50 ms; it occurs after a read,
not concatenated with a full analysis budget. This is not a hard target latency or
CPU-load guarantee: driver waits, preemption and debug logging still take wall time.
TX/RX/codec configuration and the synchronous board read/write path are unchanged.

Full 4096/48k and bass 2048/3k windows, all 24 exact log bands, Q27/Q30 arithmetic,
normalization and the FIR alias filter are retained. Pending ANALYSIS hops coalesce
when busy: the next alternating full/bass job takes the newest complete window,
not a queue of old FFT requests. PCM is not skipped to accomplish that. Fast/Slow
energy averaging uses the actual window-to-window input-sample interval, preserving
125ms/1s time constants despite variable analysis cadence.85/683ms are minimum
contiguous INPUT warmup lengths, not a guarantee that computation has finished then.
High bands can complete before bass and must continue updating afterward.

Histories reserve a second window in PSRAM so a bounded copy remains valid while
input advances. A copy delayed until its overwrite margin is exhausted is abandoned
and retried from a newer window, never read through invalid borrowed storage.
No raw DMA pointers escape the installed driver. Analysis commits only on complete
work; stop/gap/gain/Resume discard partial work. Real input gaps still clear live
validity and require fresh contiguous histories. Frozen alone preserves its explicit
snapshot through gaps. Window ages are based on the actual selected input end,
not FFT completion or UI publication. Bands over 500 ms old are invalidated, not
shown as fresh live data. PSRAM growth and target memory deltas are in the parent
handoff; no new internal stack or large internal allocation is introduced.

Additional debug-only fields: `slices`, `phase` (0 idle,1 copy,2 window,3 bit reverse,
4 FFT,5 band power,6 commit), `copy_restarts`, `max_slice_us`. Slices/restarts are
since the latest history reset; max_slice_us is the session maximum elapsed slice,
including preemption. Existing resets form the source-continuity epoch; analysis
ages are relative to that epoch. `timestamp_us` now marks the latest input read
boundary, not delayed DSP publication. `process_us` includes ingest, bounded work,
snapshot and scheduling checks but excludes the separate lower-priority tick pause.
Counters do not measure ADC samples lost during a gap. No PCM/private payload is logged.

### Exact owner retest request

Only after the parent supplies the independently verified Dev image/hash:

1. Confirm WS-C5-35/v3.0.26 and primary USB-C. At Home enter `debug on`, then
   `debug status`; expect enabled. Open Audio RTA in landscape Modern/Tools and System.
2. Capture at least 15 seconds with speech/music and suitable known 70 Hz/1 kHz tones.
   Expect high bands before bass; then continuing `valid=ffffff`, history growth,
   advancing frames and varying window ages. Samples should grow near48000/s.
   Repeated overrun/reset growth or flashing partial/blank masks remains FAILURE.
   Large max_slice_us indicates an unexpectedly long slice/preemption; it is not
   exclusive CPU time. A bounded initial gap may recover with fresh warmup.
3. While active, test Freeze/Resume and gain, then Back/Home DURING work; reopen
   immediately and after settled idle. Frozen must hold exactly; Resume/gain must
   warm new input. Stop must not publish partial analysis or require an LVGL lock.
4. Enter `debug off`, `debug status`; expect disabled and no periodic diag lines.
   Repeat the 15 second continuity check visually, then both menus/all rotations,
   ten settled exit cycles and the mandatory 15 minute soak above. Record UI/heap/
   DMA/task/channel observations and preserved background features.

The aggregate-calibrated host cost model charges actual production q30 operations,
FIR-input chunks and scalar/snapshot work; it fails v3.0.25 and passes this candidate
at the captured aggregate cost envelope, including variable 2/6 ms preemptions and
all producer phases. It does NOT contain measured per-phase target CPU timings.
At deliberately doubled arithmetic cost, capture stays continuous but some bands
age out; the test requires honest invalidation, not a false all-live claim. Thus
physical sustained full-band throughput, UI responsiveness, resource settling and
microphone/frequency response remain UNQUALIFIED until Jim's bench capture.


## v3.0.27 gain, render isolation and scan-exit candidate

The independent parent gate passed all eight final-source builds, package versions
and hashes, including the unconditional aborted-scan late-event regression. No
physical speed measurement was performed. The checks below remain owner-bench
requirements, not performance claims inferred from compilation.

### Gain selection, save failures and retirement

The single existing capture worker loads/saves NVS outside the LVGL lock. It
validates the supported gain steps, applies a changed codec setting first, and
only then sets/commits NVS. The displayed applied gain is not advanced on codec
failure. A failed NVS open/read/set/commit is reported by a distinct stage/error
in AUDIO_RTA logs and copied snapshot, without claiming a successful save.
The Gain button says `saved` only when the last committed value equals the
applied value; `unsaved` marks an NVS error. Load fallback is24dB, never inferred
from zero. Read errors do not erase or automatically overwrite the stored key.

Requests queued faster than the worker consumes them coalesce to the latest
supported value. An identical selection or refresh never re-writes flash, and a
failed save is not automatically retried by refresh/identical selection. To retry
explicitly, choose a different value and then the wanted value. On reopen/reboot,
the last successfully committed setting is loaded, not an uncommitted selection.
Exit before the worker processes a queued selection discards it. If processing
has already begun, apply/commit may complete before bounded worker retirement;
no UI callback waits for flash and no new task/stack is created. A flash stall
can still produce a real capture gap; normal discontinuity handling remains on.
A codec failure ends the session with the earlier applied/committed values still
truthfully reported. Back/Home deletes the popup without sending Resume to the
retiring session. Starting, zero-sequence Frozen and errors remain explicit.

### Responsiveness evidence and limits

Existing unchanged-label and band-damage suppression is retained, not newly
claimed. The chart now declares/draws an opaque background using pinned LVGL's
own style/cover path, so bar damage can stop at the plot rather than redraw the
underlying page. Native real-LVGL tests require COVER, zero unchanged flushes,
bounded single-band damage and byte-identical partial/full exposed framebuffers
for both home layouts and all four rotations, including overlay dismissal.

Inspection of the linked v3.0.26 WS35 ELF found software floating-point helper
calls in retained DSP paths; this is static evidence, not runtime attribution.
The actual worker called the full scalar snapshot (4096-sample peak rescan plus
logarithms) once per capture read although its UI consumes every50ms. A native
500-processed-read run counted500 such snapshots before,100 after publication
coalescing at >=2400 input samples (five512-sample blocks, nominal53.3ms).
Every-sample ingestion and every bounded incremental analysis slice are unchanged;
DSP numeric math and windows are byte-identical to v3.0.26. Copy publication can
lag a newly completed high/bass job by up to one publication interval. This is
not physical20FPS, C5 handler speed, CPU utilization or an acoustic qualification.
The accepted v3.0.26 continuous RX/single-owner design, priority/tick admission,
6144-byte internal stack and v3.0.25 RX LEFT admission remain unchanged. No DMA
buffer enlargement, task/priority/watchdog tuning or sample-rate reduction.

RISC-V32 ABI-only sizeof probes give session64->64 bytes and snapshot448->464
bytes (16 bytes per copy), with unchanged DSP source/workspace. This ABI probe is not a physical heap result. Independent package/ELF comparison
measured linked internal growth of 48 bytes on WS-C5-35, 32 bytes on NM-CYD-C5
and 16 bytes on each of the other six boards. DSP source/workspace and the
6144-byte internal capture stack are unchanged. NVS transient library allocations,
flash latency and physical internal/DMA heap costs still require bench measurement.

### WiFi Scan & Attack exit ownership

The owner-supplied exit-rebuild patch is retained: screen-active gating, cleared
stop state and navigation pointers. Additional narrow lifecycle corrections
bind finalization/repeats to the successfully started scanner ticket, reject
already-dispatched older completions during immediate reentry, display failed starts rather
than a permanent spinner, and re-register the stop hook after results-page
construction (which itself runs outgoing teardown). A failed repeat finalizes
the accumulated results. Background scans and shared results are not aborted
by the SAS stop hook; existing handshaker/OT/blackout dispatch exclusions stay.
No supplied author header existed, so no contributor identity is invented;
existing @birolt29 co-developer credit is preserved.

Independent review reproduced the aborted-scan late-event race and corrected
admission: `wifi_scanner_abort()` requests the stop without marking the scanner
idle. The documented SDK SCAN_DONE retires the old ticket and reads the results
before reopening admission. Immediate active/passive restart returns busy until
that event drains; no blocking wait occurs under the UI lock. This case now runs
unconditionally in the production-extraction scanner test. Existing callers that
abort before taking radio ownership (OT Surveyor, handshaker, blackout and Wi-Fi
UI cleanup) require physical transition/retry checks because this deliberately
changes their short admission window. No guessed SDK scan-ID mapping is used.
A missing driver completion leaves admission closed rather than misattributing
an old event; normal RF error recovery and owner diagnostics remain important.

### Owner retest checklist after parent publishes the verified image

1. Verify WS-C5-35/v3.0.27 on primary USB-C, Erase OFF. `debug on`: expect gain
   load/apply, advancing input near48k samples/s, steady full validity, no new
   sustained overruns, and improved/usable controls; record handler warnings
   without mistaking wall time/preemption for CPU usage.
2. Open Gain while running: plot holds but capture drains. Close: fresh warmup,
   then live. Freeze first, open Gain, select/close: remains Frozen until Resume.
   Repeat from preparation and use Back/Home with popup open; immediate reopen
   must not resurrect the old screen. Both menus x all rotations.
3. Select0dB, leave/reopen and reboot:0 is restored. Repeat24 and42; Gain says
   saved only after commit. On injected/real save failure expect unsaved plus
   stage/error log, no false persisted value, and earlier committed value after
   reboot. Codec failure must show Error and keep Back/Home responsive.
4. With a bounded authorized Wi-Fi scan, Back/Home/forward to targets before
   completion: no forced results-page resurrection. Immediate reentry while a
   scan is still owned elsewhere shows start failure; Back/retry after completion.
   Normal adaptive completion and results-page Back/Home still work. Retest both
   menu routes and other existing background scan consumers without RF changes.
5. Repeat with `debug off`, settled open/close heap checks and extended soak.
   Capture private diagnostics only; do not publish raw captures or payloads.
