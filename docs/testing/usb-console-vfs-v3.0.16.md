# v3.0.16 Development: USB debug console VFS route

## Narrow correction

The installed ESP-IDF v6.0.2 USB Serial/JTAG VFS registers `/dev/secondary`
when USB is the secondary console and `/dev/usbserjtag` for the primary route.
The debug console now opens both input and output using the configured route.
No console flags, physical ports, GPS routing, pin assignments, stack capacity,
NVS, partitions or board configurations are changed. Classic CYD and HackerBox
retain intentionally disabled console behavior.

On Waveshare ESP32-C5-Touch-LCD-2.8 (WS-C5-28), the reported v3.0.15 startup
failure was `Input stream failed`, `ESP_FAIL`, `errno=2` with 79,042 bytes of
internal free memory and a 51,200-byte largest block. This is a missing VFS path,
not evidence of console worker allocation failure. WS-C5-28, NM-CYD-C5 and
Pancake-C5 use the secondary route; Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35)
uses the primary route. Existing SDK configuration remains authoritative.

## Evidence and acceptance limits

The production-source host harness compiles primary and secondary routes
separately with ASan/UBSan, models the IDF-registered path, and exercises startup,
failure cleanup, retry, borrowed-driver ownership and idempotence. There are
26 passing cases across the two routes. The established host regression runs
660 tests with one unavailable private-capture fixture skipped.

All eight board profiles built successfully at shared version v3.0.16. The canonical
package gate verified eight boards and 32 artifacts: packaged/generated equality,
application descriptors, board flags, flash offsets and merged image layouts.
Independent publication review remains required.
Build/host evidence is not physical command reception, logging-under-load or NVS
persistence acceptance. No flashing or publication is part of this preparation.
The separate AP mDNS allocation issue is unchanged and is not fixed by this patch.

## Pending physical input check

On the matching board and existing partition layout, without erasing settings,
open the existing USB serial port with carriage-return input. Send `debug status`,
`debug on` and `debug query`; retain actual replies and console startup status.
Seeing USB logs alone does not establish command input. Reboot and inspect the
saved setting separately before claiming persistence. Check logging under load
separately. Physical acceptance remains pending.
