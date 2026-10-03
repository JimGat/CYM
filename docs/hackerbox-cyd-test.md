# HackerBox CYD experimental v2.15.57

Amberjack 0131: red/blue reversal, clipped UI, incomplete calibration. Controller unverified. Candidate retains ILI9341 and Classic pins/console/GPS, BGR, inversion OFF, swap OFF, mirrors ON/ON, 240x320 native portrait. Portrait is intentional. Existing Classic mapping unchanged.

Build: make hackerbox-cyd. Isolated package/manifest. Dev flasher entry requires beta=1; stable Pages may lack this entry, so use immutable full image at 0x0000.

New touch_hb NVS namespace starts calibration automatically. Press firmly at TL, TR, BL, BR brackets, lifting between taps. All four targets must be visible. Confirm OK within 5 seconds. Bad samples retry without saving. No invented ADC calibration constants.

Report full coverage/no strip, colors, non-mirrored readable text, four visible targets, OK alignment and reboot persistence. If clipped, stop and send photo. Hardware unvalidated.

User-reported markings (preserved literally): Guition; ESP32 2432S028; 2626 v1.4. These do not prove controller identity.
