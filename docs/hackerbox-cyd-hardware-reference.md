# HackerBox CYD — Guition V1.4

Hardware supplied in HackerBox #0131 AMBERJACK, identified by Jim Gatwood. HackerBoxes lists the included platform as ESP32-2432S028R. User reports board marking `ESP32 2432S028` (space, not hyphen), two USB connectors, and Guition branding.

## Photographic evidence

![Guition CYD rear detail, photographed by Jim Gatwood](https://raw.githubusercontent.com/JimGat/CYM/Jimgat_Dev/docs/assets/hackerbox-cyd/guition-v1.4-back.jpg)

Original photograph: Jim Gatwood; supplied for project documentation and board-reference contribution. Close-up shows `Guition`, `V1.4`, `TF`, and a dotted `2026` marking. User initially transcribed the numeric marking as `2626`; photo reads `2026`. Meaning of that marking is unverified; do not assert manufacture date.

Visible connector silk: P3 has GND/IO35/IO22/IO21 labels; CN1 has GND/IO22/IO27/3.3V labels. These are photographed labels, NOT electrically verified pinout measurements. The photo shows an ESP-32S-labelled module, antenna connector, LED1, and TF-card socket. LCD controller is not visible or identified.

## Why this is a separate variant

Classic CYM v2.15.56 works on Jim's existing boards but on this sample he observed red/blue reversal, clipped/transposed UI, an unused screen strip, and inability to finish calibration. Those observations do not prove a different controller or a touch fault after successful calibration.

CYM v2.15.57 adds a separate experimental HackerBox CYD profile. Candidate: ILI9341 driver retained, BGR order, inversion off, axis swap off, both mirrors on, native 240x320 portrait. All panel settings remain hardware-unvalidated. Existing Classic mapping and restored GPS behavior are unchanged. Touch calibration uses a separate NVS namespace and derives axis swap/inversion from measured corner taps, not this photograph.

All seven profiles built; 313 host tests and sanitizer calibration tests passed. Physical display/calibration acceptance is pending. Test procedure: [HackerBox CYD test instructions](https://github.com/JimGat/CYM/blob/Jimgat_Dev/docs/hackerbox-cyd-test.md).

## Reference contribution summary

Proposed ValleyTech entry: Guition / ESP32 / ESP32 2432S028 / V1.4, distributed in HackerBox 0131 AMBERJACK. Include rear photograph and distinguish sample observations from established pinout/controller facts. Do not identify this as ST7789 or assert equivalence to JC2432W328 without exact-board documentation or hardware proof.

Source: https://hackerboxes.com/products/hackerbox-0131-amberjack
