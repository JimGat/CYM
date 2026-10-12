# v2.15.92: bounded WS35 amplifier and normal-UI corrections

## Scope and status
Development/Beta firmware candidate. Physical sound, completed normal refresh under one second, and all-board functional acceptance are not established by host tests or builds. Stable/main are outside this cycle.

## WS35 expander correction
Pinned Waveshare ESP32-C5-Touch-LCD-3.5 commit 04e6134cf3e37309b2bec9915189efeace1161bc, `example/ESP-IDF-V554/07_exio/components/io_extension/io_extension.c`, specifies direction bit 1=output, 0=input, and two-byte little-endian mode/output/input registers. Its Arduino 01_exio implementation agrees. The prior direction mask 0xffdc configured EXIO0/1/5 as inputs. The adapter now uses 0x0023: touch reset, LCD reset and EXIO5 PA_CTRL outputs; EXIO6 stays input. INPUT04 is read as a two-byte little-endian pin-state register.

The amplifier ON/OFF pin readback gate remains mandatory. I2C errors, read errors, wrong direction and mismatches fail closed. Amp writes preserve other output bits. This corrects the source-level explanation of the .91 ON-readback refusal; actual output voltage, launch success and sound need hardware proof. WS28 EXIO3 component routing is unchanged. ES8311/I2S GPIOs, 22050 Hz mono and -30 dB volume are unchanged; no automatic tone or blind gain increase.

## Navigation correction
Home no longer writes unsupported ASCII `restart` to the GPS-owned UART or reports a successful write without checking it. Navigation intent, USB console, screen stop hooks and existing radio cleanup are preserved. Radio reset optimization is not included without proof that required cleanup can be omitted safely.

## Normal UI diagnostics, not a speed claim
Existing five-second reporting now includes layout/refresh elapsed spans, Screen popup call timing, requested/saved/joined invalidation pixel areas, render-band area and cover/draw visits. Hot-path hooks only update bounded RAM counters: no allocation, I2C or logging at the boundary. Work counts/pixels are not time or CPU utilization. Nested elapsed spans overlap and include task preemption; never add them as independent CPU costs. Counter totals are unsigned 32-bit and may wrap; prefer interval windows.

No renderer refactor, SPI-clock adjustment, staging/buffer resizing or DMA/completion bypass. Native gameplay source/transport, independent touch/BOOT input and orderly same-image restart Exit remain unchanged. The generic ST7796 error-return correction is deferred until partial-enqueue buffer ownership can be safely tested.

## Verification
Parent independently ran 455 tests in 71.688 seconds, all passed. Eight board builds passed; unchanged 4647 frozen compilation/configuration/test inputs tie these artifacts to the reviewed source. The independent package verifier checked all eight manifests/app descriptors, generated board/flash configuration, merged images, build/package equality and memory bounds: 32 artifacts. All 16 bootloader/partition artifacts remain byte-identical to .91. Original ignored/untracked work and prior test evidence were preserved.

Host tests exercise production amp code with protocol/error/mismatch fixtures, Home callbacks under eight board macros, diagnostics/reset/reporting, and real pinned LVGL Screen popup open/reopen/idle/cancel across Classic/Modern and normal orientations. Peripheral/NVS save callbacks are mocked; host clocks and GPIO mocks do not prove physical timing or sound.

## Operator acceptance
1. Select the board at the Beta flasher and choose Development. Verify boot reports v2.15.92. Use primary USB-C for programming/debugging; normal boot with BOOT button released, monitor at 115200 baud. Full images flash at 0x0000. Do not erase settings merely for this test.
2. In Classic and Modern, repeat Settings -> Screen, close/reopen, then save normal orientations 0/90/180/270. Capture DISPLAY_DIAG, UI_DIAG and UI_WORK alongside navigation and completed-paint timing. Acceptance means final completed refresh below one second, not an individual stripe/callback below one second.
3. On WS35 startup into isolated gameplay, expect AUDIO_PA requested=0 and requested=1 with mode_shadow=0023, write_rc=0, read_rc=0, verified=1; INPUT04 should reflect EXIO5. Codec configuration must remain verified. AUDIO_STARTED audible=unconfirmed does not certify sound: listen to actual SFX; measure PA_CTRL if readiness or silence persists. Capture the complete startup-to-fault/Exit sequence, not only the generic fault screen.
4. WS28 independently requires EXIO3 readiness and actual sound. Verify the previously accepted WS35 native gameplay quality, touch plus BOOT Fire, fixed selector/game orientation 270, and orderly Exit cold restart with normal saved orientation restored.
5. Exercise applicable GPS, SD, radio and controls/services on other boards. Green compilation is a cross-build regression gate, not universal physical compatibility.

Further responsiveness changes require the new diagnostic evidence; no speculative tuning is claimed in this release.
