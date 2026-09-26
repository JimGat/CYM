# Hosyond ESP32-S3 Display Family

CYM supports the Hosyond/LCDWiki ES3C35P 3.5-inch as a shared-CYM software target beginning with v2.15.27. It compiles the canonical `ESP32C5/main/` application and is integrated into the shared web flasher. Display and touch are physically qualified; the remaining peripheral acceptance checklist is pending. The 2.8-inch and 4.0-inch variants remain experimental development targets.

## Family summary

All three boards use an ESP32-S3 N16R8 module: dual-core Xtensa LX7 at up to 240 MHz, 16 MB flash, 8 MB OPI PSRAM, 2.4-GHz 802.11b/g/n Wi-Fi, and Bluetooth 5. They also provide capacitive touch, microSD, USB-C, battery charging, audio hardware, an RGB status LED, UART, and expansion pins. The display/touch/storage buses are not interchangeable across the whole family.

| CYM target | Vendor/SKU | Display | Touch | Native resolution | CYM state |
|---|---|---|---|---|---|
| `hosyond-s3-28` | ES3C28P (touch); ES3N28P is the no-touch sibling | ILI9341V, 4-line SPI | FT6336G, I2C | 240×320 | Planned; official core documentation imported |
| `hosyond-s3-35` | ES3C35P | ST77922, 4-data-line QSPI | Integrated ST77922/TDDI I2C path at 0x55 | 320×480 | Supported shared-CYM software target v2.15.27; display/touch qualified; peripheral acceptance pending |
| `hosyond-s3-40` | ES3C40P | ST7796S, 4-line SPI | FT6336U, I2C | 320×480 | Planned; official individual documentation imported |

Sources: [LCDWiki 2.8-inch product page](https://www.lcdwiki.com/2.8inch_ESP32-S3_Display), [LCDWiki 3.5-inch product page](https://www.lcdwiki.com/3.5inch_ESP32-S3_Display), and [LCDWiki 4.0-inch product page](https://www.lcdwiki.com/4.0inch_ESP32-S3_Display).

## Confirmed differences

| Resource | 2.8-inch | 3.5-inch | 4.0-inch |
|---|---|---|---|
| LCD controller/bus | ILI9341V / 4-line SPI | ST77922 / QSPI | ST7796S / 4-line SPI |
| Touch controller | FT6336G | Board-specific ST77922/TDDI driver in current bring-up | FT6336U |
| LCD data pins | CS 10, DC 46, SCK 12, MOSI 11, MISO 13 | **Qualified:** CS 10, SCK 12, QSPI D0–D3 11/13/14/9 | CS 10, DC 46, SCK 12, MOSI 11, MISO 13 |
| Backlight | GPIO45 | **Qualified:** GPIO41, active high | GPIO45 |
| Touch I2C | SDA 16, SCL 15 | **Qualified:** SDA 38, SCL 39, address 0x55 | SDA 16, SCL 15 |
| Touch reset/interrupt | RST 18, INT 17 | **Working profile:** RST 48, INT 47 | RST 18, INT 17 |
| microSD | SDIO CLK 38, CMD 40, D0–D3 39/41/48/47 | Current-page map: CLK 5, CMD 4, D0–D3 6/7/2/3; CYM SPI mode CS3/SCK5/MOSI4/MISO6; **mount still unqualified** | SDIO CLK 38, CMD 40, D0–D3 39/41/48/47 |
| Battery ADC | GPIO9 | Current-page/profile GPIO8; **unqualified** | GPIO9 |
| RGB LED | GPIO42 | Current-page/profile GPIO40; **unqualified** | GPIO42 |
| UART0 | RX 43, TX 44 | RX 43, TX 44 | RX 43, TX 44 |
| Expansion | GPIO2/3/14/21 | Different/shared pin exposure; verify before enabling peripherals | GPIO2/3/14/21 |

The 2.8-inch and 4.0-inch boards are close enough to share a common ESP32-S3 peripheral-map base, with display/touch controller and geometry overrides. The 3.5-inch board requires a separate low-level display/touch/storage backend but should still compile the same CYM application and UI source.

## Documentation caveats requiring hardware proof

- **3.5-inch discrepancy resolved for Jim’s ES3C35P (2026-09-25):** physical display/touch testing matches the current LCDWiki map (CS10, SCK12, QSPI D0–D3=11/13/14/9, BL41, touch SDA38/SCL39/RST48/INT47 at 0x55), not the older checked-in package/workbook. The older files describe a different revision and remain historical evidence only. The upstream ST77922 default init is also for a 532×300 panel; this board requires the factory 63-entry 320×480 table, 40 MHz QSPI, INVON/RGB565, no mirror, and 4-pixel X alignment. After changing panel firmware, physically power-cycle because LCD reset is tied to EN/CHIP_PU. See the board-specific README for the complete discrepancy table and remaining unqualified peripherals.
- The 2.8-inch page lists I2S output on GPIO8 and input on GPIO6, while the 4.0-inch page reverses those two signals. Confirm the schematics/vendor demos before enabling CYM audio.
- LCDWiki's 4.0-inch page links its “I/O resource allocation table” to the ES3C28P (2.8-inch) workbook. The 4.0-inch pin table and schematic are usable, but the workbook must not be treated as an independent 4.0-inch source.
- Product-page claims establish hardware design intent, not CYM runtime support. Every variant still needs independent display, touch, SD, radio, orientation, and stability testing.

## Shared-code requirements

- Compile the canonical `ESP32C5/main/` application sources for S3; do not copy/fork `main.c` or feature modules.
- Put display, touch, SD, backlight, orientation, and optional peripherals behind `board_hal` capabilities/backends.
- Gate unsupported S3 features: no 5-GHz Wi-Fi and no 802.15.4 radio.
- ES3C35P exposes SD, RGB, battery ADC, and external UART GPS through its board profile for acceptance testing; audio, vibrator, and RF-HAT remain gated.
- A shared-source change must continue building NM-CYD-C5, WS-C5-28, CYD-2432S028, and the promoted ES3C35P target.
- Compilation is not hardware qualification.

## Imported vendor files

Core vendor material is stored under:

- `docs/hardware/hosyond-s3-28/`
- `docs/hardware/hosyond-s3-35/`
- `docs/hardware/hosyond-s3-40/`

The repository stores the core specifications, schematics, pin workbook where a valid board-specific workbook exists, controller datasheets, and LCD initialization tables. The complete 2.8-inch vendor package may still be retained separately; it is not required to duplicate every vendor tool/example in the source repository.

## Support status

As of this document update:

- Supported software targets are NM-CYD-C5, WS-C5-28, CYD-2432S028, and Hosyond ES3C35P 3.5-inch.
- ES3C35P display/touch are physically qualified; SD, RGB, battery, external GPS, Wi-Fi, BLE, and bounded soak remain pending on the shared-CYM image.
- Hosyond S3 2.8-inch and 4.0-inch remain experimental documented port candidates.
- Build success is not physical qualification.
