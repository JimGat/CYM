# HackerBox CYD experimental v2.15.59

Amberjack 0131: red/blue reversal, clipped UI, incomplete calibration. Controller unverified. Candidate retains ILI9341 and Classic pins/console/GPS, BGR, inversion OFF, swap OFF, mirrors ON/OFF, 240x320 native portrait. Portrait is intentional. Existing Classic mapping unchanged.

Build: make hackerbox-cyd. Isolated package/manifest. Dev flasher entry requires beta=1; stable Pages may lack this entry, so use immutable full image at 0x0000.

New touch_hb NVS namespace starts calibration automatically. Press firmly at TL, TR, BL, BR brackets, lifting between taps. All four targets must be visible. Confirm OK within 5 seconds. Bad samples retry without saving. No invented ADC calibration constants.

Report full coverage/no strip, colors, non-mirrored readable text, four visible targets, OK alignment and reboot persistence. If clipped, stop and send photo. Hardware unvalidated.

User-reported markings (preserved literally): Guition; ESP32 2432S028; 2626 v1.4. These do not prove controller identity.

Physical .57 test: Jim reports correct rotation/color, but upside-down/mirrored relative to expected orientation. Photo normalized to USB-bottom shows horizontal glyph reflection with heading above buttons. .58 toggles X mirror only, preserving BGR and swap OFF. Hardware validation pending.

User explicitly clarified physical top = ESP antenna, bottom = USB-C; 180-degree correction is also required. .58 build cancelled/unpublished. .59 flips both axes relative to that abandoned candidate, using mirrors ON/OFF. No physical confirmation yet.

## Shareable board links

Beta: `https://jimgat.github.io/CYM/beta/?beta=1&board=hackerbox-cyd` (deployment pending). Existing root UI requires deployment before it understands new parameters/boards. Registered IDs only; unknown or unavailable IDs fall back to NM-CYD-C5. Selecting a board never connects/flashes automatically.

Physical feedback: v2.15.59 looks OK after extended power-off. Keep LCD clock at 40MHz; no further display tuning planned without recurring symptoms. Unplug all power for about 10 seconds after panel configuration updates before evaluating ghosting. Calibration success remains to be confirmed.

Jim confirms calibration completed and touch alignment is good on v2.15.59. Reboot persistence has not been explicitly confirmed.
