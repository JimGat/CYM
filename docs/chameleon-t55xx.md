# Chameleon Ultra physical T5577/T55xx cloning

CYM extends its existing Chameleon Ultra BLE reader path with physical T5577/T55xx cloning for EM410x and HID Prox credentials. This is separate from `Clone to Slot`, which writes the Chameleon's emulator memory.

## Supported flow

1. Connect a Chameleon Ultra over BLE. Chameleon Lite has no LF writer hardware.
2. Open `Read LF 125 kHz` and scan the source credential.
3. For an EM410x five-byte ID or HID Prox 13-byte record, tap `Clone T5577`.
4. Read the destructive-action warning, remove the source card, and place the blank or intended target T5577 against the Chameleon Ultra.
5. Tap `Write`.
6. CYM sends the current upstream protocol command (`3001` for EM410x or `3003` for HID Prox), waits 100 ms without blocking the UI, then rescans the target.
7. Success is displayed only when read-back exactly matches all five EM410x bytes or all 13 meaningful HID Prox bytes.

`Write complete` is not treated as verification. A matching read-back is required for `Verified - T5577 matches`.

## Recovery choices

- `Retry Verify` rescans without rewriting the target.
- `Retry Write` repeats the destructive write after the operator confirms the target is still positioned correctly.
- `Cancel` aborts the UI operation and drains any late BLE response before another command may start.

CYM reports transport/send failure, command timeout, disconnect, protocol rejection, unsupported Chameleon firmware, no tag during verification, and verification mismatch separately.

## Physical validation procedure

Hardware validation requires a Chameleon Ultra with firmware that supports commands 3001 and 3003, one known EM410x source, one known HID Prox source, and writable T5577 targets.

For each source type:

1. Read the source and record the ID shown by CYM.
2. Tap `Clone T5577`; confirm `Clone to Slot` remains a separate action.
3. Remove the source, position a blank target, and confirm the warning.
4. Verify that CYM does not report success merely when the write response arrives.
5. Keep the target positioned for read-back and require `Verified - T5577 matches`.
6. Read the target again in a fresh LF scan and compare the full source value.
7. Repeat with no target present; require `No tag found during verification` and retry choices.
8. Repeat with a different readable target after writing; require `Verification mismatch`.
9. Disconnect the Chameleon during a write or verify; require a disconnect result and no crash.
10. Cancel during a command, then start a new scan; confirm the late response cannot complete the new operation.

Until these steps are captured on real hardware, firmware builds and automated tests are software validation only.

## Phase 2 raw-block investigation (not implemented)

Pinned upstream ChameleonUltra source includes command `3016` (`DATA_CMD_LF_T55XX_WRITE`) for a single raw T55xx word. Its packed 11-byte request is: block number, 32-bit big-endian word, password-use flag, 32-bit big-endian password, and page selector. Page 0 permits blocks 0-7; page 1 permits blocks 0-3.

The firmware explicitly returns LF success even though T55xx supplies no write acknowledgement. Upstream does not provide a paired decoded raw-block read command in the reviewed client path; command 3007 is a generic LF sample capture rather than a verified T55xx block read. A safe generic editor would therefore need a separately designed decode/read-back path, password handling and lockout protections. CYM does not expose command 3016 in this release.
