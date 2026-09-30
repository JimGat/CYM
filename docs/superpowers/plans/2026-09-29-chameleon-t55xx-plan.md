# Chameleon Ultra T5577/T55xx Clone Implementation Plan

> For Hermes: execute this plan inline on ESP32-Dev as `dev`, task by task, using strict RED-GREEN-REFACTOR. Do not create or modify a CYM checkout on JARVIS.

Goal: Extend the existing CYM Chameleon Ultra LF result workflow so EM410x and HID Prox credentials can be cloned to a physical T5577/T55xx tag and verified by read-back.

Architecture: Keep `chameleon_ble` as the sole BLE/frame transport. Add a small pure codec for exact upstream payload construction and semantic comparison, expose typed transport outcomes without replacing existing callbacks, and add one bounded LVGL clone/verify state machine to the existing LF reader screen.

Tech stack: ESP-IDF C, NimBLE, LVGL, Python unittest contracts, host GCC codec tests, existing `scripts/build.sh` multi-board packaging.

---

1. Baseline and architecture evidence
   - Confirm clean `Jimgat_Dev`, remote-head equality, no overlapping build/worker, and current version.
   - Preserve all unrelated/untracked work.
   - Add `docs/superpowers/specs/2026-09-29-chameleon-t55xx-design.md`.
   - Verify no placeholders/contradictions and that upstream commit IDs/functions are cited.

2. RED: protocol codec contracts
   - Create `tests/test_chameleon_t55xx_contract.py`.
   - Add tests that compile/run a small host C harness against the codec.
   - Assert command IDs 3001/3003, exact 17-byte EM payload, exact 25-byte HID payload, invalid-length rejection, five-byte EM comparison, 13-byte HID comparison, and no public/loggable key accessor.
   - Run the focused test and confirm failure because the codec does not exist.

3. GREEN: protocol codec
   - Create `ESP32C5/main/chameleon_t55xx.h` and `.c`.
   - Use private fixed constants matching upstream current client: target key `20 20 66 66`; candidates `51 24 36 48` and `19 92 04 27`.
   - Provide only payload builders, supported-credential validation, and semantic comparison.
   - Add the source to `ESP32C5/main/CMakeLists.txt`.
   - Run focused tests to green; run a negative mutation/revert check to prove the test catches incorrect payload bytes.

4. RED: typed transport outcome and stale-response cleanup
   - Extend focused contracts for protocol status retention, timeout, BLE write failure, disconnect callback from `cham_poll`, and cancel/drain behavior.
   - Confirm failure against existing boolean-only transport.

5. GREEN: transport outcome
   - Modify `ESP32C5/main/chameleon_ble.h/.c` without replacing existing callback APIs.
   - Record command, exact Chameleon status, and local outcome before callbacks.
   - On disconnect, defer callback failure to `cham_poll` rather than silently clearing it in the NimBLE event callback.
   - Make cancellation detach the UI callback while retaining/draining the outstanding command until response/timeout so a stale frame cannot satisfy a later same-ID command.
   - Run focused and existing tests.

6. RED: EM clone/verify UI/state contracts
   - Add source contracts for contextual EM action, confirmation text, command 3001, exact payload builder use, nonblocking settle, read-back command 3000, expected-buffer preservation, bounded retry, exact comparison, verified-only-on-match, retry verify/write/cancel, typed errors, logs without keys, and stop-hook cleanup.
   - Confirm focused failure.

7. GREEN: EM clone/verify
   - Modify only the existing LF section in `ESP32C5/main/main.c`.
   - Add dedicated expected/readback state and popup pointers.
   - Show `Clone T5577` only for five-byte EM410x on Chameleon Ultra.
   - WRITE logs the credential, sends 3001 with 5-second timeout, waits 100 ms nonblocking, then retries existing 3000 reads within the existing seven-second scan window.
   - Distinguish command failure, unsupported operation, timeout, disconnect, no tag during verify, and mismatch.
   - Only exact read-back displays `WRITE SUCCESS\nVERIFIED`.
   - Ensure cancel/back/teardown cannot leave a callback targeting deleted LVGL objects.
   - Run focused and full tests.

8. RED/GREEN: HID clone/verify
   - Add failing contracts for command 3003 and HID payload/verification.
   - Reuse the existing 13 meaningful bytes from the 16-byte scan result.
   - Send expected format byte to 3002 during verification; compare format, 32-bit facility code, 40-bit card number, issue level, and 16-bit OEM by comparing the canonical 13-byte representation.
   - Show `Clone T5577` for supported HID results on Ultra.
   - Run focused and full tests.

9. Error/recovery and regression review
   - Verify no-target never reports success, mismatch offers all three actions, unsupported firmware is explicit, disconnect returns cleanly, and cancel drains stale response.
   - Confirm existing clone-to-slot, save, scanning rotation, BLE connection, reconnect, device info, HF, cards, MF keys, slots, and detect source paths are unchanged except transport cleanup.
   - Run all automated tests.

10. Documentation and optional Phase 2 research
    - Add user/operator hardware procedure and implementation notes under `docs/hardware/`.
    - Document command 3016 and internal `lf_t55xx_write_block`/`t55xx_send_cmd` only as research; do not expose raw operations.
    - Document the upstream naming mismatch and no-ACK behavior.

11. Release gate
    - Read current versions and bump patch only (v2.15.41 -> v2.15.42) across the three CMake sources and four manifests.
    - Build/package `nm-cyd-c5`, `ws-c5-28`, `cyd-2432s028`, and `hosyond-s3-35` on ESP32-Dev.
    - Verify each packaged app reports v2.15.42; verify manifests, parts, merged image sizes, and SHA-256.
    - Stage only intended files, run diff checks, commit with `v2.15.42: feat(chameleon): add verified T5577 cloning`, no AI attribution, fetch/check ancestry, push only `Jimgat_Dev`, and read back remote artifacts/web flasher.

12. Physical gate
    - Inspect attached hardware on ESP32-Dev. If a remotely operable Chameleon Ultra/CYM/T5577 fixture exists, execute the eight requested tests and capture serial evidence.
    - If physical movement of tags is required and no human fixture operator is available, do not claim hardware completion. Publish the build as hardware-validation-pending and provide a copy-paste procedure with expected UI/serial results.
