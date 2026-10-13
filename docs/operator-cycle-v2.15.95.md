# CYM v2.15.95 operator checks

## Release scope and honest acceptance

Gameplay ES8311 volume is +9 dB, using the existing codec volume path. The mixer,
I2S routing and amplifier lifecycle are unchanged. Positive gain may clip: report
actual loudness/distortion, not merely successful initialization/write counters.
Classic CYD and HackerBox CYD default brightness is 90%; a saved brightness wins.
Other board defaults are unchanged. Do not erase NVS to force a default.

## WS-C5-35 external GPS and console

Use primary USB-C for flashing/debugging; the secondary micro-USB is not needed.
Use a 3.3 V-compatible ATGM336 UART interface:

| WS35 expansion J3 | Module |
|---|---|
| pin24 GPIO11 UART1 TX | RX |
| pin26 GPIO12 UART1 RX | TX |
| pin28 GND | GND |
| pin32 VCC3V3 | 3.3 V supply, within module requirements |

The pinned vendor schematic assigns J3 U0TXD/U0RXD to GPIO11/12. Firmware remaps
those pins to UART1. GPIO11/12 also have selectable camera clock/select routes;
actual R56/R59 resistor population must be verified on the tester's board. Camera
software remains unused. Do not swap pins speculatively or modify resistors based
only on firmware enablement.

Application and IDF bootloader use native USB Serial/JTAG only. Generated app and
bootloader configs must both confirm USB primary and no UART secondary. Immutable
ROM output before the bootloader is a separate physical check; this release does
not burn eFuses or claim complete ROM UART silence.

Ask: "What should I see with the GPS plugged in?"
Expected: GPS Info shows received module/NMEA data. `No lock` means data detection,
not a valid position fix. A valid fix supplies coordinates; satellite count alone
does not establish fix/time trust. Shared baud discovery probes 9600/38400/115200,
then attempts normal configured baud sync. No persistent module-flash command is used.

Ask: "How do I collect useful GPS diagnostics?"
Expected: Settings -> Hardware -> Debug enables optional firmware diagnostics.
Wardrive -> Options -> GPS Debug enables the existing bounded `[GPSDBG]` heartbeat.
On WS35 primary USB-C supports `help`, `debug status`, `debug on`, `debug off`;
`debug status` reports NVS-persisted state. Do not expect the new interactive parser
on either Classic profile: their existing console configurations remain unchanged.
Keep actual RX/NMEA counters, module-presence, fix validity and satellite count
separate in reports. No valid NMEA points to receive/baud/routing; valid NMEA with
no fix points to the GPS fix boundary rather than a WiFi collection result.

## HackerBox / Classic passive WiFi checks

Owner reported HackerBox WiFi Observer and Scope failures. Both paths previously
required nonexistent PSRAM. Classic now uses bounded internal observer storage
(8 APs, 8 clients/AP, 16 probes) and an internal task stack; PSRAM boards retain
100 APs / 50 clients/AP / 200 probes. Scope uses native-width spectrum with a shorter
16-row waterfall on Classic, internal canvas memory and honest allocation failure
states. Wroom/S3 are 2.4 GHz only; Scope cannot select 5 GHz there.

Ask: "How do I verify Observer?"
Expected: WiFi -> WiFi Observer -> WiFi Observer; Start, Stop, Rescan and revisit
should collect nearby permitted APs/clients/probes without restart, blank screen,
heap failure or task overflow. Check Classic and Modern navigation and both
orientations. A host policy test is not evidence of received RF traffic.

Ask: "How do I verify Scope?"
Expected: WiFi Scope shows channel sweep and bars/waterfall on 2.4 GHz. If its
canvas/task cannot allocate, the screen explicitly says stopped/insufficient memory,
not a silent blank screen. Check Back/Home/re-entry and both orientations. Physical
memory headroom and responsiveness still require acceptance.

Ask: "Why does Wardrive show satellites but no networks?"
Expected: Existing Wardrive admission requires a valid fix or accepted cached
position; its task waits for fix before enabling capture. Sats alone is insufficient.
The owner's Wardrive failure is not yet diagnosed or claimed fixed. Record GPS
validity/coordinates, channel label (moving/CH--/STOPPED), network count, radio mode,
SD availability, and primary USB-C startup errors to localize the failure. Preserve
existing GPS and Classic console settings.

## Web flasher

Main flasher: https://jimgat.github.io/CYM/
All boards: https://jimgat.github.io/CYM/?beta=1
HackerBox: https://jimgat.github.io/CYM/?board=hackerbox-cyd

Groups appear as ESP32 Wroom, ESP32-S3, ESP32-C5; display names sort alphabetically
inside each group. HackerBox is shown by default and has no beta badge. It still
uses Development because no HackerBox Stable artifacts exist on `main`; board
promotion does not manufacture a Stable firmware release. Other Stable binaries
stay unchanged. `?beta=1` unlocks every registered board and selects Development.
Development binaries are pinned to the exact verified publication commit.

Flash a packaged full image at offset `0x0000`. For WS35 console-routing qualification
use full-image Flash All, not app-only Quick Flash: the IDF bootloader changed.
Release delivery includes immutable raw URLs and SHA-256 values.
