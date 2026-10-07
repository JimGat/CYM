# Patch #03: Hidden Camera tap and battery indicator

## Scope and provenance

This integration retains the owner-approved work supplied by CYM co-developer @birolt29 in Patch #03, then applies narrow review corrections for gesture lifetime, LVGL ownership, ADC error handling, and object lifecycle. Corrective integration changes are separate maintainer work. Doom is not part of this patch.

@birolt29 reported compiling, flashing, and bench-testing the four release-board variants from his source tree. That report is contributor evidence, not a claim that these repository artifacts were physically qualified. The integration gate rebuilds and packages all eight current shared-source targets; physical validation of these exact artifacts remains pending.

## User-visible behavior

- Hidden Camera rows keep their identity from LVGL `PRESSED` through `CLICKED` or `PRESS_LOST`, so a count change cannot clean and recreate the touched row mid-gesture. RSSI text continues to refresh without replacing rows, and deferred list changes apply on the next timer tick.
- Battery acquisition runs every 10 seconds on boards that declare `BOARD_HAS_BATTERY_ADC`.
- The indicator is a voltage estimate, not a fuel gauge: green above 65%, amber from 26-65%, red at or below 25%, and blinking red at or below 10%.
- `FULL` means measured VBAT is at least 4.15 V. It does not assert charging or charger completion.
- WS-C5-28 reads the CH32V003 expander EXIO_ADC at I2C address 0x24 as a 10-bit value with an approximately 3.3 V reference and a 3:1 divider. Calibration remains unity because the two supplied observations had opposite error signs.
- WS-C5-35 remains unsupported for this acquisition path; its CH32V006/AXP2101 hardware is different.
- Classic and Modern menu navigation are unchanged. The shared home and submenu title bars reserve space for the indicator.

## Operator check

1. Open Hidden Camera in either menu layout and tap a changing row once. Expected: the selected device opens immediately; the row is not replaced during the gesture.
2. Return to the list. Expected: deferred additions/removals appear and RSSI continues updating.
3. On WS-C5-28, wait at least 10 seconds after startup. Expected: a percentage or voltage-threshold `FULL` badge appears without overlapping GPS or Go Dark.
4. Navigate repeatedly between Home and submenus. Expected: one indicator remains, its critical blink continues safely, and no stale-object fault occurs.
5. On unsupported boards, expected: no fabricated battery reading appears.

Host builds and contracts cannot prove touch feel, ADC accuracy, charger state, or teardown stability on physical hardware. Capture serial output and screen observations when these exact binaries are tested.
