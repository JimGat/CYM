# Audio RTA beta operator guide

Development v3.0.23, initially enabled only for the **Waveshare
ESP32-C5-Touch-LCD-3.5 (WS-C5-35)**. This is a software-verified beta for owner bench
testing, not hardware-qualified acoustic instrumentation. Existing co-developer
attribution to @birolt29 is preserved.

## Install the Development beta

Open https://jimgat.github.io/CYM/beta/?board=ws-c5-35 in desktop Chrome or Edge.
Use the board's primary USB-C data port, select **Development**, and confirm
**WS-C5-35 / v3.0.23** before installing. Leave **Erase OFF** for a normal update.
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
  Default0dB is conservative and not yet acoustically qualified. Select a gain to
  reset histories, resume/warm up and show actual configured gain. Close cancels.
  No gain NVS persistence. No AGC/noise suppression/AEC, recording/export/streaming.

The different FFT resolutions create an intentional characterized crossover boundary
at266.70Hz +/-23.44Hz. Host tone sweeps measured up to1.8432dB adjacent-band sum
error there; the <=1dB fidelity criterion excludes this stated boundary. Do not hide
this with animation or interpret it as a certified third-octave instrument.

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
