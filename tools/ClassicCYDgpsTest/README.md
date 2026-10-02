# ClassicCYDgpsTest

Standalone, receive-only electrical diagnostic for the dual-USB Classic CYD
(ESP32-2432S028). It is intentionally separate from production CYM firmware.

## Safety and wiring

1. Flash `ClassicCYDgpsTest-full.bin` at offset `0x0000` with ESPConnect.
2. Power the GPS and connect common ground.
3. Connect **GPS TX only** to the Classic P1 signal being tested.
4. Leave GPS RX disconnected and leave the second Micro-USB/CH340 port unplugged.
5. Read the diagnostic results on the CYD display.

The utility never calls `uart_write_bytes`; UART2 is receive-only. Application
console and bootloader logs are disabled. It repeatedly scans GPIO1, GPIO3, and
GPIO26 at 9600, 38400, and 115200 baud for four seconds per combination.

## Display fields

- `B`: raw byte count
- `F/P/O`: framing, parity, and overflow/buffer-full errors
- `$`: NMEA sentence-start characters
- `L`: complete CR/LF-terminated lines
- `C`: lines with valid NMEA XOR checksums
- `HEX`: first received bytes in hexadecimal

`FOUND RX GPIO...` means valid checksummed NMEA was received. `NO UART BYTES`
after a complete cycle means none of the candidate pin/baud combinations saw
serial bytes. A byte count without valid checksums still proves electrical
activity and usually points to baud, framing, or signal-integrity trouble.

GPIO26 is normally the passive buzzer in CYM. This diagnostic releases it to
input only while testing; it does not alter production firmware.

## Build the diagnostic utility

```sh
. /home/dev/esp/esp-idf/export.sh
cd tools/ClassicCYDgpsTest
./build.sh
```

The script creates the ESPConnect-compatible merged image
`ClassicCYDgpsTest-full.bin`. Flash it at `0x0000`.
