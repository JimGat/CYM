# WS-C5-35 QR Decoder: aiming and diagnostics

Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35), v3.0.12 Development diagnostic candidate.
The owner confirmed v3.0.11 close-before-SD capture twice, recovered the files,
and reopened with Scan Again. Preserve that established behavior. v3.0.12 adds
matched native RGB565-LE plus exact decoder grayscale, once-only completion
claiming, descriptor-accounting observations, format readback and offline
independent-decoder replay. It is NOT a claimed physical camera repair.
Settled-run/discard-startup and exposure changes remain evidence-gated; the
current wake/capture/standby cycle and vendor register program are unchanged.
Host/build results and hardware acceptance are separate gates.

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

The worker copies one native RGB565 frame (153600 bytes) and its exact decoder
grayscale (76800 bytes) into bounded PSRAM: at most 230400 additional snapshot
bytes, one pending request, no frame queue or background rearm. Both are from
the same acquisition, NOT the rotated/reduced preview. The native buffer is
immutable until this sole worker next acquires or closes. Raw is copied before
close, grayscale remains the decoder input, and metadata includes frame_id.
No internal DMA/ISR control storage moves into PSRAM.
It then closes/quiesces the camera BEFORE any SD access. A close failure retains
camera ownership and blocks SD/restart rather than freeing a live resource.
The explicit capture pauses scanning after the save attempt; press Scan Again /
Retry to resume. This deliberate pause avoids allocating camera resources again
before the requested image has been recovered. A reopen failure is shown as a
camera error; Back and retry remain available unless ownership is retained.
It writes a matched P5 PGM and headerless little-endian RGB565 pair under:

    /sdcard/lab/QR/debug/frame-0000.pgm
    /sdcard/lab/QR/debug/frame-0000.rgb565

The bounded exclusive filename search reserves BOTH names at the next free
0000..1023 identity; an existing sibling reserves that identity across reboots.
It never overwrites prior files. Success means both closes succeeded. Failure
removes only the two files created by this attempt; power loss can leave an
orphan, so the two-file operation is not filesystem-atomic. Directory creation occurs only on this action; no
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
and `decode_millifps` give throughput. The separate `timing acquire_us`,
`convert_preview_us`, `decode_wall_us` counters are accumulated owner-task wall
spans (including scheduling), not sensor frame duration or CPU utilization;
acquire includes wake/wait/halt/standby/unpack. The decode wall span includes
quirc identify AND normal/mirror decode; it does not isolate those internals.
Existing `decode_us` and `max_decode_us` are decode
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
  recv_bytes is the SDK's completion accounting, NOT an independent measurement
  of bytes on the sensor wire. `partial_events`, `partial_bytes`, `last_partial`,
  `fake_eofs`, `fake_error`, `done_events` describe this attempt's SDK callbacks.
  IDF fake EOF accounts one current descriptor before publishing accumulated
  bytes. Descriptor-sized short counts can therefore involve accounting/event
  synchronization; they do not alone prove image bytes were dropped. Short or
  over-capacity completions are rejected, never unpacked using stale tail data.
  The first completion consumes armed ownership; a subsequent GPIO edge must
  not run fake EOF against an already-finished transaction. Counters reset on
  camera reopen; a quiet error interval is not proof that a frame was valid.
- record_save_begin/end: isolate SD save delay/failure. End value0 means success;
  nonzero is an errno. A failed save must not discard the displayed result.
- format_readback: debug-only, four bounded read-only comparisons after vendor
  setup. Expected reg12=4 reg3a=5 reg0b=3 reg09=19, match=1, errors=0,0,0,0.
  Failure is observational, not permission to tune registers or bypass capture.
- capture_displayed value=5: explicit capture paused normally, NOT an error.
  error_displayed value=4 remains an actual QR_ERROR state.
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

## Vendor/SDK evidence and bounded diagnostic selection (v3.0.12)

Immutable vendor reference: waveshareteam/ESP32-C5-Touch-LCD-3.5 commit
04e6134cf3e37309b2bec9915189efeace1161bc, under example/ESP-IDF-V554/01_factory/
components/espressif__esp_cam_sensor/:

- sensors/bf3901/bf3901.c: frame header 4 bytes, row header 6, 480 pixel
  bytes/row, 320 rows, total155524. Row check covers four header bytes; the
  next two are not pixel data. Controller spi_cam_decode copies pixel bytes
  unchanged, consistent with CYM packet-unpack (no display byte swap).
- sensors/bf3901/private_include/bf3901_settings.h defines RGB=0x04 and
  G3LB5=0x05. The 2-bit RGB565 table is declared RGB565_LE, despite an
  inconsistent human-readable 1bit/15fps mode name; use rx_lines and format.
- bf3901_set_stream writes0x09=0x03 enabled and0x13 standby. Table starts
  standby;0x0b=0x03 comment says skip2frames. Frame metadata also says drop
  the first SPI packet (not image data). Neither comment proves settled AE,
  repeated-wake behavior or safe rearm timing for CYM's PARLIO path.

Installed IDF6.0.2 commit7101770dc6db2667b3c477cc31365dd1acd6db4e,
components/esp_driver_parlio/src/parlio_rx.c: default_desc_done_callback adds
one descriptor length; trigger_fake_eof stops/resets GDMA, resets shared PARLIO,
then calls descriptor and EOF callbacks synchronously. It refuses a paired TX.
Disable stops DMA and clears the transaction; CYM must retain callback/context
and buffer ownership until teardown succeeds. No vendor rearm task/unsafe
free/delete path or borrowed-I2C deletion was imported. Cache alignment,
DMA-capability admission and TX exclusion are retained unchanged.

Do not enable a continuously running sensor just by removing standby. Required
before a settled acquisition experiment: trace clock/CS and SDK completion
ordering with the new counters, establish a frame-boundary rearm contract,
prove quiescence at cancel/timeout/short/close failure, then bound startup discard
count and wall budget. No such hardware proof exists in this candidate.
Exposure controls likewise need a sensor register specification (field meanings,
ranges, auto/manual dependencies and readback) AFTER actual paired format
verification. The vendor initialization table alone is not that specification.
No guessed gain, shutter, threshold or sensor-format settings are provided.

Select diagnostics without changing firmware registers:

1. Normal/debug OFF: no voluntary snapshots, no new diagnostic logs.
2. Debug ON plus Save Debug Frame: one matched pair, stop before SD, explicit
   Scan Again. Exercise two cycles, missing/full SD, debug OFF while pending,
   Back/Home while pending, and benign successful QR plus a pending image.
   A valid result must remain visible, save once before the optional pair,
   and survive pair failure. No write/reentry after a retained close failure.
3. Offline replay: exact LE RGB (production), byte-swapped RGB, LE BGR and
   byte-swapped BGR are four bounded interpretations of the SAME raw file.
   These are diagnostic comparisons, NOT firmware or sensor tuning. Correct
   production LE gray should match the PGM at every pixel. PGM alone cannot
   establish original RGB byte order or row packing.

On the authorized dev host (outputs may contain private image-derived hashes;
keep them private; no payload text is printed):

    cd /home/dev/projects/CYM-NM28C5-jarvis-ws35-docs
    export TMPDIR=/home/dev/projects/cym-qr312-evidence
    /home/dev/projects/cym-qr308-evidence/host-venv/bin/python tools/qr_frame_replay.py /path/to/frame-0000.pgm --rgb565 /path/to/frame-0000.rgb565 --output-dir /home/dev/projects/cym-qr312-evidence/operator-replay

Expected: replay-results.json with production quirc counts/error histogram and
independent ZXing validity/length/SHA256; `little_rgb` mismatch count0. No
payload/URL is printed. Pillow and zxing-cpp3.1.1 are installed in that host venv;
cc builds the checked-out production decoder into the output directory.
Omit --rgb565 for older PGM-only captures. A successful independent decoder
with failed quirc isolates a library limitation on that exact image; failure
of both does NOT establish printing, optics, exposure or electrical cause.

Repeat operator checks at0/90/180/270, dark-neon, Modern Tools and Classic Home.
Preserve primary USB-C only, existing NVS and app offset0x10000, erase-all OFF,
SD20MHz, disabled WS35 BOOT, GPS GPIO28 and audio/display/touch/radio ownership.
Record actual touch/Back latency and acquire/convert/decode spans; no measured
UI-speedup claim follows from equal-priority policy or a green host test.
