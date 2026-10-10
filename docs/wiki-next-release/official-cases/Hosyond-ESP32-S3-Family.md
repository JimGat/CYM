# Hosyond ESP32-S3 Display Family

## Official case and assembly manuals

Start with the **[Official CYM Cases](Official-Cases)** supplied by co-developer **@birolt29** for Hosyond ES3C35P 3.5-inch (Standard or Slim). The collection provides original EN/DE/TR manuals, print models and photos, preserving @birolt29 / @alen29 credits and CC BY-NC-ND 4.0 licensing. Check its wiring/charging and fit caveats before assembly; case designation is not peripheral qualification. Older RF-HAT/community enclosures remain alternatives on [Where To Get It](Where-To-Get-It#3d-printed-cases).

> **Release status:** the Hosyond ES3C35P 3.5-inch (`hosyond-s3-35`) is a released shared-CYM target as of v2.15.34 and is selectable in the web flasher. The 2.8-inch and 4.0-inch variants remain planned, independently gated ports.

CYM is preparing one shared-code port for the Hosyond/LCDWiki ESP32-S3 display family. All variants use an ESP32-S3 N16R8 module (dual-core Xtensa LX7, 16 MB flash, 8 MB OPI PSRAM), 2.4-GHz Wi-Fi, Bluetooth 5, capacitive touch, microSD, USB-C, battery charging, audio hardware, and an RGB LED. They do not have the ESP32-C5's 5-GHz or 802.15.4 radios.[1][2]

## Model differences

| CYM target | Vendor model | Display | Touch | Resolution | Port state |
|---|---|---|---|---|---|
| `hosyond-s3-28` | ES3C28P | ILI9341V, 4-line SPI | FT6336G, I2C | 240×320 | Planned; official core docs imported |
| `hosyond-s3-35` | Hosyond ES3C35P 3.5-inch | ST77922, QSPI | ST77922 TDDI/capacitive touch | 320×480 | Released in v2.15.34; shared CYM app + web flasher |
| `hosyond-s3-40` | ES3C40P | ST7796S, 4-line SPI | FT6336U, I2C | 320×480 | Planned; official individual docs imported |

The 2.8-inch and 4.0-inch boards share most of their peripheral pin map: LCD CS 10, DC 46, SCK 12, MOSI 11, MISO 13, backlight 45; touch SDA 16, SCL 15, reset 18, interrupt 17; SDIO clock 38, command 40, and data 39/41/48/47; battery ADC 9; RGB LED 42; UART RX/TX 43/44; expansion GPIO2/3/14/21.[1][2]

The 3.5-inch board uses a narrow low-level HAL backend while compiling the same CYM application and UI sources. Hardware qualification established the current ES3C35P display/touch profile: ST77922 QSPI at 40 MHz, 320×480, capacitive touch, and the current LCDWiki pin generation. Older checked-in vendor material describes a different revision and must not override the qualified profile.[3]

## Documentation cautions

- The released 3.5-inch profile follows the physically qualified current-board wiring (LCD CS10, SCK12, D0=11, D1=13, D2=14, D3=9; backlight 41; touch SDA38/SCL39/RST48/INT47). Older checked-in vendor material describes another revision and must not be used to rewrite this mapping without new hardware proof.[3]
- The 2.8-inch and 4.0-inch product pages reverse the published I2S input/output roles for GPIO6 and GPIO8. Audio stays disabled until checked against schematics/vendor demos and hardware.
- LCDWiki's 4.0-inch page links its IO-workbook entry to the 2.8-inch ES3C28P workbook, so CYM uses the 4.0-inch schematic and page pin table rather than treating that workbook as independent 4.0-inch evidence.[2]

## CYM architecture

The S3 family will not receive copied application source. `ESP32S3` will compile the same canonical CYM sources used by the current boards. Display, touch, SD, backlight, orientation, and optional peripherals will be selected through `board_hal` capabilities/backends.

Features that require unavailable hardware—5-GHz Wi-Fi, 802.15.4, and unverified RF-HAT/GPS/peripheral mappings—will be hidden or disabled. Each physical model must independently pass display, touch, orientation, SD, Wi-Fi, BLE, ESP-NOW, reboot/cold-boot, and soak testing before release promotion.

## Current support boundary

- Released: NM-CYD-C5, WS-C5-28, CYD-2432S028, and Hosyond ES3C35P 3.5-inch.
- Planned/documented: Hosyond S3 2.8-inch and 4.0-inch.
- ES3C35P release boundary: shared CYM, display/touch, Modern/Classic navigation, and current Deauth Harvest workflow are exercised; SD, RGB LED, battery ADC, UART GPS, broader Wi-Fi/BLE qualification, and bounded soak remain open. Audio, vibrator, RF-HAT, 5 GHz, and 802.15.4 remain unavailable/gated.
- The ES3C35P manifest and binaries are deployed by the same web flasher as the other release boards.

## Sources

[1] https://www.lcdwiki.com/2.8inch_ESP32-S3_Display — 2.8inch ESP32-S3 Display - LCDWiki
[2] https://www.lcdwiki.com/4.0inch_ESP32-S3_Display — 4.0inch ESP32-S3 Display - LCDWiki
[3] https://www.lcdwiki.com/3.5inch_ESP32-S3_Display — 3.5inch ESP32-S3 Display - LCDWiki
