# Classic CYD external GPS

CYM supports an external NMEA GPS receiver on the Classic CYD (`CYD-2432S028R` / `CYD2USB`) through the board's P1 UART expansion JST. This uses the same shared GPS parser, status, wardriving, Universal Clock, and NTP integration as the S3 and C5 targets.

## Connection contract

- Use the **primary USB-C** port for programming and JTAG debugging.
- The **second Micro-USB** and the **P1 UART expansion JST** belong to the external UART path and are not used for the CYM console.
- The P1 UART must not carry CYM logs or debug output. The Classic production profile disables the ESP-IDF UART console and bootloader log stream.
- Connect the external GPS to P1 using the same UART/NMEA architecture as the S3 and C5 targets.
- GPS on P1 preserves NM-RF-HAT compatibility: the RF-HAT keeps its SD Card Shim SPI path and GPIO22/GPIO27 control lines, matching the working Bruce/HaleHound Classic wiring.

## Wiring

| Classic P1 UART expansion JST | ESP32 signal | Connect to GPS |
| --- | --- | --- |
| TX-labelled signal | GPIO1 / UART1 RX | GPS TX |
| RX-labelled signal | GPIO3 / UART1 TX | GPS RX (optional for receive-only NMEA) |
| GND | Ground | GPS GND |
| VIN/power | Board connector supply | Use only when compatible with the GPS module's rated input |

This follows the proven HaleHound/Bruce convention: GPS TX feeds GPIO1, while GPIO3 can send configuration commands to GPS RX. Use 3.3 V logic levels; do not apply 5 V logic to an ESP32 GPIO.

## Firmware behavior

The Classic profile enables `BOARD_HAS_GPS` and `BOARD_TIME_HAS_GPS_UART` and maps the shared GPS stack to `UART_NUM_1`, with RX on GPIO1 and TX on GPIO3. The UART0 console and bootloader log stream are disabled in the production profile so CYM does not transmit diagnostics onto P1. GPS status, parsing, baud/rate control, wardriving, Universal Clock, and NTP reuse the same shared implementation as the S3 and C5 builds.

With valid NMEA input, the Classic build can provide:

- GPS presence, acquisition, and fix status
- live and last-known coordinates
- wardrive location data
- GPS-backed Universal Clock state
- GPS-disciplined NTP service when networking is active

## Validation status

Compilation and automated tests do not prove the physical connector, module power compatibility, NMEA baud, fix acquisition, or sustained runtime behavior. Validate the exact Classic board revision and GPS module on hardware before calling the path physically qualified.
