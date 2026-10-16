# WS-C5-35 QR Decoder candidate

Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35) only. Development v3.0.8;
source/native-test/build qualification is not physical camera acceptance.

## Operator flow

- Modern: Tools and System -> QR Decoder. Classic: home -> QR Decoder.
  Expected: Starting camera, then aspect-preserving preview with green framing
  border and Point camera at QR code. No camera startup occurs at firmware boot.
- Present a normal URL or text QR. Expected: preview disappears, capture stops,
  QR Code plus byte count and scrollable inert text. Nothing opens a URL, changes
  network configuration, or executes payload. Controls/unsupported bytes display
  as backslash-x plus two hex digits; JSON payload_hex preserves all bytes.
- With writable mounted SD: Saved filename, one file under /sdcard/lab/QR.
  Without usable SD: Not saved plus reason, but the result remains readable.
  Save independently creates lab and lab/QR; it never deletes a path collision.
- Scan Again explicitly restarts. Same payload gets a new record. Back returns
  to the menu used to enter; Home returns home. No physical button is involved.
- A missing/busy camera or insufficient RAM produces an error and Retry/Back.
  A stop that cannot prove DMA quiescence retains resources and blocks restart;
  reboot is required rather than freeing potentially live buffers.

## Limits and architecture

quirc is pinned under components/cym_qr/third_party/quirc with its ISC notices.
The BF3901 register program is pinned under components/cym_camera/vendor with
Apache-2.0 notices. No vendor video/UI/rearm-task implementation is imported.
Native IDF 6.0.2 PARLIO RX is used with a private fake-EOF function for frames
above 64 KiB. A linker admission guard excludes PARLIO TX while capture owns RX;
changing IDF requires re-auditing that coupling. GPIO0/1/11/12 are camera pins;
GPS RX28, shared I2C ownership, LCD/SD SPI2, SD20MHz, console and audio stay as-is.
Large image/decoder buffers use explicit PSRAM; RX additionally checks cache
alignment and DMA-ext capability. Driver DMA descriptors remain internal.

The UI consumes one latest preview, not a frame queue. The worker never calls
LVGL and closes capture before saving or result display. Screen stop removes its
timer, detaches image/text/cache references, cancels and waits boundedly; it never
force-deletes a worker. Slow shutdown retains the context for later safe reaping.

Real native QR fixtures include binary/NUL, URLs, plain/numeric/alphanumeric,
600-byte text, rotations, mirroring, noise and nearest-center multi-code selection.
A 1200-byte dense synthetic fixture is a known quirc limitation: no decode is
accepted as such, never reported as correct payload. These larger host fixtures
are not evidence that a 240x320 camera resolves dense symbols.
No linear barcodes, image saving, payload console logging or cloud decoding.

## Required physical acceptance (NOT executed; no USB hardware attached)

1. Open from Modern and Classic, portrait and landscape. Verify preview color,
   aspect, orientation/mirroring and actual successful decoded bytes. Test printed
   and phone samples; record distance, symbol size, illumination and latency.
2. Verify blank/no-code remains scanning. Exercise missing-camera/startup error,
   low-memory and busy PARLIO paths. Test Back/Home while starting/capturing,
   decoding/saving, reading a result and retrying. No stale UI callbacks/reset.
3. With SD absent/full/read-only, confirm Not saved and usable result. With new
   lab/QR, existing records and regular-file lab or QR collision, verify exact
   JSON bytes, honest UTC validity, no overwrite and no false Saved message.
4. At least 30 open/scan/exit cycles and 15-minute preview soak. Record internal,
   largest DMA-capable and PSRAM heap plus qr_scan stack high-water mark. Confirm
   no leak, watchdog, retained resource or shutdown/reopen regression.
5. Confirm touch/display, GPS RX28, SD20MHz, audio and ordinary Wi-Fi/BLE use
   before and after scanning. Primary USB-C remains the only diagnostic console.
6. Inspect all other board packages: no tile, route, QR/camera symbols or startup.

Manual SD archive: in the separate CYM-SD-Assets checkout run
`python3 tools/build_sd_pack.py /path/to/new/archive.zip`; extract and copy
contents of sdcard/ preserving existing files, or use tools/install_sd.py.
No card formatting, flashing, publication or Stable changes are part of this work.
