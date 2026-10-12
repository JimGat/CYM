# Development v2.15.86: startup SD consent and display regression cycle

## Shared startup behavior (all eight boards)
After the first successful normal-startup SD mount, three read-only stat calls
check `/sdcard/lab/deauths`, `/sdcard/lab/gattwalker`, and `/sdcard/lab/otsurvey`.
Missing paths and files occupying directory paths trigger a consent overlay.
Later makes no provisioning changes. Provision requests the existing non-formatting
Validate & Provision owner after startup and any first-run home-layout selection.
There is no automatic formatting, overwrite, or repeated navigation prompt.
For an uncalibrated XPT2046 panel, the checks still run at mount; consent waits
until required touch calibration finishes so the buttons can be used safely.
A failed mount and isolated game startup do not trigger this prompt.

## Display correction
The owned internal DMA staging buffer grows from 1024 to 4096 bytes, within every
SPI adapter's maximum transfer size. A 320x15 RGB565 flush uses three color
transactions instead of fifteen; landscape 480-pixel rows are batched four at a
time. The buffer is boot allocated and aligned by the SPI bus allocator.
Ownership remains held until actual DMA completion; rejected enqueue does not
wait for nonexistent completion, and missing accepted completion remains fail-closed.
Watchdog feeds check the calling task's actual subscription. Startup rendering
no longer tries to feed main_task before its registration. SPI clocks and SD
frequency, watchdog timeout, partitions, radio behavior, audio, and calibration
are unchanged. Fewer transactions are proven in a production host harness;
physical latency/FPS must still be measured on both WS-C5-28 and WS-C5-35.

## Operator acceptance
1. Verify the packaged Beta version, then boot both Waveshare C5 boards.
2. Navigate Home, WiFi Menu, Scan & Attack, Detect & Defend, and Deauth Mon.
   Check screen painting, Back responsiveness, and absence of startup
   `esp_task_wdt_reset: task not found` errors. Save LONG handler timings.
3. Use an SD card missing one sentinel: expect a single popup listing it.
   Later must leave that path untouched. Reboot, choose Provision, and expect
   the existing Validate & Provision progress screen and missing directory creation.
4. Complete cards should boot without this popup. Test first-run layout selection,
   calibrated/uncalibrated resistive touch, portrait/landscape and both home layouts.
5. Separate physical game/audio acceptance remains outstanding.

## WS-C5-28 battery visibility
The badge starts as `BAT ?` until there is a usable voltage estimate.
Zero/error/below-range expander samples keep this honest unknown state visible,
instead of disappearing or inventing a percentage/presence status. Valid
percentage/FULL estimates and critical blinking are unchanged. The monitor retries
LVGL publication up to 20 times with bounded 100ms waits and 50ms yields, without
repeating sensor acquisition. Sampling stays 10s; the startup log now says 10s.
Other boards retain their existing battery behavior. No ADC routing, divider,
reference voltage, calibration or charger detection changed. This is a visibility
correction, not proof of corrected ADC accuracy.

Check Classic/Modern Home and a function page. A usable sample should become an
icon plus percentage/FULL. If `BAT ?` persists, save startup battery initialization,
`Battery ADC read failed`, or out-of-range messages. Do not assume battery absence.
