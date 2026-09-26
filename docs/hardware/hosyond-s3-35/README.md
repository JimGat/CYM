# Hosyond/LCDWiki ESP32-S3 3.5-inch source documents

Board family: **ES3C35P** / CYM target `hosyond-s3-35`.

Current official source: https://www.lcdwiki.com/3.5inch_ESP32-S3_Display

The checked-in specification, schematic, IO workbook, ST77922/TDDI protocol documents, and audio/touch datasheets came from an older vendor package. That package is retained as provenance, but its GPIO table does **not** describe Jim's physically tested board. The live LCDWiki ES3C35P page and the hardware-qualified CYM profile are authoritative for this unit.

## Hardware-qualified display/touch profile (2026-09-25)

Physical board testing with CYM-S3 `v2.13.85` established:

| Item | Qualified value |
|---|---|
| SoC / memory | ESP32-S3 N16R8; 16 MB flash; 8 MB OPI PSRAM at 80 MHz |
| Panel | ST77922 TDDI, native portrait 320×480, QSPI |
| QSPI pins | CS=GPIO10, SCK=GPIO12, D0=GPIO11, D1=GPIO13, D2=GPIO14, D3=GPIO9 |
| QSPI display clock | 40 MHz (panel-only; flash and OPI PSRAM remain 80 MHz) |
| Backlight | GPIO41, active high |
| LCD reset | Tied to EN/CHIP_PU; no independent LCD reset GPIO |
| Init profile | ES3C35P factory/vendor 63-entry table; CASET `0x013f`, RASET `0x01df` |
| Pixel format | RGB565, RGB element order, big-endian transport, inversion ON (`0x21`) |
| Orientation | Native portrait; `mirror_x=false`, `mirror_y=false` (MADCTL `0x00`) |
| Draw alignment | X start/end rounded to 4-pixel boundaries |
| Touch | Integrated ST77922/TDDI I2C path at `0x55`; SDA=GPIO38, SCL=GPIO39, RST=GPIO48, INT=GPIO47 |
| Physical proof | Image visible; text reads normally; top diagnostic bar red; title cyan; touch coordinates green and responsive |

The source-of-truth profile is `ESP32C5/components/board_hal/include/boards/hosyond_s3_35.h`; the board-specific panel table is `ESP32S3/main/hosyond_s3_35_lcd_init.h`.

## Documentation and upstream discrepancies

| Source/assumption | Discrepancy | Resolution |
|---|---|---|
| Older checked-in vendor package/workbook | Lists SCK/D0-D3 as GPIO11/12/13/14/15, backlight GPIO9, touch I2C GPIO8/18, SDMMC GPIO45/38/39-42, battery GPIO3, RGB GPIO17 | Describes a different/older board revision. Do not use its GPIO table for Jim's ES3C35P. Keep the files only as historical vendor evidence. |
| Current LCDWiki ES3C35P page | Lists CS10, SCK12, D0/D1/D2/D3=11/13/14/9, BL41, touch SDA38/SCL39/RST48/INT47, SDIO CLK5/CMD4/D0-D3=6/7/2/3 | Matches the physically working display/touch profile and is authoritative for this board. SD/audio/battery/RGB remain separately unqualified. |
| Upstream `esp_lcd_st77922` built-in default | Uses CASET/RASET `0x0213`/`0x012b` for a 532×300 panel | Wrong for ES3C35P. Supplying `init_cmds=NULL` produces a bad scan window/partial lines. Always supply the factory 63-entry 320×480 table. |
| Earlier CYM profile | QSPI at 80 MHz | ST77922 spec gives a 16 ns minimum write cycle (~62.5 MHz maximum). Use 40 MHz only for the panel bus. |
| Earlier CYM orientation call | `mirror_x=true` | Made text read backwards. Correct native portrait is no X/Y mirror. |
| USB serial/JTAG reset after flashing | Assumed to reset LCD | It resets the CPU but does not toggle EN/CHIP_PU, so the LCD may retain the previous bad state. For initial bring-up after changing panel firmware: unplug USB-C, wait about 10 seconds, reconnect. Once correctly initialized, ordinary soft reboots are acceptable. |
| Faint residual lines after wrong init | Appeared screen-burned | Observed fading while the correct image remained active: temporary image retention from the bad scan state, not confirmed permanent damage. |

## Qualification boundary

Display rendering, orientation, RGB565 colors, and responsive touch are physically qualified for Jim's ES3C35P. The current image is still a bring-up stub, not the shared CYM application. SD currently times out during mount, and SD, audio, battery ADC/scaling, RGB LED, expansion pins, long-run stability, packaging/manifests, and web-flasher integration remain unqualified. Do not promote this board to release status until those gates and the shared-CYM port pass.
