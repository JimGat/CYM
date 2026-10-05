# Waveshare ESP32-S3-Touch-LCD-5B beta

Hardware qualification is pending. This is the canonical CYM application, not a display demo. Select ONLY the 5B 1024x600 model, not the 800x480 5-inch variant or a Hosyond board.

## Install and operate
Use https://jimgat.github.io/CYM/beta/?board=ws-s3-5b in desktop Chrome/Edge. Verify Waveshare S3 Touch LCD 5B, Development channel, ESP32-S3 and the reported firmware version. Stable selection is not permitted for this beta profile. Native USB Serial/JTAG logs use GPIO19/20. Do not press/hold BOOT while the app is displaying: GPIO0 is RGB DATA6, not an application wake input. Go Dark wakes by holding the capacitive screen for five seconds.

The full image is CYM-WS-S3-5B-full.bin at offset 0x0000. The three-part manifest uses the unique ws-s3-5b bootloader (0x0000), partition table (0x8000) and app (0x10000). The four artifacts live in ESP32S3/binaries-ws-s3-5b/. All offsets must match this S3 build, not ESP32-C5 offsets.

## Display and touch foundation
The physical panel is 1024x600; LVGL lays out the canonical application on a 512x300 logical landscape viewport. Integer scale 2 expands each completed rendered pixel uniformly, including fonts, popups, lists, buttons and images. Montserrat 12/16/28 are 24/32/56 physical pixels; common 30/36-pixel controls are 60/72 physical pixels. Inverse touch divides both axes by the same scale with strict bounds (1023,599 maps to 511,299). Both Classic and Modern reuse their current responsive landscape layout. Small panels retain their original path. cym_viewport.h is reusable for later high-resolution transports, including a future P4, but there is NO P4 hardware support here.

Limitations: pixel replication preserves the existing raster fonts; it is not native high-DPI antialiasing. Legacy fixed-width cards/background art may remain narrower/centered within the wider viewport. Long dashboards/lists retain scrolling rather than shrinking text. No physical corner/color/long-run validation has been performed.

## Clock / retention
Fit the supported coin-cell RTC battery to retain PCF85063 time across power loss. No onboard GPS or usable external GPS UART is claimed: RGB, USB, SD, I2C, RS485 and CAN occupy the documented pins. CYM advertises GPS not supported; the shared GPS qualification engine remains available to profiles with qualified UART wiring.

Choose Clock from either menu, then:
  Display Only: no Wi-Fi/STA/AP/DNS/mDNS/SNTP startup. Valid previously disciplined RTC restores UTC and reports RTC HOLDOVER. Unset/oscillator-stop/untrusted/unreasonable/backward RTC stays UNSYNCED.
  Client NTP: select a saved 2.4GHz Wi-Fi connection; public UTC discipline updates RTC and persists trust. Existing 60-second polling and bounded cancellation remain unchanged.
  AP NTP: serves local UTC and source quality; clients must connect to the displayed AP/IP. Untrusted time is advertised unsynchronized, never fake GPS quality.
Display offset is presentation only; RTC and NTP remain UTC. Missing/dead battery after power loss must never seed garbage. A fresh device with plausible but never-disciplined RTC is deliberately not trusted: first synchronize using Client NTP.

## Transport evidence and memory
Reference: retained official vendor-demo.zip SHA256 ba208ac802387189a079930dbc4b40bfacd1d8608045aba3b9b2838be5a8fbcd and vendor schematic SHA256 d5b0dd67ddf93fc2ac045043db9f65cbba12652f8ee20bd1fd719fe300ae8cb6.
The newer ESP-IDF/08_lvgl_v8_demo explicit 1024x600 branch uses 21MHz, horizontal back/front/pulse 145/170/30, vertical 23/12/2, negative PCLK. Although its default selects 800x480, this beta explicitly selects its 1024x600 timing branch. The older 05_IO_Test uses 18MHz and H188/44/88 V16/3/6; it is not silently mixed with the newer profile. Jim must qualify this choice on the physical 5B.
RGB DATA0..15: 14,38,18,17,10,39,0,45,48,47,21,1,2,42,41,40. VSYNC3/DE5/PCLK7/HSYNC46. I2C8/9. CH422G mode0x24/output0x38 are function addresses, NOT register indices. EXIO1 touch reset,2 backlight,3 LCD reset,4 SD CS are masked under one output mutex.
Two physical framebuffers consume 2457600 PSRAM bytes, two logical frames 614400 PSRAM bytes; two 10-line bounce buffers consume 40960 internal bytes, excluding driver overhead. ISR context/semaphore storage is persistent internal DRAM. Submission waits two frame-complete boundaries before recycling the old physical buffer. A timeout freezes ownership until the outstanding boundary completes. There is no SPI display completion semaphore. Native RGB565 has no SPI byte swap.
SD uses a dedicated 20MHz SPI2 bus (11 MOSI/12 SCK/13 MISO) and expander CS wrapped around serialized host command/data transactions; the reset preamble holds CS high through 80 idle clocks. Backlight/touch reset preserve SD and other output bits. No SD corpus refresh is included.

## Jim's physical acceptance checklist
1. Boot serial shows WS-S3-5B, 1024x600/x2, correct version, 8MB PSRAM; no resets or RGB underrun while Wi-Fi/BLE/SD are busy.
2. Classic and Modern: read labels comfortably; navigate Settings and Clock; scroll lists/popups; check red/green/blue/white/black and all four touch corners plus drag/release.
3. Mount and browse a known FAT SD; provision/read/write a test file; verify display/touch/backlight survive concurrent SD traffic.
4. Fresh/no battery: Display Only remains UNSYNCED after power loss and does not enable networking.
5. Client NTP: valid public UTC, RTC updated, timeout/retry and quick exit work; display offset never changes served UTC.
6. With coin cell, synchronize, power fully off/on: Display Only restores RTC HOLDOVER. Repeat without battery: no garbage restore.
7. AP NTP: connect a client to the displayed AP, query UDP123, confirm UTC/quality/request count; test unsynchronized startup as well.
8. Go Dark/dim: panel dark, outputs preserved, five-second touch hold wakes. Do not use BOOT as an app wake button.
