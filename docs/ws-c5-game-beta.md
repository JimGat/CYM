# WS-C5 selector and same-image reboot-isolated beta operator manual

Development v2.15.78, built on ESP32-Dev as dev, branch Jimgat_Dev.
Use the exact development commit pinned by the Beta flasher for matching source.
This beta is provided for physical qualification, not hardware sign-off.
Current-cycle evidence: /home/dev/ws-c5-35-fixes/selector-reboot-handoff.md.
This is not a hardware qualification or publication claim.

## Delivered scope and explicit non-features

WS-C5-28 and WS-C5-35 only; engine excluded from the other six profiles.
Five-Hardware-tap PinZero LABS selector: after-hours workshop backdrop, Professor
Zero/ZeroBot reference, cyan/magenta/amber panels, original industrial portal and
128x64 pixel handheld silhouettes, large Back/Cancel. Arduboy is disabled COMING
SOON: no AVR emulator or launch exists. Selector/license work without SD.
Artwork is immutable flash indexed16 data, no continuous animation. Original
Jim-owned lab-1440.webp is untouched/pinned with derivative hashes in assets/PROVENANCE.json.

Both WS default270 only without valid saved orientation (0..3). Saved CYM choice
wins. Selector temporarily uses270; Back restores prior live transform, then main
rebuilds Settings. No saved orientation change. Game uses270 on a fresh boot.
Native logical sizes: WS28 320x240; WS35 480x320. DEV preview paths:
  /home/dev/ws-c5-35-fixes/selector-preview-ws28.png
  /home/dev/ws-c5-35-fixes/selector-preview-ws35.png
These are actual production-code headless LVGL captures with host peripheral/
engine stubs, NOT hardware photographs. Recursive bounds/font widths and image
pixel/color inspection are executable; physical appearance remains parent review.

Live subsystem handover is superseded. No universal stop/join, radio shutdown,
forced deletion, live flag wiping or subsystem restoration in launch. Radios
reset with the system. Same firmware/factory app and existing NVS: no partition,
bootloader, offset, OTA slot/boot-selection change. All eight packaged partition
SHA256 values must equal published HEAD before parent acceptance.

SFX preserve WAD DMX data, eight mixer channels, 22050 Hz mono 16-bit Philips I2S
through ES8311, -30 dB initial volume plus mixer headroom. No music (-nomusic),
MUS/OPL synth, microphone or beep substitute. Engine owns samples; DMA copies PCM.
Audio stops before memory reclaim; stop faults retain ownership. PCM host proof
is not audible speaker proof.

## Copy-paste operator sequence AFTER parent publication

1. Desktop Chrome/Edge, correct board beta URL:
     https://jimgat.github.io/CYM/beta/?board=ws-c5-28
     https://jimgat.github.io/CYM/beta/?board=ws-c5-35
   Expected: correct board/version and parent-approved Development pin. Select Development and confirm the displayed v2.15.78 version before flashing.
2. Separate SD contents:
     https://github.com/JimGat/CYM-SD-Assets/tree/feature/doom-sd-assets/sdcard
   Copy contents of sdcard/ to FAT32 root, retaining licenses/credits.
   Required disk path doom/doom1.wad; runtime /sdcard/doom/doom1.wad.
   Supported ONLY official Freedoom Phase 1 v0.13.0, SHA256:
     7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d
   No commercial WAD/mods, automatic download or auto-format.
3. CYM -> Settings -> Hardware Options: five completed taps/releases within
   existing six-second window, gaps below800 ms. Expected: landscape270 selector;
   no license or engine yet. One Hardware tap still navigates after800 ms.
   Settings Easter egg is unchanged. Classic/Modern share this Settings callback.
4. ARDUBOY: no launch, COMING SOON. DOOM: scrollable GPL attribution, no warranty,
   data-license/source notice. Cancel returns to selector without intent/engine.
   BACK / CANCEL rebuilds Settings in prior live orientation, including portrait touch.
5. Continue: mounted SD and a regular nonempty doom1.wad checked before commit.
   Expected success: MODE_INTENT_COMMITTED, then same-image system restart.
   Busy: REBOOT_REFUSED owner=<named owner>, readable refusal. Finish/exit that
   transfer in CYM and retry; launcher does not stop it. Missing SD/WAD or NVS
   open/set/commit failure never authorizes restart.
6. Next boot: MODE_CONSUMED selected=1, ISOLATED_BOOT normal_services=0 rotation270,
   then structural/hash validation, engine/audio. No normal radios/tools/GPS/
   capture/provision/screenshot workers. Missing/untrusted WAD or engine init error:
   readable scrolling instructions, Return CYM outside scroll; ordinary CYM restart.
7. Gameplay controls (single touch, not simultaneous move/fire):
     Left / Move / Right: turn left, forward, turn right.
     Back / Fire / Use: backward, shoot, activate doors/switches.
     Menu / OK / Exit: menu, confirm, safe cleanup then ordinary CYM restart.
   Lift/slide off releases; lost-touch timeout releases stale holds.
8. Exit during hash/init/play waits actual audio/engine cleanup, release-done AND
   suspended-state join before worker/UI/mailbox deletion. Expected EXIT_REQUESTED,
   AUDIO_STOPPED if started, ENGINE_JOIN_READY owned=0, UI_RELEASED, GAME_EXIT,
   then normal CYM using saved preferences. Fault retains ownership, not fake release.

## Recovery independent of SD/game

Intent is read and consumed+committed just after minimal safe NVS init, BEFORE
normal services/game initialization. Bounded12-byte magic/version+mode/integrity
record; Doom enabled, Arduboy enum reserved/disabled. Only supported WS software
reset ESP_RST_SW with BOOT not held launches. Missing/corrupt/unknown/disabled/
consume-failed records fall back to normal CYM. Stale power-on intent is consumed,
never launched; watchdog/panic also falls back. No NVS erase/repair for intent. If NVS initialization itself fails, normal CYM
uses defaults with WiFi refused instead of erasing saved configuration.

BOOT held at early app entry bypasses independently of SD/display/engine. During
isolated loop BOOT requests safe Exit. Reset/power-cycle recovers a hard hang: intent
already consumed. If BOOT+reset enters ROM download mode, release BOOT and reset
normally; physical strap/button behavior is a bench check, not host evidence.
Essential display/DMA/mutex failure before usable rendering logs ESSENTIAL_INIT_FAILED;
reset returns CYM. No readable-screen claim if the display/allocator itself cannot init.

## Exact initialization allowlist and storage policy

app_main consumes intent before obs_store/detectors, OT hooks/survey flush timer,
GPS UART/task, LED, wifi_cli_init, saved-config/UI splash, scanner arrays, normal
RTC/timekeeper, screenshot worker, gw/cham/honeypair/blueduck/wp, portal HTML,
normal SD cache/provision/whitelist and battery tasks. Isolated entry returns instead
of falling through ordinary startup/main loop.

Allowed: LVGL allocator/core, existing WS board I2C/expander/PMIC essentials via
display/touch adapters, display/touch/backlight, LVGL+SD mutexes, display DMA/flush
semaphore, input driver, LVGL tick, synchronous no-format SD transport mount, logging/
main watchdog, isolated validation/UI/engine/SFX worker. WS35 audio shares
ws_c5_35_i2c_bus(); WS28 already-live I2C/expander. No normal splash/idle/tool/UI
timers are registered. Display/touch callbacks contain no radio/worker starts.
Source ordering/suppression tests cover this boundary, not device task enumeration.

Before intent commit: named persistent service/write producers are refused: file
server, captures/survey, uploads, provision/pending completion, active screenshot/
queue and scanner-log owners. Parked screenshot handle alone is not busy.
WS-only bounded32-slot admission wraps real /sdcard fopen/fclose/open/close and
mkdir/unlink/remove/rename/rmdir, retaining ownership through real close/mutator
return. Atomic freeze rejects new opens/mutators and immediately refuses existing
handles/operations; no giant cleanup or indefinite wait. Close errors retain admission,
refuse launch and require reset/recovery. Raw provision format separately refused.
Remount reserves admission in main before task creation until transport/result
submission finishes. File-server service refused even between requests. Shared SD
transport must also be idle and stays held until restart. Deferred UI/survey/write
starts are main-owned; no callbacks pumped during synchronous transaction. app_main
starts no console. Future external/raw storage API must enroll before use.

## Vendor routing evidence

WS28: https://github.com/waveshareteam/ESP32-C5-Touch-LCD-2.8
Commit 4d7a40b75cfe609f87b619296db2d96536fe800e at:
  /home/dev/projects/ESP32-C5-Touch-LCD-2.8-upstream
04_sd_music BSP header lines 52..61: I2C0/1, BCLK24/LRCLK25/DOUT26/DIN27,
MCLK NC. BSP c lines 300..318 enables CH32V003 IO_POWER_AMP_IO (PIN3) high;
lines 381..426 configure ES8311 slave DAC, use_mclk=false. Reuse existing
CYM s_i2c_bus and s_io_expander; no second bus.

WS35: https://github.com/waveshareteam/ESP32-C5-Touch-LCD-3.5
Commit 04e6134cf3e37309b2bec9915189efeace1161bc at:
  /home/dev/projects/ESP32-C5-Touch-LCD-3.5-upstream
02_lvgl_demo BSP header lines 79..92: I2C26/27, BCLK23/LRCLK10/DOUT25/DIN24,
MCLK and PA GPIO NC. BSP c lines 251..358: I2S0 master Philips 16-bit mono
22050 Hz, ES8311 slave use_mclk=false, esp_codec_dev 1.5.11. CYM reuses
ws_c5_35_i2c_bus(); TX only, microphone absent. No inferred audio capability
flag is added to other boards.

## Reproduce gates on canonical DEV only

Through ssh dev@ESP32-Dev, as dev in the authorized worktree:
  python3 -m unittest discover -s tests -v
  python3 tests/run_selector_host.py
  python3 tests/run_doom_engine_host.py --wad .hermes/doom-prototype/fixtures/freedoom-0.13.0/freedoom1.wad --output .hermes/doom-prototype/selector-reboot-engine
  . /home/dev/esp/esp-idf/export.sh
  make -j1 all-boards
  python3 scripts/verify-dev-packages.py --version v2.15.78 --output /home/dev/ws-c5-35-fixes/selector-reboot-packages.json

Real engine/WAD host gate: gameplay/ammo/menu/use/turn/confirm/release, three reopens,
missing-file recovery,24 allocation faults/cancellation, nonzeroSFX PCM, owned=0.
Portable production intent/storage/main C tests use ASan/UBSan; storage has threaded
admission races. Real LVGL production UI checks glyph widths/bounds/art decode,
five-click timer, license/readiness/refusal/Cancel, repeat selectors, init errors/join.
No synthesized API/hardware success. Verifier without --commit checks working
packages, not committed blobs. Preserve unrelated .hermes/state_idf.ld/caches.

BOTH-board physical checks after parent approval: four saved orientations/default270,
Cancel/corner touch/RGB/clipping, real speaker SFX/volume/no music, busy transfer/
file-server/provision refusal, BOOT, Exit during hash/init/play and repeated cycles.
Save serial/photos. Build/host success is not physical evidence.

## Parent-only review/publication

Parent reviews exact scoped files, eight builds/32 packages, partition SHA equality
vs HEAD, pinned engine/art provenance and test evidence. Do not stage unrelated
.hermes/, state_idf.ld, caches or docs/feedback/docs/prompts. No AI trailers/game
name in commit messages; preserve human birolt29 credit. Stable artwork/flasher/
manifests remain main-sourced, unchanged by this cycle. After parent commit, pin
beta to exact SHA and verify workflow headSha/immutable outputs/hashes. Matching
GPL source must accompany binaries:
  https://github.com/JimGat/CYM/archive/<parent-commit>.tar.gz
  https://raw.githubusercontent.com/JimGat/CYM/<parent-commit>/ESP32C5/docs/manifest.ws-c5-28.json
  https://raw.githubusercontent.com/JimGat/CYM/<parent-commit>/ESP32C5/docs/manifest.ws-c5-35.json
License: component NOTICE.md, LICENSE.engine, PROVENANCE.json, native-cym.patch;
art provenance separately in assets/PROVENANCE.json.
