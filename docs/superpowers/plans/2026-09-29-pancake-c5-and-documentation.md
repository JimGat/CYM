# Pancake-C5 Beta and Documentation Implementation Plan

**Goal:** Add a beta Pancake-C5 board target and complete HID/T5577 and Universal Clock documentation in README and Wiki.

**Architecture:** Reuse the canonical ESP32-C5 application with a dedicated board HAL profile and narrow Pancake display/touch adapter derived from the pinned C5Lab hardware implementation. Add beta-only packaging/flasher integration and no parallel feature implementations.

## Tasks

1. Add RED contracts for exact Pancake pins, Kconfig/HAL dispatch, adapter selection, 40-MHz landscape display, FT6336 transform, time capabilities, packaging, beta flasher visibility, workflow staging, version, documentation, and credits.
2. Add the Pancake board profile, SDK defaults, FT6336 driver/adapter, and board-specific initialization hooks to shared `main.c`.
3. Add `pancake-c5` build, package, manifest, Pages workflow, and beta flasher entry; bump the shared patch version to `v2.15.43`.
4. Update README and repository operator docs for verified physical HID/EM T5577 cloning and full Clock operation/accuracy/use cases.
5. Update Wiki NFC/RFID, create Universal Clock and Pancake pages, and update Home/Use Cases/Contributors links and credits.
6. Run focused tests and the full suite.
7. Build/package all five boards; inspect every package version and image.
8. Commit/push CYM and Wiki, verify remote SHAs, immutable files, beta flasher, hashes, and flash offset `0x0000`.
9. Deliver the detailed status and remote-test procedure in CLI and Telegram.

## Acceptance boundary

Pancake remains beta and unvalidated on hardware. A green build proves integration only. Do not promote it or claim touch/display/storage/GPS success until D3h420 or another operator reports physical results.
