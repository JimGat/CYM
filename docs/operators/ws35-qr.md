# WS-C5-35 QR Decoder — v3.0.27

Available in Stable v3.0.27 only on Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35) with its supported camera. Other boards do not acquire a camera or display this tool.

## Operate

1. Modern: Tools & System → QR Decoder. Classic: Home → QR Decoder.
2. Wait for preview; aim a simple QR code with its complete white quiet zone visible. The preview is aspect-preserving; software/build checks do not guarantee recognition distance, illumination tolerance or dense-code performance.
3. A valid result is inert escaped text. CYM does not open URLs, execute payloads or automatically configure networks. The camera stops before SD access; a successful save reports a JSON record under `/sdcard/lab/QR`.
4. Missing/unwritable SD reports **Not saved** while leaving the result readable. Use **Scan Again** for another capture. Back returns to the entry menu; Home returns to the selected layout.
5. Missing/busy camera, memory or shutdown errors use the displayed Retry/Back path. If stop cannot prove capture quiescence, restart is blocked rather than freeing potentially live resources.

Keep debug OFF for normal use. For bounded diagnostics use primary USB-C at 115200, `debug on`, then `debug off` afterward. **Save Debug Frame** is explicit and consent-gated: the camera image can contain private information. Review files before sharing; never publish sensitive QR payloads or camera dumps.

## Qualification limits and related checks

Earlier owner testing confirmed close-before-SD diagnostic capture and Scan Again; this is not broad QR-recognition acceptance. Check decoded bytes, all rotations/both menus, SD absent/full/error cases, repeated open/exit and a long preview soak. Verify GPS GPIO28, touch/display, unchanged SD speed, audio and ordinary radio use before/after. No camera pin reassignment, NVS erasure or SD formatting is required.

[Detailed diagnostics and historical evidence](../ws35-qr-debug.md) · [Board wiring/qualification](../hardware/waveshare-c5-touch-lcd-35.md)
