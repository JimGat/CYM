# v3.0.2: manual SD setup and Classic RGB

## Behavior

- Every board with no registered PSRAM skips automatic Validate & Provision.
- Startup with missing SD folders shows manual-download instructions and OK;
  OK continues boot without setting provisioning consent or changing files.
- Settings > SD Card > Validate & Provision shows the same manual setup modal;
  OK closes it and leaves the SD menu usable. Classic/Modern share this handler.
- Settings Format + Provision is blocked before format confirmation or I/O.
  Prepare FAT32 on a computer instead. Boot SD-recovery behavior is unchanged.
- Boards with usable PSRAM retain the existing provisioning path and checked
  task-stack allocation; transient exhaustion is not called absent PSRAM.
- Classic CYD-2432S028 and HackerBox Amberjack 0131 use common-anode, active-low
  RGB through the existing status/clear interface. PWM inversion makes zero
  brightness HIGH/off; RMT is never initialized on them.
- Waveshare profiles have no onboard RGB LED and remain no-op. Other boards'
  existing WS2812 behavior is unchanged. No GPS/console/SD/layout changes.

## Manual SD setup

Download https://github.com/JimGat/CYM-SD-Assets with Code > Download ZIP.
Extract it. Copy the contents of `sdcard/` onto the card root (`lab/` at root),
skipping existing files. For a fresh card, copy `.example` templates to the same
folder without that suffix. Do not replace private keys/configuration/captures.
Alternatively, from the extracted repository run:

```sh
python3 tools/install_sd.py "/path/to/mounted/SD-card"
```

Expected: JSON copied/preserved counts; repeating it copies zero new files when
nothing has changed. The installer never formats and never overwrites files.

## Owner hardware acceptance (not claimed by host tests or compilation)

1. Classic and HackerBox: matching-layout application-only flash at 0x10000,
   erase-all disabled; preserve settings. Full images use 0x0000 and can overwrite
   NVS/PHY/settings even with erase-all disabled.
2. With FAT32 card missing required folders, boot: no-PSRAM manual prompt fits;
   OK reaches Home without a provisioning task or boot loop.
3. In both Classic and Modern layouts, open SD Card > Validate & Provision:
   OK closes the warning, menus/Back/Home remain responsive; repeat 3 times.
4. Select Format: manual warning appears; existing files remain unchanged.
5. Install the manual pack; check expected folders/resources and normal SD use.
6. Check Classic/HackerBox LED status colors during idle/scanning and Go Dark:
   off must be fully off, wake restores indication. Check all three colors.
7. On a PSRAM-equipped board, verify provisioning still works. On Waveshare,
   verify no onboard RGB initialization; display/touch/GPS remain usable.

Primary programming/debug USB only; no logs on the GPS/JST UART.

## Owner acceptance and Stable promotion

Jim reported: "I have tested the PSRAM gate and the descrete RGB led and everything works well!"
This confirms those two fixes on his tested hardware; it is not a claim that every
board, peripheral, or individual checklist step above was physically tested.
Jim subsequently authorized promotion to main and refreshing the existing v3.0.0
release assets while preserving already-shared links. The tested v3.0.2 images
are reused without a new firmware build/version or a moved v3.0.0 tag.
