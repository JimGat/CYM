# HackerBox CYD — Guition V1.4

Hardware supplied in HackerBox #0131 AMBERJACK, identified by Jim Gatwood. HackerBoxes lists the included platform as ESP32-2432S028R. User reports board marking `ESP32 2432S028` (space, not hyphen), two USB connectors, and Guition branding.

## Photographic evidence

![Guition CYD rear detail, photographed by Jim Gatwood](https://raw.githubusercontent.com/JimGat/CYM/Jimgat_Dev/docs/assets/hackerbox-cyd/guition-v1.4-back.jpg)

Original photograph: Jim Gatwood; supplied for project documentation and board-reference contribution. Board markings are `Guition`, `V1.4`, `TF`, and `2626`, confirmed by Jim inspecting the physical board. An earlier photographic reading of `2026` was incorrect. The meaning of `2626` is unverified; do not assert a manufacture date.

Visible connector silk: P3 has GND/IO35/IO22/IO21 labels; CN1 has GND/IO22/IO27/3.3V labels. These are photographed labels, NOT electrically verified pinout measurements. The photo shows an ESP-32S-labelled module, antenna connector, LED1, and TF-card socket. LCD controller is not visible or identified.

## Why this is a separate variant

Classic CYM v2.15.56 works on Jim's existing boards but on this sample he observed red/blue reversal, clipped/transposed UI, an unused screen strip, and inability to finish calibration. Those observations do not prove a different controller or a touch fault after successful calibration.

CYM v2.15.57 adds a separate experimental HackerBox CYD profile. Candidate: ILI9341 driver retained, BGR order, inversion off, axis swap off, both mirrors on, native 240x320 portrait. All panel settings remain hardware-unvalidated. Existing Classic mapping and restored GPS behavior are unchanged. Touch calibration uses a separate NVS namespace and derives axis swap/inversion from measured corner taps, not this photograph.

All seven profiles built; 313 host tests and sanitizer calibration tests passed. Physical display/calibration acceptance is pending. Test procedure: [HackerBox CYD test instructions](https://github.com/JimGat/CYM/blob/Jimgat_Dev/docs/hackerbox-cyd-test.md).

## Reference contribution summary

Proposed ValleyTech entry: Guition / ESP32 / ESP32 2432S028 / V1.4, distributed in HackerBox 0131 AMBERJACK. Include rear photograph and distinguish sample observations from established pinout/controller facts. Do not identify this as ST7789 or assert equivalence to JC2432W328 without exact-board documentation or hardware proof.

Source: https://hackerboxes.com/products/hackerbox-0131-amberjack

## Silicon identification

Jim reports ESPConnect identified this sample as `ESP32-D0WD-V3 (revision 3)`. This is a user-provided tool readout, not independently captured here. Silicon revision 3 and PCB V1.4 are separate identifiers. This readout does not identify the LCD controller, flash capacity, or PSRAM.

## Additional physical report

Jim reports ESPConnect flash ID `0x1660C4`, flash manufacturer `0xC4`, 4MB flash, and no PSRAM detected. Preserve these as reported readouts without inferring a vendor name. v2.15.57 physical test: rotation and colors look correct, remaining orientation/mirror issue. v2.15.58 candidate changes only HackerBox X mirror, from ON/ON to OFF/ON; physical confirmation pending.

## v2.15.59 physical display feedback

Jim reports the display looks good on v2.15.59. Slight raster/ghosting was initially observed, but after an extended complete power-off he reports it looks OK. Keep the existing 40MHz LCD SPI clock and initialization unchanged; no timing/VCOM fix is established or required from this observation. Recommend complete power removal for about 10 seconds after panel-setting changes. This is a reported recovery, not proof of its mechanism. Touch calibration completion/persistence remain unconfirmed.

## Touch calibration acceptance

Jim confirms calibration/alignment completed successfully and touch is good on v2.15.59. Display mapping and calibrated touch alignment are physically accepted for this sample. Calibration persistence across reboot and other peripherals remain unconfirmed; do not imply full-board qualification.
