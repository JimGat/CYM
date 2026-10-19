# Classic USB Debug operator instructions

Applies only to Classic CYD-2432S028 and HackerBox Amberjack 0131 CYD. Hardware acceptance of this runtime option is NOT VERIFIED. Other boards retain their existing console behavior.

## Start logging

1. Physically unplug the GPS harness before enabling debug. A powered GPS TX can contend electrically with UART0 TX on GPIO1 even if firmware GPS is disabled. Disabling GPS in a menu is NOT sufficient. Disconnect other external drivers on that shared signal too.
2. Connect the verified board USB-to-UART bridge to your computer. Open its serial port at **115200 baud, 8 data bits, no parity, 1 stop bit, no hardware flow control**. Do not assert DTR/RTS or use an auto-reset monitor if you want to retain the acknowledged runtime session.
3. From either Classic or Modern Home, open Settings, Hardware Options, then the separate **Classic USB Debug** entry. Scroll the Hardware Options tile area if necessary, especially in landscape. The existing **Debug diagnostics** switch is verbosity, not this transport.
4. Read the warning and tap **I disconnected GPS - Enable**. Cancel / Close before acknowledgement leaves normal GPS and silent application logging unchanged. Expected status: ON, 115200 8N1, GPS unavailable. The serial stream starts with an application log containing `Classic USB Debug ON` (best effort); subsequent existing application logs are forwarded. No command prompt is provided.
5. For optional diagnostic measurements, enable **Debug diagnostics** separately in Hardware Options. That verbosity setting remains persisted across reboot; the USB Debug transport never is. Returning with Back/Home or closing the popup preserves an already acknowledged active transport. Reopening Hardware Options shows the current mode. GPS Info explicitly reports GPS unavailable; old coordinates may remain last-known/stale, never a live fix.

Both the tile list and the bounded popup scroll in portrait and landscape. No new GPS task or serial REPL is started. C5/S3 native-console behavior is not changed.

## Return to normal GPS

1. Leave GPS physically unplugged. Open Classic USB Debug again and tap **Return normal / Reboot**.
2. The firmware restores the previous log sink, detaches UART0 TX from GPIO1 and deletes its owned UART0 driver before rebooting. The next boot is normal, USB Debug OFF. GPS initialization is inhibited from the acknowledged attempt until that reboot, including failed enable attempts; it cannot restart into a partially removed log transport.
3. Power off before reconnecting GPS, then power on for normal GPS operation. This also avoids connecting GPS during reset-time ROM pin activity. Do not infer that an application shutdown can control ESP32 ROM behavior.
4. If enable or TX shutdown fails, the UI reports failure and leaves GPS inhibited. A failed TX shutdown does not reboot. Keep GPS disconnected; power off before restoring the harness. Re-entry after a failed attempt requires reboot/power cycle, not another acknowledgement. Repeated enable while already ON is idempotent.

## Logging limits and connector facts

- Application ESP-IDF logs only after acknowledgement. No replay of startup messages, ROM boot diagnostics, bootloader output, panic/backtrace capture, or crash durability is promised.
- `CONFIG_ESP_CONSOLE_NONE` and bootloader log level NONE remain unchanged. Default application/bootloader UART logging stays silent; original ESP32 ROM/reset/download behavior is separate and cannot be controlled by this runtime option. This is not native USB/JTAG on the original ESP32.
- Output is bounded and best effort: each logger call uses a 128-byte stack buffer and emits at most 127 bytes into available UART FIFO space without waiting. Long calls are truncated; FIFO-full, concurrent or reentrant calls may be partially emitted or dropped. Heavy bursts may join or truncate lines. There is no per-log heap allocation, output task, input parser, FSD expansion or transport NVS key.
- The Guition V1.4 photo identifies **P1 VIN/TX/RX/GND**. The older V0.1 schematic connects P1 through 100 ohm signal resistors to UART0 GPIO1/GPIO3; that is not a continuity measurement of the V1.4 assembly. Normal CYM GPS instead receives through the GPIO matrix as UART2 RX GPIO1; nominal UART2 TX GPIO3 remains undriven. **P3 is GND/35/22/21.** Exact USB2 socket routing remains unverified: do not assume independent selectable USB sockets. GPIO22/27 remain reserved when RF-HAT is enabled.

## Required physical retest before acceptance

- On both Classic and HackerBox: normal cold boot, GPS absent/present, NMEA acquisition and sustained fix; verify application/bootloader silence separately from ROM behavior.
- Both Home layouts and both screen orientations: find entry, scroll full warning and every action, Cancel with no TX drive, acknowledge, close, Back/Home and re-enter with correct state. Watch for stale UI pointers or timers.
- With GPS disconnected, scope GPIO1 and capture bridge logs at 115200; verify no runtime TX before acknowledgement, bounded output under load, debug verbosity separate, and GPS consumers/status/rate/baud/detection blocked while active.
- Exercise explicit shutdown, reboot and OFF default; scope TX release before restart and power off before reconnecting GPS. Repeat normal/enable/disable/reboot cycles, plus resource/setup failure paths where safely injectable.
- Development v3.0.28 software gates passed: all eight board builds, 32 packaged artifacts, 708 unit tests (one expected skip) and 20 standalone regression runners. Compilation and host tests do not establish electrical safety, bridge routing, boot reliability, RF/SD coexistence or hardware acceptance.
