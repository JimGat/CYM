# Classic CYD external GPS

CYM supports an external NMEA GPS receiver on the Classic CYD (`CYD-2432S028R` / `CYD2USB`) through the board's P3 UART expansion JST. This uses the same shared GPS parser, status, wardriving, Universal Clock, and NTP integration as the S3 and C5 targets.

## Connection contract

- Use the **primary USB-C** port for programming and JTAG debugging.
- The **second Micro-USB** and the **P3 UART expansion JST** belong to the external UART path and are not used for the CYM console.
- The P3 UART must not carry CYM logs or debug output. The Classic production profile disables the ESP-IDF UART console and bootloader log stream.
- Connect the external GPS to P3 using the same UART/NMEA architecture as the S3 and C5 targets.
- GPS on P3 preserves NM-RF-HAT compatibility: the RF-HAT keeps its SD Card Shim SPI path and GPIO22/GPIO27 control lines, matching the working Bruce/HaleHound Classic wiring.

## Wiring

| Classic P3 UART expansion JST | ESP32 signal | Connect to GPS |
| --- | --- | --- |
| TX-labelled signal | GPIO1 / UART2 RX | GPS TX |
| RX-labelled signal | GPIO3 / UART2 TX | GPS RX (profile contract; leave disconnected in RX-only v2.15.64) |
| GND | Ground | GPS GND |
| VIN/power | Board connector supply | Use only when compatible with the GPS module's rated input |

Physical testing of v2.15.48/v2.15.49 and the reversed v2.15.50 mapping produced no GPS identification. CYM therefore follows the working Bruce and HaleHound Classic contract exactly: GPS TX feeds P3 TX/GPIO1 as UART2 RX, while P3 RX/GPIO3 is the profile UART2 TX contract; v2.15.64 does not attach or drive it. The same unmodified GPS harness works through NM-RF-HAT on NM-CYD-C5, so do not repin it for this Classic build.

For the first receive-only test, connect only power, ground, and **GPS TX to P3 TX/GPIO1**. Leave GPS RX disconnected. The reference Classic schematic labels P3 power as VIN and routes it to the board 5 V rail, whereas NM-CYD-C5 P5 supplies 3.3 V. CYM's standard ATGM336H breakout has an onboard voltage regulator and accepts either supply, so it is power-interchangeable between these boards. Verify the permitted VCC before substituting a different GPS module. UART logic remains 3.3 V; do not apply 5 V logic to an ESP32 GPIO.

## Firmware behavior

The Classic profile enables `BOARD_HAS_GPS` and `BOARD_TIME_HAS_GPS_UART` and maps the shared GPS stack to `UART_NUM_2`, with the profile contract UART2 RX on GPIO1 and TX on GPIO3. v2.15.64 attaches RX only and suppresses Classic module configuration writes. Before attaching UART2 RX, CYM explicitly establishes GPIO1 as an input, releasing its reset-time UART0 TX function, then connects it through ESP-IDF's UART input matrix. The UART0 console and bootloader log stream are disabled in the production profile so CYM does not transmit diagnostics onto P3. GPS status, parsing, baud/rate control, wardriving, Universal Clock, and NTP reuse the same shared implementation as the S3 and C5 builds. The GPS Setup footer is generated from the active board profile instead of displaying the former static UART1/IO4/IO5 text.

With valid NMEA input, the Classic build can provide:

- GPS presence, acquisition, and fix status
- live and last-known coordinates
- wardrive location data
- GPS-backed Universal Clock state
- GPS-disciplined NTP service when networking is active

## Validation status

Compilation and automated tests do not prove the physical connector, module power compatibility, NMEA baud, fix acquisition, or sustained runtime behavior. Validate the exact Classic board revision and GPS module on hardware before calling the path physically qualified.


## v2.15.64 corrected integration and evidence boundary

Co-developer @birolt29 supplied the CN1 autodetection intent. His daily
ESP32-2432S028R CN1 GPIO22 RX / GPIO27 TX build (#04+#05+#06) is self-reported
working, not an integration hardware test. The HAT GPIO1/3 route is
schematic-derived and was NOT hardware-tested by him. Jim's isolated
ClassicCYDgpsTest did physically receive checksummed NMEA on UART2 RX GPIO1
at 9600; that result is retained, but is not proof of this production build.

The profile wiring contract remains RX1/TX3. This build deliberately attaches
only RX: TX3 and TX27 are NOT driven, even after detection. Classic PCAS,
PMTK/UBX baud/rate commands are suppressed; the Options baud command therefore
returns false rather than claiming a successful module change. Receive baud
is shown separately from the stored preference. GPS RX may remain disconnected.
GPIO3 can share an onboard CH340 output: external outputs must not be tied
together. Check the physical schematic/bridge and use receive-only GPIO1 first.

Classic UART allocation/detection is deferred until critical boot allocations
complete; subsequent reception uses a bounded nonblocking main-loop single
reader and the shared NMEA parser, not a new dedicated task. Detection accepts
framed checksummed NMEA across split reads and considers configured, 115200,
38400 and 9600 baud. RF-HAT profiles reserve GPIO22/27 throughout and never
probe CN1. Without RF-HAT, CN1 RX22 is an input-only candidate, never TX27.
Absent initial detection returns to the profile route, with bounded late
receive-only detection windows and a live status footer. The earlier reverted
deferred-task/main-loop experiments and resets remain relevant: no green
build establishes the root cause fixed or qualifies boot/stack headroom.
