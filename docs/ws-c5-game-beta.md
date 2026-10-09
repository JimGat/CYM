# WS-C5 hardware beta operator manual

Software test candidate: v2.15.71. All eight builds and 32 generated/package
artifacts verified. 366 regression tests and real-engine ASan gameplay,
mutation/reset, fault/reopen tests passed. Parent publication/readback remains
a separate gate; hardware boot/display/touch/stack/heap evidence is still pending.
The current source uses native IDF PSRAM BSS placement and flash-backed mutable
state/mobj tables. Do not substitute an older WS package with this version label.

Scope: existing CYM application, WS-C5-28 and WS-C5-35 only. This is a silent,
touch-only experimental game. Other six packages carry no game engine. There
is no ordinary menu tile, sound implementation, external controller support,
new SD mount, RF change, or commercial WAD. Hardware qualification is pending;
host gameplay and compile/link checks are not physical approval.

## Jim: prepare and launch

1. Use desktop Chrome/Edge and the normal beta board choices:
   https://jimgat.github.io/CYM/beta/?board=ws-c5-28
   https://jimgat.github.io/CYM/beta/?board=ws-c5-35
   After coordinator publication, select Development and check the handoff
   firmware version and exact board. Do not select a different screen size.
   Neither this recovery nor its tools flash anything automatically.
2. Get separately supplied SD contents from exactly:
   https://github.com/JimGat/CYM-SD-Assets/tree/feature/doom-sd-assets/sdcard
   Copy the contents of sdcard/ to the FAT32 SD root. Required file:
   doom/doom1.wad, opened by firmware as /sdcard/doom/doom1.wad.
   This is official Freedoom Phase 1 v0.13.0, SHA256
   7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d.
   Preserve accompanying license and credits. The SD-assets branch is not
   merged to assets main and is not part of the firmware repository.
3. Insert the card. Use CYM's existing Settings -> SD Card -> Remount SD Card
   only if the existing mount is not ready, then return to Settings. Do not
   format your card or run an unrelated provisioning operation for this test.
4. Stop other tools normally. The launcher fails closed if SD is unmounted,
   Bluetooth/802.15.4 mode or an active tool/task is present. It does not stop
   or restart radios itself. Return to an idle Settings screen.
5. Tap and RELEASE the existing LAB5 firmware-version footer eight times
   within six seconds. A held press is not eight taps. Navigation, touch loss
   or timeout resets the sequence. No corner gesture or added menu tile.
6. The license page appears before engine allocations. Scroll to read its
   attribution, GPL/no-warranty and matching-source notice. Cancel returns
   unchanged to Settings. Continue checks the idle gate again and validates
   the existing SD file before engine startup.
7. During the hash/init wait, Exit remains usable. Missing or invalid WAD
   shows a wrapped vertical-scroll message with the full SD-assets URL and
   FAT32 root-copy instructions above. Exit is outside that scroll area.
   Download on a computer, correct the SD file, exit and launch again.
8. Gameplay buttons, bottom three rows:
     Left / Move / Right: turn left, forward movement, turn right.
     Back / Fire / Use: backward movement, shoot, activate a door/switch.
     Menu / OK / Exit: engine menu, confirm, leave game.
   A single touch holds one action; simultaneous move/fire is not claimed.
   Lift or slide off a control to release it. Touch-loss watchdog releases
   stale holds. Exit requests cancellation immediately; CYM waits for safe
   cleanup and explicit worker deletion before deleting the canvas/mailbox.
   If SD cleanup is busy, it retains ownership and shows a stopping message
   rather than freeing live memory. Persistent SD failure needs investigation,
   not a fabricated successful exit.
9. Exit returns to the existing home layout without the usual radio restart.
   Re-enter through Settings and the same footer gesture. Repeat at least ten
   times, including Exit while validating and while fighting/moving.

## Serial evidence to capture tomorrow

Capture full boot/version/PSRAM output and CYM_DOOM messages:
  LICENSE_SHOWN engine_not_started
  LICENSE_CANCEL no_engine_allocations (Cancel path)
  CONTINUE / WORKER_BEGIN heap markers
  LAUNCH_REQUESTED path=/sdcard/doom/doom1.wad
  ENGINE_STARTED state_bytes=<actual linked span>
  EXIT_REQUESTED
  WORKER_CLEAN and ENGINE_JOIN_READY ... owned=0
  UI_RELEASED heap marker

Check responsive touch in every screen orientation already supported by the
board HAL; renderer uses the existing LVGL canvas, logical coordinates,
RGB565 palette conversion, display byte order and panel flush path. There is
no private display driver. Check red/green/blue, text orientation, no clipping,
all controls, long errors, SD/display concurrency and repeated heap recovery.
Photograph missing/invalid messages and both panels. Report resets, watchdogs,
low-memory refusal, stuck held actions, blocking Exit or steadily declining
free/largest PSRAM. A compile success does not qualify existing panel DMA
completion behavior; the game never lends its worker mailbox to display DMA.
Check boot/heap/stack headroom from real hardware; linked static headroom is
an upper bound before runtime allocations, not measured live free RAM.

## Reproduce software gates on ESP32-Dev

Use the canonical checkout, Jimgat_Dev, and no other firmware writer:
  cd /home/dev/projects/CYM-NM28C5-jarvis-ws35-docs
  python3 -m unittest discover -s tests -v
  python3 tests/run_doom_engine_host.py --wad .hermes/doom-prototype/fixtures/freedoom-0.13.0/freedoom1.wad --output .hermes/doom-prototype/host-recheck

The official fixture is external/private test data, not tracked. The runner
checks its exact hash, compiles all 80 actual engine C files with ASan, and
asserts level ticks, movement, ammo consumption, menu/confirm/use/turn/release,
three reopens, missing-file recovery, 24 allocation failures and cancel/reopen.
No WAD download, title-only substitute or synthetic gameplay is used.

Build all eight sequentially, with the current intended source version already
synchronized in the three CMake anchors and eight manifests:
  . /home/dev/esp/esp-idf/export.sh
  for board in nm-cyd-c5 ws-c5-28 cyd-2432s028 hosyond-s3-35 ws-c5-35 pancake-c5 hackerbox-cyd ws-s3-5b; do scripts/build.sh "$board" || break; done
  python3 scripts/verify-dev-packages.py --version <handoff-version> --output .hermes/doom-prototype/recheck-packages.json --commit <handoff-SHA>

The verifier checks generated board flags, actual ELF engine symbols on two
WS/exclusion on six others, separately captured image-loaded initialized state and IDF-zeroed PSRAM state ranges, linked static RAM, actual
application descriptor, flash header/size, partitions, exact generated exports,
merged-image parts, all part paths/hashes and all 32 Git blobs (not LFS pointers).
Firmware changes require another sequential patch version before building.

## Coordinator-only publication and beta deployment

The writer does not push or deploy. Independently verify the prepared commit,
all gates, licensing source and artifact hashes first. If branch HEAD changed
unexpectedly, stop; no force push, reset, main merge, tag or release.

After verification, from the authoritative checkout, substitute the exact
handoff commit (not a guessed future SHA):
  test "$(git branch --show-current)" = Jimgat_Dev
  test "$(git rev-parse HEAD)" = <handoff-SHA>
  git push origin HEAD:refs/heads/Jimgat_Dev
  git ls-remote origin refs/heads/Jimgat_Dev
  gh workflow run deploy-flasher.yml --repo JimGat/CYM --ref Jimgat_Dev -f expected_sha=<handoff-SHA>
  gh run list --repo JimGat/CYM --workflow deploy-flasher.yml --branch Jimgat_Dev --limit 5
  gh run view <run-id> --repo JimGat/CYM --json headSha,conclusion,url

Require run headSha == handoff SHA and conclusion == success. The workflow
rejects a dispatch outside Jimgat_Dev or with a different expected SHA. Stable
root is copied exclusively from main; only /beta/index.html is replaced and
its normal Development board choices are pinned to immutable GITHUB_SHA.
The six default stable packages are not sourced from development. No main or
stable branch change is needed. The beta preview gate compares every root
stable file byte-for-byte and checks the development pin without deploying.

After deployment, read back /beta/index.html and verify its dev reference equals
the handoff SHA; fetch both WS manifests and every immutable artifact URL and
compare all handoff hashes. URLs after push (not yet available before push):
  https://raw.githubusercontent.com/JimGat/CYM/<handoff-SHA>/ESP32C5/docs/manifest.ws-c5-28.json
  https://raw.githubusercontent.com/JimGat/CYM/<handoff-SHA>/ESP32C5/docs/manifest.ws-c5-35.json
Manifest part paths resolve relative to each immutable manifest URL. All eight
manifest/artifact URLs are enumerated in finish-handoff.json. Matching source:
  https://github.com/JimGat/CYM/archive/<handoff-SHA>.tar.gz
Source/license/provenance: ESP32C5/components/cym_doom/NOTICE.md,
LICENSE.engine, PROVENANCE.json and patches/native-cym.patch. Firmware embeds
no WAD; the separate SD branch keeps Freedoom's own license and credits.

## Linked memory evidence (not live free RAM)

- WS-C5-28 initialized engine state: 19,892 bytes in loaded internal data; zero engine state: 93,936 bytes in IDF-zeroed PSRAM. Linked static upper-bound internal headroom: 35,888 bytes.
- WS-C5-35 uses the same reset spans; linked static upper-bound internal headroom: 40,608 bytes.
- Worker requests a 24,576-byte stack through FreeRTOS; runtime allocations reduce these static upper bounds. Initialization fails closed if worker/buffers cannot be allocated. Confirm actual startup and stack/heap headroom on hardware; no minimum runtime free-memory guarantee is claimed.
- The two large mutable tables are copied from immutable flash defaults into owned PSRAM for each launch. Tests mutate them before teardown and assert restored defaults on reentry; initialized values are not lost in NOLOAD storage.
