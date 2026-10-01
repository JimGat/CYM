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
| TX-labelled signal | GPIO1 / UART1 TX | GPS RX (optional for receive-only NMEA) |
| RX-labelled signal | GPIO3 / UART1 RX | GPS TX |
| GND | Ground | GPS GND |
| VIN/power | Board connector supply | Use only when compatible with the GPS module's rated input |

Physical testing of v2.15.48 and v2.15.49 produced no GPS identification with the prior GPIO1-RX/GPIO3-TX interpretation. The Classic mapping is therefore reversed for this A/B test: GPS TX feeds P1 RX/GPIO3, while P1 TX/GPIO1 can send optional configuration commands to GPS RX. A plug-and-play NM-CYD-C5 GPS lead may need its two UART signal contacts repinned for the Classic. With CYM's standard ATGM336H breakout the power contacts are compatible, but the signal positions are not automatically interchangeable.

For the first receive-only test, connect only power, ground, and **GPS TX to P1 RX/GPIO3**. Leave GPS RX disconnected. The reference Classic schematic labels P1 power as VIN and routes it to the board 5 V rail, whereas NM-CYD-C5 P5 supplies 3.3 V. CYM's standard ATGM336H breakout has an onboard voltage regulator and accepts either supply, so it is power-interchangeable between these boards. Verify the permitted VCC before substituting a different GPS module. UART logic remains 3.3 V; do not apply 5 V logic to an ESP32 GPIO.

## Firmware behavior

The Classic profile enables `BOARD_HAS_GPS` and `BOARD_TIME_HAS_GPS_UART` and maps the shared GPS stack to `UART_NUM_1`, with RX on GPIO3 and TX on GPIO1. Before attaching UART1 RX, CYM explicitly establishes the selected GPIO3 receive pin as an input, then connects it through ESP-IDF's UART input matrix. The UART0 console and bootloader log stream are disabled in the production profile so CYM does not transmit diagnostics onto P1. GPS status, parsing, baud/rate control, wardriving, Universal Clock, and NTP reuse the same shared implementation as the S3 and C5 builds.

With valid NMEA input, the Classic build can provide:

- GPS presence, acquisition, and fix status
- live and last-known coordinates
- wardrive location data
- GPS-backed Universal Clock state
- GPS-disciplined NTP service when networking is active

## Validation status

Compilation and automated tests do not prove the physical connector, module power compatibility, NMEA baud, fix acquisition, or sustained runtime behavior. Validate the exact Classic board revision and GPS module on hardware before calling the path physically qualified.
