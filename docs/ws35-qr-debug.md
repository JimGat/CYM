# WS-C5-35 QR Decoder: aiming and diagnostics

Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35), v3.0.11 Development test candidate.
The camera preview was confirmed visible by the owner on v3.0.9. The v3.0.10 physical log reproduced SD DMA allocation exhaustion during
debug capture and long decode/UI wall times. v3.0.11 is a corrective candidate;
physical frame recovery, UI timing, rotation and recognition acceptance remain
pending. Host/build results are recorded separately in the cycle handoff. Synthetic QR images are not camera evidence.

## Normal operation

Open QR Decoder from either home layout. The full native camera frame is fitted
without stretching or cropping to a 120x160 portrait or 160x120 landscape preview.
The decoder always sees the original 240x320 grayscale input, not this reduced
or rotated display copy. Keep the complete code and its white quiet zone in view.
No new display-driver rotation, mirroring, camera pins or SD frequency is used.

A valid decode hides the preview and shows inert, escaped text. URLs are not
opened. Binary/non-ASCII bytes display as ASCII \xHH; recoloring is disabled.
During camera stop / SD save the result is already visible with `QR decoded -
Saving record / stopping camera...`. Completion reports `Saved <filename>` or
`Not saved: <error>`, retaining the result even on save failure. Scan Again /
Retry is above the potentially long, vertically scrollable result. A retained
camera stop failure blocks restart; do not bypass that gate. Use Back or Home
to leave. Both preserve the existing Modern/Classic navigation contracts.
Normal individual records remain `/sdcard/lab/QR/qr-XXXXXXXX.json`.

## Rotation reference and next hardware checks

The persisted settings index maps directly to LVGL NONE,90,180,270. LVGL's
software rotation maps logical90 to native `(y,W-1-x)` (CCW). The owner's
correct 180 Portrait Flipped preview is the reference; the compensated preview
maps source pixels into logical coordinates as follows:

| Screen setting | Preview transform before LVGL | Raw corners at output TL,TR,BR,BL |
|---|---|---|
| 0 Portrait | 180 | BR,BL,TL,TR |
| 90 Landscape | CCW90 | TR,BR,BL,TL |
| 180 Portrait Flipped | identity (owner reference) | TL,TR,BR,BL |
| 270 Landscape Flipped | CW90 | BL,TL,TR,BR |

Composition with global LVGL rotation is always the same physical180 baseline;
this is not a second global screen rotation. Asymmetric color/coordinate host
fixtures verify all four transforms without reflection. Reopen QR Decoder after
changing orientation; orientation is immutable during an open scan. Settings
are outside this screen, so there is no supported live orientation mutation.

On the board, check all four settings with an asymmetric printed arrow/text,
not only a rotationally symmetric QR: move the target left/right and up/down,
verify framing and lack of mirror. Check270 with buttons/SD on top, expansion
bottom; compare180 with USB-C on top. Report any discrepancy rather than
assuming the mathematical mounting inference is physically qualified.

## Primary USB-C console only

Existing debug controls are unchanged and persist through reboot. Commands are
lower-case; these exact successful responses come from `cym_debug_command`:

    debug on
    Debug ON persisted; applied immediately

    debug status
    Debug ON

    debug off
    Debug OFF persisted; applied immediately

    debug status
    Debug OFF

`debug` or `debug query` also reports `Debug ON` / `Debug OFF`.
Invalid arguments: `Usage: debug [on|off|status|query]`.
Persistence failures: `Debug persistence failed: <ESP error>; unchanged ON`
(or OFF), never a false success. Hardware Options has the existing synchronized
Debug diagnostics switch. This feature never turns debug on automatically and
does not use the GPS UART or expansion connector for logs.

## Capture a useful 20-30 second test

1. Connect the primary USB-C serial console and start saving its text locally.
2. Send `debug on`, then `debug status`; retain the responses.
3. Open QR Decoder. Capture startup allocation/HWM and camera-open markers.
4. Aim at a benign simple code for20-30 seconds. Include white margins. Note
   orientation, movement alignment and whether a result or error appears.
5. If recognition fails, voluntarily use Save Debug Frame as described below.
6. Press Back (or Home). Retain ui_stop, worker_complete/camera_retained and
   worker_park markers. Send `debug off` and `debug status` when finished.
7. Report the observed UI text and share the serial excerpt. Do not send real
   account tokens, personal QR payloads or camera images without reviewing them.

## Voluntary Save Debug Frame

Visible only while scanning AND debug is enabled. Scroll below the preview if
needed. The explicit warning states that the camera image may contain private
QR content; pressing Save Debug Frame is consent for ONE image to be written.
There is no automatic image capture, continuous recording, network or upload.

The worker takes one PSRAM snapshot of the exact native decoder grayscale
input, including the original full field of view and matching numeric metadata.
It then closes/quiesces the camera BEFORE any SD access. A close failure retains
camera ownership and blocks SD/restart rather than freeing a live resource.
The explicit capture pauses scanning after the save attempt; press Scan Again /
Retry to resume. This deliberate pause avoids allocating camera resources again
before the requested image has been recovered. A reopen failure is shown as a
camera error; Back and retry remain available unless ownership is retained.
It writes P5 PGM under:

    /sdcard/lab/QR/debug/frame-0000.pgm

The bounded exclusive filename search chooses the next free0000..1023; it never
overwrites a prior image. Directory creation occurs only on this action; no
SD-Assets update is needed. PGM comments record numeric dimensions, source and
gray stride, screen and decoder orientation, gray statistics and this frame's
candidate/attempt/error counters. No payload is embedded as text metadata.
The PIXELS themselves may reveal sensitive QR data or the surroundings.

While pending: `Saving one camera image... Back cancels pending work`.
Success: `Saved debug/frame-NNNN.pgm` followed by
`Scan paused. Press Scan Again.` on the status label. The preview is hidden once
the worker is safely parked, and Scan Again / Retry becomes visible.
Failure: `Frame not saved: <error>. Retry.` (missing SD, busy/unwritable card,
allocation, write or close failure). After a close/save attempt the scan is
paused, including SD failure; use Scan Again, then press Save Debug Frame again
only if another image is wanted. Snapshot allocation failure leaves the scan
running without closing the camera. A request consumes at most one pending
slot; repeated clicks cannot queue captures. Debug OFF, a debug-generation
change or Back cancels a not-yet-written request, including cancellation while
waiting for the SD mutex. The worker rechecks request validity after admission. An SD write already in progress
may finish; UI teardown retains live worker ownership rather than freeing it.
A successful decode on the same frame has priority: escaped text is published,
the camera closes, and the normal record is saved once BEFORE the optional
image. A failed camera close blocks both writes, retaining the decoded text.
Image failure never overwrites a successful decoded result or saves it twice.
The UI does not synchronously wait for the button's SD operation. Card and
shared-bus latency remain hardware-dependent. Back uses the existing bounded
three-second join and may retain a still-stopping worker; retry later, never
force-free it. A failed write/close removes only its own incomplete image.

For diagnosis, copy the PGM from your SD card yourself, inspect it offline, and
share only a benign test frame voluntarily. It is a real camera input sample;
the generated `printable-simple-qr.png` in the development evidence directory is
only a synthetic print target, not a captured camera frame.

## Interpreting debug output

Summaries are rate-limited to five seconds plus one final summary on exit.
Counters are per scan attempt and reset on Scan Again. `elapsed_ms`, `processed`
and `decode_millifps` give throughput; `decode_us` and `max_decode_us` are decode
work timing (including scheduling). Shape/stride/format are actual acquired
frames, or zero shape if none arrived. Current format0 is RGB565 little-endian.

- frames=0 with timeouts/errors: capture path, not evidence of a QR ECC problem.
  Twelve consecutive acquire failures stop safely. Check last_error and final
  camera/error markers. No frames means gray statistics are not a scene sample.
- frames rising, processed rising, candidates=0: camera and decode loop ran but
  quirc found no candidate. Review the voluntary PGM before blaming hardware,
  focus, printing, lighting, camera packet content or library limitations.
- candidates rising: detection happened. `normal` and `mirror` count attempts.
  Named counts: SUCCESS, INVALID_GRID_SIZE, INVALID_VERSION, FORMAT_ECC,
  DATA_ECC, UNKNOWN_DATA_TYPE, DATA_OVERFLOW, DATA_UNDERFLOW. They include normal
  attempts AND mirror fallback attempts, not just final failures. A format/ECC
  failure is not by itself proof of an optical or electrical cause.
- gray_min/max/mean and dark/light (<64/>191) describe the last native gray
  frame. Flat/limited statistics motivate inspecting the PGM; they are not a
  substitute for it. No private pixel or payload dump appears in serial.
- decoded_payload_length: quirc decoded a payload (length only, including0).
  decoded_displayed_saving proves UI reached the pre-save result path, if the
  save took long enough to be observed by the UI poll.
- camera_close_begin/end: isolate normal-result camera-stop delay/failure.
- qr_start stage=debug_close_begin/end and debug_save_begin/end: debug-only
  memory markers include internal and DMA free/largest blocks. Compare the
  post-close DMA headroom with the v3.0.10 DMA_free=258 / DMA_largest=168.
  Successful close precedes the first SD operation. End value/error0 is success.
  No save_begin after failed close is expected. Scan Again emits
  stage=scan_again_start then camera_open with fresh headroom. A failed reopen
  must report error, not continue scanning with a missing camera.
- qr_camera invalid_response: at most one summary per five seconds on errors;
  incomplete counts short/missing RX completion, header counts invalid frame
  headers, row counts invalid row headers, shape counts length/capacity errors.
  recv_bytes is a byte count only, never packet content. Counters reset on
  camera reopen; a quiet error interval is not proof that a frame was valid.
- record_save_begin/end: isolate SD save delay/failure. End value0 means success;
  nonzero is an errno. A failed save must not discard the displayed result.
- result_published then result_displayed: completed worker publication and UI
  display. worker_park followed by owner reap is the only safe reclaim path;
  done alone is not a join. ui_stop records leaving the screen.

## Scheduler correction and physical timing gate

The installed IDF main/UI task has priority1; v3.0.10 QR worker priority2 can
preempt it for the whole CPU-bound quirc identification/decode. The frame-end
100ms delay does not create UI opportunities inside that work. v3.0.11 changes
only the QR worker to priority1, using the installed 100Hz equal-priority time
slicing. quirc perspective grouping/jiggle and normal/mirror Reed-Solomon work
remain unchanged. This is not a decoder-quality fix and does not guarantee
sub-second UI latency. LVGL wall times include scheduling, drawing and waits;
these logs do not establish that display buffers are too small.

Host tests execute the actual worker and UI poll under a deterministic READY
policy replay during a long mocked decode, including UI cancellation. That
checks priority/admission policy, NOT real RTOS timing. The physical gate is a
comparable 20-30 second capture showing touch/Back responsiveness, handler/decode
wall times, no watchdog faults and an actual recoverable PGM. Measure and report
remaining stalls; do not infer improvement from compilation or the host model.

## Recognition evidence and limits

Independent qrcode/Pillow fixtures exercise native camera-sized canvases,
versions1/2/4/6/10, all four ECC levels, all rotations, mirror fallback, gray,
RGB565-LE and padded row strides; moderate scale, blur and contrast are covered.
A synthetic BF3901 packet traverses the production packet-unpack, grayscale and
quirc pipeline. These are software checks, not an observed physical scan.

The prior1200-byte `Long text ` repeated120 times fixture is version29,564x564
with four-pixel modules. It still has no candidates at0/180 and decodes correctly
at90/270 in the pinned upstream quirc identifier (dlbeer/quirc commit
927d680904dc95fdff4cd9d022eb374b438ff8f2). That high-density limitation is not
silently skipped, is not full QR support, and does not establish why the owner's
printed simple codes failed. No heavy decoder replacement or speculative
multi-pass preprocessing was added. Next physical diagnostics are necessary.

## NVS-preserving board test, parent-controlled publication

Use only the verified WS-C5-35 APPLICATION image at offset0x10000, erase-all OFF.
Do not select the merged full image for the first settings-preserving test.
Match the exact SHA256 and path in the final handoff manifest before writing.
Do not erase NVS, format SD, change partitions, or flash another board's package.
This work does not itself authorize or perform flashing/publication.
