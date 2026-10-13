# CYM v2.15.98 — optional audio and receive-only GPS test candidate

## What the supplied hardware log establishes
WS28AudioDiag v0.1.2 completed with rc=0, ctrl_faults=0 and cleanup_locked=0. It submitted 66,150 PCM bytes in 130 writes and completed codec/I2S cleanup. During all pre-codec ON samples and the full 15-second ON window, CH32 input remained 0xf7: sensed EXIO3 stayed low despite requested output 0x0b. OFF readback matched. No measured PA_CTRL voltage, wire-level clocks, speaker or audible output was supplied. The mismatch predates codec initialization; more settling delay is not justified by this capture. Acknowledged writes and submitted PCM are not electrical or audible verification.

## WS-C5-28 behavior
Supported ES8311/I2S audio is attempted first, retaining the physical amplifier-readback gate, fixed-rate SFX mixer, existing gain, and existing settling limit. `doom_audio_healthy()` never reports silent operation as working audio. Failed initialization can continue without sound only when PA OFF succeeds and codec, I2S/DMA, task and queue ownership are fully released. A separate WS28-only safe-silent capability admits that path. Runtime output/queue failures use the same cleanup requirement. Failure to stop/delete/read back safely still aborts through the existing error/reboot path; it does not bypass ownership or delete a live task.

Expected initial mismatch path: `AUDIO_NOT_READY ... reason=amp_pin_readback`, then `AUDIO_INIT_FAILED ... cleanup_rc=0 silent_safe=1`, then `AUDIO_SILENT_FALLBACK board=WS28 ... cleanup=verified`, followed by moving gameplay. Seeing a title image alone is not acceptance. A speaker is not required to test silent gameplay.

## WS-C5-35 GPS and the U0TX/U0RX labels
The pinned vendor schematic 04e6134cf3e37309b2bec9915189efeace1161bc labels GPIO11 as U0TXD and GPIO12 as U0RXD. Firmware retains UART1 RX routed through the C5 GPIO matrix to GPIO12; net names do not force UART0. UART1 is a supported peripheral choice, not proof of physical board routing. R56/R59 camera/UART routing and the fitted resistor population still require board-specific verification; do not infer population from a photograph or change resistors speculatively.

WS35 now installs RX-only UART at the saved baud (9600 default), explicitly resets GPIO11 to input, leaves TX detached, and does not send PCAS/PMTK/UBX configuration or autodetect traffic. The GPS monitor is the sole receiver; wardrive observes its GPS snapshots without consuming its bytes. NMEA fragments survive UART read boundaries; overflow is rejected and a fresh `$` resynchronizes the bounded framer. Other boards keep their existing receive/configuration behavior. Selecting a baud on WS35 changes only the local receiver, not the GPS module or its update rate.

Primary USB-C Serial/JTAG remains the console. This cycle does not change console configuration and sends no application/debug logs or GPS configuration traffic through the UART expansion/second USB. 115200 for the USB monitor is independent of the GPS's confirmed 9600 baud.

## Operator test — GPS
1. Use the existing known 3.3V-compatible GPS output and common ground. Module TX feeds board RX/U0RX (GPIO12 net); module RX is not needed for this receive-only candidate. Never attach RS-232 voltage levels or guess header pads.
2. In Wardrive Options select the module's confirmed 9600 baud. Reboot once, capture primary USB-C, and confirm `GPS_RX_OWNER board=WS35 uart=1 rx=12 tx_detached=11 baud=9600 ... config_writes=0`.
3. Enable Hardware -> Debug diagnostics and GPS Info -> Serial GPS log. Both are required for the extra bounded `GPS_RAW_RX` line. Capture three five-second windows; disable the diagnostics afterward if no longer needed.
4. `bytes5s>0` with NMEA text establishes reception; GGA/RMC and fix must be checked separately. Raw bytes with no valid sentences point to baud/framing/data quality. Continued `bytes5s=0 total=0` remains a no-reception condition, not just a no-satellite-fix condition; retain the routing/voltage investigation rather than claiming a software fix.
5. Opening Wardrive must not stop the monitor's receive counts. GPS reception does not independently qualify wardrive packet capture.

## Operator test — gameplay
1. With the existing licensed/shareware/free assets unchanged, launch through the existing selector. Keep the established 270-degree game orientation; do not reformat SD or replace assets for this test.
2. Capture the audio decision above; start a level, move, turn and fire. Confirm advancing display updates (`NATIVE_PRESENT completed_total` with debug enabled), responsive touch, and BOOT/fire behavior where already supported. Silent gameplay is acceptable only after `cleanup=verified`.
3. Exit through the existing cold-reboot route. Confirm normal CYM orientation/settings and display/touch/SD remain usable, then repeat once. Report freezes or cleanup failures rather than treating a static title as success.

## Flashing and settings
Full merged images flash at 0x0000. They include 0xff padding over NVS/PHY and can overwrite/erase saved settings even when an erase-all checkbox is off. For an already matching production layout, prefer the board's application-only image at 0x10000 with erase-all disabled. Never erase NVS or format SD as part of this test. Partition tables and bootloaders must match the previous production cycle byte-for-byte.

## Qualification boundary
Shared intended version is v2.15.98 across all eight affected packaged release boards. All eight builds, all eight packaged app/manifest versions and all 32 binary compositions/hashes must pass before publication to Jimgat_Dev. Main, tags and releases are not changed.

Tests compile the actual production audio backend with fault injection, including unsafe PA-OFF/task/I2S/codec-delete cleanup; the actual sound adapter with initial/runtime safe/unsafe admission; and the actual bounded GPS framer with ASan/UBSan. The real engine's opt-in silent host run uses an explicitly mocked safe audio failure, executes moving/firing/menu gameplay over three 301-frame reopen cycles, and checks cleanup and allocation/cancel recovery. This proves host software behavior, not C5 hardware responsiveness, PA voltage or audible sound. Final counts/hashes and immutable downloads are supplied in the completion report.

No broad refactor: saved settings, partitions/bootloaders, task stacks, selector/game orientation, existing controls, normal UI layouts, display/touch/SD, Chameleon human authorship and @birolt29 co-developer credit are retained. Classic and HackerBox keep their existing 90 default brightness with saved-NVS precedence; console configuration stays unchanged. WS28 viewport/caption performance and wardrive capture remain physically unqualified.
