# WS28AudioDiag v0.1.0 — standalone diagnostic

Approved plan: host-test pure bounded PCM and abort/cleanup policy first (RED
then GREEN), implement synchronous single-owner adapter, build independent
ESP32-C5 project, merge real flash artifacts. No Doom, SD, WiFi, BLE, LVGL,
production edits, NVS APIs, gate bypass or flashing.

Separate CH32 OFF/ON/OFF input sampling from ES8311/I2S tone. EXIO3 is PA_CTRL.
Requested direction 0x0b (1=output), output 0x03 off / 0x0b on keep EXIO0/1
reset lines high and EXIO2 RTC input. These masks are NOT hardware readback.
Preload output off before direction to avoid deliberately lowering reset lines.
Output-mode input mismatch remains evidence, never electrical verification;
the standalone tone proceeds only after required operations succeed.
Conservative 440Hz, 22050Hz mono Philips 16bit, amplitude 2048, volume -18dB,
1.5 seconds, BCLK24/LRCLK25/DOUT26, slave DAC BCLK-derived clock, no MCLK.
One automatic run after 4s primary USB-C Serial/JTAG connection grace;
GPIO28 BOOT short press repeats. No UART console or secondary console.
All runs attempt amp off and codec/I2S cleanup. Cleanup faults print and
latch repeat lockout; no forced task deletion or live DMA free.
Audible=unconfirmed always; owner listening is the acceptance gate.

Existing .97 output-mode input remained 0x03 after requesting on 0x0b;
battery removal did not resolve it. No hardware-tested successful gameplay
baseline. Vendor input-mode reads do not prove output sensing; commented
EXIO4 mapping is not used. Reference:
https://docs.waveshare.com/ESP32-C5-Touch-LCD-2.8 ; vendor reference revision
77a7dceac38a1bd491173b3906205217a382c08c.

## Flash safety
DO NOT erase-flash. Reflash production afterwards. Layout unchanged:
NVS 0x9000/0x6000, phy 0xf000/0x1000, factory 0x10000/0x700000,
storage 0x710000/0xf0000. Board 32MB flash, 8MB PSRAM (not used).
Full image at 0x0000 has ff padding over NVS/phy. **Writing this full image
can erase covered sectors including NVS: ff padding does NOT preserve NVS.**
ESPConnect full-image workflow risks settings loss. Back up settings or
prefer sparse boot/table/app flashing using build/flash_args: boot 0x2000,
table 0x8000, app 0x10000. Only these three explicit files avoid covering NVS.
No partition data is initialized. This task builds only, never flashes.

## Build/test
On ESP32-Dev as dev: source /home/dev/esp/esp-idf/export.sh;
python3 tools/WS28AudioDiag/tests/test_host.py;
cd tools/WS28AudioDiag; bash build.sh.
Evidence/checkpoints: /home/dev/ws-c5-35-fixes/ws28-audio-diag/.

## Preferred operator procedure: preserve production settings
Use only on WS-C5-28 with the existing CYM v2.15.97 bootloader and partition
table. Flash WS28AudioDiag-app.bin at 0x10000, with erase-all disabled.
Do not use a flasher that forces address 0x0000 for the app-only image.

Example from a PC with esptool installed (replace PORT):
python -m esptool --chip esp32c5 --port PORT write-flash 0x10000 WS28AudioDiag-app.bin

Open the PRIMARY USB-C serial console, then reset. The LCD is intentionally
not initialized: a blank screen is expected. After four seconds expect BEGIN,
CH32 samples, codec I2C results, PCM write/summary, cleanup and END. Listen
for one quiet 440 Hz tone lasting 1.5 seconds. Short BOOT press repeats.
If repeat_locked appears, save the log and reset; do not force repeat.
Send the complete BEGIN-to-END log and say whether the tone was audible.

Interpretation:
- Tone heard despite input mismatch: output sensing is unsuitable as a
  production gate candidate, but this still does not qualify gameplay.
- No tone with I2C failure: investigate the reported operation before I2S.
- No tone with accepted writes: clocks, PA_CTRL voltage, speaker/codec path
  remain unconfirmed; accepted writes/PCM counts are not physical proof.

Restore by writing the v2.15.97 WS-C5-28 production APP image at 0x10000,
again without erase-all. This diagnostic never writes NVS or SD.
The full diagnostic image is supplied for completeness at 0x0000, but do
not use it for the settings-preserving test; it can erase NVS/phy sectors.
Artifact offsets, byte counts and hashes are in artifact-manifest.json.

Software qualification: two host tests (PCM/policy and project contract),
13 injected policy operation-fault positions; real ESP-IDF 6.0 build on
ESP32-Dev. Hardware adapter fault execution, electrical PA state, codec
clocks and audibility still require owner testing. Production is unchanged.
