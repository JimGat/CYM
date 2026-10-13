# CYM v2.15.97 — WS-C5-28 amplifier-readback test candidate

## Scope and evidence
Correction after the physical retest: Jim reports only a frozen title screen, not moving gameplay, on the previous images. Battery removal did not resolve it. There is no verified working WS-C5-28 gameplay baseline. His v2.15.96 capture reaches amplifier enable, then rejects output shadow 0x0b versus input 0x03 with `amp_pin_readback`; cleanup has zero frames. No older-image fallback appears in that capture.

The sole runtime change is WS-C5-28 amplifier readiness sampling: up to 11 input reads, separated by at most ten requested 10 ms RTOS delays. This is 100 ms of requested delay plus I2C and scheduler time, not a measured absolute 100 ms deadline. A matching first sample has no added delay. Direction/output changes preserve unrelated pins. Direction/write/read errors, shadow mismatch, and persistently wrong input still reject readiness. WS-C5-35 control is unchanged.

This tests the settling hypothesis; it does not establish that CH32V003 input sampling is delayed or that this repairs Jim's physical board. Do not represent software shadows or successful compilation as amplifier-pin or audible-output proof.

## Operator test
1. For a matching partition layout, prefer the commit-pinned application image at 0x10000 with erase-all disabled. The full image is flashed at 0x0000 but can overwrite/erase NVS and PHY regions; do not describe it as settings-preserving.
2. Capture the primary USB-C serial output through isolated launch.
3. Check `AUDIO_PA board=WS28` fields `pin_reads`, `settle_ms` (requested retry delay), `pin_read` and `verified`.
4. A settling recovery should show enable input bit 0x08 set and `verified=1`, then `AUDIO_STARTED`. Confirm gameplay and audible firing independently.
5. If it still fails with `pin_reads=11 settle_ms=100 pin_read=03`, the mismatch persists beyond this window. Send that log; do not bypass the gate or change SD assets.
6. Exit/reboot and repeat once; verify normal CYM remains usable.

## Unchanged contracts
Gameplay viewport/caption/buttons, audio gain, codec/I2S format, task stacks, partitions, bootloaders, saved settings, Chameleon integration, and Stable firmware remain unchanged. The small WS28 viewport is a separate pending change.

## Qualification
Host regression exercises delayed enable/disable, immediate success, bounded persistent mismatch, missing handle and I2C failures. All eight board builds/package versions and the full suite must pass before development publication. Physical acceptance remains pending Jim's test.
