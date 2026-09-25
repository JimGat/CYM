# Hosyond ESP32-S3 Display Family

CYM is preparing shared-firmware support for three ESP32-S3 display boards sold by Hosyond/LCDWiki. These are development targets, not released CYM boards yet. They are not currently present in the stable/dev web-flasher selectors, and the existing `ESP32S3` image is a hardware bring-up stub rather than the full CYM application.

## Family summary

All three boards use an ESP32-S3 N16R8 module: dual-core Xtensa LX7 at up to 240 MHz, 16 MB flash, 8 MB OPI PSRAM, 2.4-GHz 802.11b/g/n Wi-Fi, and Bluetooth 5. They also provide capacitive touch, microSD, USB-C, battery charging, audio hardware, an RGB status LED, UART, and expansion pins. The display/touch/storage buses are not interchangeable across the whole family.

| CYM target | Vendor/SKU | Display | Touch | Native resolution | CYM state |
|---|---|---|---|---|---|
| `hosyond-s3-28` | ES3C28P (touch); ES3N28P is the no-touch sibling | ILI9341V, 4-line SPI | FT6336G, I2C | 240×320 | Planned; official core documentation imported |
| `hosyond-s3-35` | Hosyond 3.5-inch ESP32-S3 | ST77922, 4-data-line QSPI | ST77922/TDDI path used by the checked-in bring-up driver | 320×480 | Experimental bring-up stub builds; full CYM port pending |
| `hosyond-s3-40` | ES3C40P | ST7796S, 4-line SPI | FT6336U, I2C | 320×480 | Planned; official individual documentation imported |

Sources: [LCDWiki 2.8-inch product page](https://www.lcdwiki.com/2.8inch_ESP32-S3_Display), [LCDWiki 3.5-inch product page](https://www.lcdwiki.com/3.5inch_ESP32-S3_Display), and [LCDWiki 4.0-inch product page](https://www.lcdwiki.com/4.0inch_ESP32-S3_Display).

## Confirmed differences

| Resource | 2.8-inch | 3.5-inch | 4.0-inch |
|---|---|---|---|
| LCD controller/bus | ILI9341V / 4-line SPI | ST77922 / QSPI | ST7796S / 4-line SPI |
| Touch controller | FT6336G | Board-specific ST77922/TDDI driver in current bring-up | FT6336U |
| LCD data pins | CS 10, DC 46, SCK 12, MOSI 11, MISO 13 | CS 10, SCK 11, QSPI D0–D3 12–15 | CS 10, DC 46, SCK 12, MOSI 11, MISO 13 |
| Backlight | GPIO45 | GPIO9 | GPIO45 |
| Touch I2C | SDA 16, SCL 15 | SDA 8, SCL 18 | SDA 16, SCL 15 |
| Touch reset/interrupt | RST 18, INT 17 | Documentation conflict: checked-in header and vendor workbook reverse GPIO47/48 | RST 18, INT 17 |
| microSD | SDIO CLK 38, CMD 40, D0–D3 39/41/48/47 | SDMMC CLK 45, CMD 38, D0–D3 39/40/41/42 | SDIO CLK 38, CMD 40, D0–D3 39/41/48/47 |
| Battery ADC | GPIO9 | GPIO3 | GPIO9 |
| RGB LED | GPIO42 | GPIO17 | GPIO42 |
| UART0 | RX 43, TX 44 | RX 43, TX 44 | RX 43, TX 44 |
| Expansion | GPIO2/3/14/21 | Different/shared pin exposure; verify before enabling peripherals | GPIO2/3/14/21 |

The 2.8-inch and 4.0-inch boards are close enough to share a common ESP32-S3 peripheral-map base, with display/touch controller and geometry overrides. The 3.5-inch board requires a separate low-level display/touch/storage backend but should still compile the same CYM application and UI source.

## Documentation caveats requiring hardware proof

- The checked-in 3.5-inch package/header and LCDWiki’s current ES3C35P page appear to describe different board revisions. The tracked package maps QSPI SCK/D0–D3 to GPIO11/12/13/14/15, backlight to GPIO9, touch I2C to GPIO8/18, and SDMMC to GPIO45/38/39–42. The current ES3C35P page instead maps QSPI SCK/D0–D3 to GPIO12/11/13/14/9, backlight to GPIO41, touch I2C to GPIO38/39, and SDIO to GPIO5/4/6/7/2/3. It also labels touch RST=48 and INT=47, while the tracked workbook/header disagree on those roles. Treat board revision/SKU identification and physical probing as mandatory before changing the proven bring-up header.
- The 2.8-inch page lists I2S output on GPIO8 and input on GPIO6, while the 4.0-inch page reverses those two signals. Confirm the schematics/vendor demos before enabling CYM audio.
- LCDWiki's 4.0-inch page links its “I/O resource allocation table” to the ES3C28P (2.8-inch) workbook. The 4.0-inch pin table and schematic are usable, but the workbook must not be treated as an independent 4.0-inch source.
- Product-page claims establish hardware design intent, not CYM runtime support. Every variant still needs independent display, touch, SD, radio, orientation, and stability testing.

## Shared-code requirements

- Compile the canonical `ESP32C5/main/` application sources for S3; do not copy/fork `main.c` or feature modules.
- Put display, touch, SD, backlight, orientation, and optional peripherals behind `board_hal` capabilities/backends.
- Gate unsupported S3 features: no 5-GHz Wi-Fi and no 802.15.4 radio.
- Do not expose RF-HAT, GPS, battery, audio, or other peripheral UI until its pins and runtime behavior are verified for that board.
- A shared-source change must continue building all three current release boards plus every S3 target included in that development phase.
- Compilation is not hardware qualification.

## Imported vendor files

Core vendor material is stored under:

- `docs/hardware/hosyond-s3-28/`
- `docs/hardware/hosyond-s3-35/`
- `docs/hardware/hosyond-s3-40/`

The repository stores the core specifications, schematics, pin workbook where a valid board-specific workbook exists, controller datasheets, and LCD initialization tables. The complete 2.8-inch vendor package may still be retained separately; it is not required to duplicate every vendor tool/example in the source repository.

## Support status

As of this document update:

- Released/supported CYM boards remain NM-CYD-C5, WS-C5-28, and CYD-2432S028.
- Hosyond S3 3.5 remains experimental bring-up.
- Hosyond S3 2.8 and 4.0 are documented port candidates.
- No Hosyond board has been promoted to release assets or the web flasher.
