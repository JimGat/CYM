# Chameleon Ultra/Lite RFID manager

CYM extends its existing `chameleon_ble.[ch]` transport; it does not introduce a second driver or replace the working BLE path.

## Screens and data paths

- **Saved Cards** scans the existing LF `.rfid` and HF `.nfc` directories. A normal tap selects an emulator slot and reuses the existing parsers/load chain. Long-press deletion requires confirmation and reports filesystem failure.
- **MF Keys** reports the built-in key count and whether `/sdcard/lab/rfid/keys/mf_keys.dic` loaded, and can reload that dictionary. It does not expose key values.
- **Detect** uses the verified Chameleon MIFARE detection commands (`4004`-`4007`), retrieves every available bounded 18-byte record batch, and exports paired captures for authorized offline `mfkey32v2` analysis. It does not crack keys on-device.
- **Settings** serializes animation (`1015`/`1016`) and sleep-timeout (`1039`/`1040`) requests because the BLE transport permits one pending command.

## Geometry and integrity rules

- Live MIFARE Classic dumping supports Mini, 1K, and 4K at 20, 64, and 256 blocks. The file importer/emulator loader also validates declared 2K images at 128 blocks. Large 4K sectors contain 16 blocks.
- Partial MIFARE captures are labeled `# Partial dump: yes` with per-block unread markers. They may be retained for analysis, but the emulator-slot loader rejects them rather than writing zero placeholders as card data.
- NTAG213, NTAG215, and NTAG216 are 45, 135, and 231 pages.
- Full dump buffers are allocated for the detected geometry and released on workflow exit. Saves are clamped to valid received pages/blocks.
- `.nfc` emulator loads reject malformed hex, duplicate records, sparse records, mixed block/page data, out-of-range indices, and geometry that does not match the declared tag type.
- MIFARE emulator writes use command `4000` with `[startBlock, data...]`; NTAG page writes use command `4022` with `[startPage, pageCount, data...]`.
- NTAG reads use command `2010` with the verified HF14A raw payload structure: options, big-endian timeout, big-endian bit length, then `0x30,page`.

## Distinct clone operations

`Clone to Slot` modifies Chameleon emulator memory. `Clone T5577` is a separate destructive physical-tag operation with confirmation and semantic read-back verification.

## Validation status

Automated protocol/source contracts and five-board compilation/package verification do not establish physical behavior. Physical validation remains required for Chameleon Ultra/Lite MIFARE and NTAG dump/load, Saved Cards SD behavior, nonce capture/cancel/export, settings read/write, and screen-exit lifecycle. The separate EM410X/HID Prox to T5577 workflow was hardware-validated in v2.15.42.
