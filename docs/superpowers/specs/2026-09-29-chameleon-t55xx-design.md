# Chameleon Ultra T5577/T55xx Clone Design

## Scope

Extend CYM's existing Chameleon Ultra integration with contextual EM410x and HID Prox clone-to-T5577 flows. Reuse the working NimBLE transport, Chameleon frame codec, LF scanner, decoded credential buffers, LVGL page, and screen-stop cleanup. Do not add a second driver, replace BLE, add raw T5577 operations, or redesign the Chameleon screen.

## Existing CYM architecture

The active implementation is shared by all four release boards through `ESP32C5/main/`.

- `ESP32C5/main/chameleon_ble.c` and `.h`
  - `cham_init`, `cham_start_scan`, `cham_connect`, and `cham_disconnect` own discovery and connection.
  - `s_build_frame` emits the existing 0x11/LRC Chameleon protocol frame.
  - `s_rx_feed` parses command, status, length, payload, and LRC.
  - `cham_send_cmd` / `cham_send_cmd_ex` enforce one in-flight command.
  - `cham_poll` drains NimBLE RX data and invokes command callbacks on the LVGL/main task.
  - The existing callback is boolean and discards the exact protocol status; timeout and disconnect are not distinguishable at the UI layer.
- `ESP32C5/main/main.c`
  - `show_chameleon_screen` and `s_cham_*` callbacks implement the existing Chameleon UI.
  - `show_cham_lf_read_screen` starts reader mode with command 1001.
  - `s_lf_protos` rotates through EM410X_SCAN 3000, HIDPROX_SCAN 3002, Viking, PAC, and ioProx.
  - `s_lf_on_scan_result` stores the existing decoded response in `s_lf_uid`, records `s_lf_found_proto_idx`, and routes completion through `s_lf_poll_timer`.
  - EM410x currently uses five ID bytes. HID Prox currently uses the upstream 16-byte scan response; the first 13 bytes are meaningful: format (1), facility code (4 BE), card number (5 BE), issue level (1), OEM (2 BE), followed by three padding bytes.
  - `s_lf_write_rfid_file` already saves EM4100 and HID 26-bit credentials as `.rfid` files.
  - `s_lf_clone_btn_cb` is the existing clone-to-emulator-slot flow using commands 5000/5002. It is separate from physical T5577 programming and remains unchanged.
  - `cham_lf_read_stop` cancels the pending command, tears down timers/overlays, nulls LVGL pointers, and intentionally leaves BLE connected.

Existing LF data flow:

`Read LF tile -> show_cham_lf_read_screen -> command 1001 reader mode -> s_lf_on_mode_set -> 3000/3002 via cham_send_cmd_ex -> chameleon_ble NimBLE transport/frame parser -> s_lf_on_scan_result -> s_lf_poll_timer -> existing credential display/save/clone-to-slot UI`

## Current upstream trace

Reference revision: ChameleonUltra `d5778cc010fb27c308b467df1376863203092daf` (`main`). Documentation revision: ChameleonUltraDocs `369a74f2b7f3e44711bc964d7ac435ee27941082` (`main`).

- `software/script/chameleon_cli_unit.py`
  - `LFEM410xWriteT55xx.on_exec` validates a five-byte ID and calls `em410x_write_to_t55xx`.
  - `LFHIDProxWriteT55xx.on_exec` packs HID as `>BIBIBH` and calls `hidprox_write_to_t55xx`.
  - `LFT55xxClone` checks device model and rejects Chameleon Lite because it has no LF writer.
- `software/script/chameleon_cmd.py`
  - `em410x_write_to_t55xx` sends command 3001 with `5-byte ID + 4-byte new_key + candidate old keys`.
  - `hidprox_write_to_t55xx` sends command 3003 with `13-byte >BIBIBH HID data + 4-byte new_key + candidate old keys`.
  - Current client constants are `new_key = 20 20 66 66` and candidate old keys `51 24 36 48`, `19 92 04 27`.
- `firmware/application/src/app_cmd.c`
  - `cmd_processor_em410x_write_to_t55xx` requires at least one four-byte candidate after the five-byte ID and four-byte new key.
  - `cmd_processor_hidprox_write_to_t55xx` requires the 13-byte HID structure, one four-byte target/new key, and at least one four-byte candidate key. Its local field names are confusing (`old_key`/`new_keys`), but the call order confirms the first key is the target/new password and the remainder are candidate old passwords.
- `firmware/application/src/rfid/reader/lf/lf_reader_main.c`
  - `try_reset_t55xx_passwd` tries each candidate old password, then the target password itself.
  - `write_t55xx` starts the LF field, performs password reset attempts, writes encoded blocks, stops the field, and always returns `STATUS_LF_TAG_OK` because T55xx supplies no write acknowledgement.
  - The source explicitly says results must be verified by the host.
- `firmware/application/src/rfid/nfctag/lf/protocols/em410x.c` and `hidprox.c` encode the protocol-specific T5577 config/data blocks.
- `firmware/application/src/rfid/reader/lf/lf_t55xx_data.c` emits the actual T5577 RF write sequence. Each data block is attempted once with the target password and once unprotected, followed by reset.

The stock client does not expose password options in these CLI commands. Although it supplies key fields required by the protocol and writes block 7 during reset attempts, the EM410x/HID config words do not enable password mode. CYM will match the current upstream payload exactly, will not expose or log keys, and will not claim that a protocol-level 0x0040 response proves a tag was programmed.

## Chosen implementation

1. Add a small host-testable payload/credential codec beside the existing Chameleon transport. It is not a driver and performs no BLE or RF I/O.
2. Preserve existing callback APIs, but expose the last command outcome/status so the UI can distinguish protocol errors, timeout, BLE write failure, disconnect, and cancellation without changing every existing callback.
3. Add a contextual `Clone T5577` action only after supported EM410x/HID reads and only for Chameleon Ultra. Unsupported firmware is handled when 3001/3003 returns invalid-command status; command 1035 capability discovery is deferred to avoid a broad handshake refactor.
4. Copy the source credential into dedicated expected storage before writing so read-back cannot overwrite the expected value.
5. Present a remove-source/place-target confirmation. WRITE sends 3001 or 3003 with the exact upstream payload. A successful command response means only that the RF sequence completed.
6. After a short nonblocking settle interval, use the existing scan command and parser for the same credential type. Retry reads within the existing bounded LF scan window. Only an exact semantic match produces `WRITE SUCCESS / VERIFIED`.
7. EM verification compares all five ID bytes. HID verification compares all 13 meaningful bytes (format, facility code, full 40-bit card number, issue level, and OEM); padding is ignored.
8. On mismatch, show expected and actual plus Retry Verify, Retry Write, and Cancel. No-tag verification, timeout, disconnect, unsupported command, invalid credential, busy state, and protocol error remain distinct.
9. Screen teardown/cancel nulls UI pointers and drains or invalidates outstanding responses so no stale response can be consumed by a later command.

## Saved credentials

CYM currently writes LF credentials to `.rfid` files, but the inspected LF screen has no existing saved-LF browser that reconstructs the full upstream HID structure reliably. Scan -> clone -> verify is Phase 1. Saved-LF-to-T5577 is documented as a separate enhancement rather than expanding the storage/UI scope.

## Testing

- Host unit tests validate exact 17-byte EM and 25-byte HID payloads, rejection of invalid lengths, and semantic read-back comparison.
- Source/integration contracts validate command IDs, use of the existing transport and scan commands, no key logging, Ultra-only UI gating, retry/cancel actions, and cleanup.
- Existing full Python tests must remain green.
- All four release boards must build/package at one patch version before push.
- Physical proof requires a connected Chameleon Ultra plus source credentials and writable T5577 tags. Compilation is not hardware proof; if no remotely operable fixture is available, the release report will clearly mark the eight physical tests pending and provide exact operator steps.

## Phase 2 research boundary

Report, but do not expose, upstream generic command 3016 and internal raw T55xx functions. Raw reads, dumps, block editing, modulation analysis, password cracking, and firmware protocol additions are outside this implementation.
