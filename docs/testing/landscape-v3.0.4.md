# v3.0.4 Development: Classic and HackerBox orientation

## Scope and evidence

Co-developer @birolt29 supplied Patch #10 against v3.0.3 / 76a8aa3d.
Input SHA-256: `0a515cfb00673e7d2188b5266bab2d2f6e1c3265e11a748dd20bc5e68ebe5b07`.
The immutable input extends ten orientation/calibration guards for Classic only.
It applies cleanly to that base. His Classic bench report covers all four angles,
touch, recalibration and heap observations during WiFi-scan churn. Those are his
reported results, not physical qualification of our exact integrated images.

The owner-authorized HackerBox extension widens those same guards to CYD2USB.
Installed LVGL rotates pixels before native flush and transforms native touch
coordinates centrally. Keep the existing HackerBox native panel swap=false,
mirror=(true,false), BGR, corner-derived calibration and `touch_hb` namespace;
keep Classic swap=true, mirror=(true,true), RGB. No second touch transform.
No driver, pin, UART, RF-HAT, partition, or general navigation refactor is included.
The dropdown/save/reboot and native-portrait calibration restore paths are enabled
for both profiles. Missing saved orientation defaults to 0; valid NVS survives.
Other profiles' rotation gates are unchanged.

`tests/test_cyd_landscape304.py` covers all ten gate selections across eight
profiles, extracted production orientation and calibration restore logic, installed
LVGL input rotation, unchanged native helpers/files, persistence/boot ordering,
and both menu routes. RED on base and GREEN on integrated source are recorded
outside the repo. These are host checks, not panel/heap hardware proof.

Landscape allocates a temporary LVGL rotation buffer. No universal RAM-headroom
claim is made. HackerBox was not tested by the contributor. Jim subsequently reported that both
v3.0.4 board builds check out, accepting Classic and HackerBox landscape. No new
heap measurements or explicit completion of every checklist item were reported.
Stable and the existing release are unchanged. No live Wiki publication is included.

## Operator checklist: run on BOTH boards and BOTH menu layouts

1. Use the matching Development v3.0.4 package: Classic `cyd-2432s028` or
   `hackerbox-cyd`. Do not interchange profiles. Preserve SD and NVS: use matching
   application-only update at `0x10000`, erase disabled, after checking partitions.
   Full images start at `0x0000` and may overwrite settings; do not erase-all.
2. With the normal physical orientation (USB bottom), check initial portrait:
   normal colors, non-reflected text, full-screen coverage and correct touch.
   Default remains 0 if no orientation was previously saved.
3. Classic layout: Settings → Screen. Modern: Tools → Settings → Screen.
   Expect Orientation options 0/90/180/270, Save/Cancel accessible.
4. Choose 90 → Save. Expect reboot, readable landscape with no wrapping/clipping.
   Touch all four corners and center; open tiles, a scrolling list, keyboard,
   GPS info and Screen settings. Cancel without saving must retain the setting.
5. Repeat for 270 and 180, then return to 0. Check power-cycle persistence at
   each angle and that ordinary portrait remains identical in color/mapping.
6. At BOTH landscape angles choose Recalibrate Touch. Expect native-portrait
   corner targets all visible; complete and confirm. Expect chosen landscape
   restored with aligned touches. Repeat but let corner acquisition time out:
   expect previous calibration retained and chosen orientation restored.
7. Repeat steps 3–6 in the other home layout. Check saved selection survives
   switching layouts, and Screen controls remain reachable without clipping.
8. Compare repeated WiFi scan/list churn in 0/90/270: record internal free heap,
   largest free block, minimum free heap and any allocation failures/reboots on
   the primary USB-C console only. No logs on GPS JST/second Micro-USB UART.
   Do not infer safety merely from the static linker memory report.
9. Spot-check existing GPS, discrete RGB/brightness and Go Dark recovery.
   Report board, version, orientation, layout, photo and serial evidence for any
   defect; do not adjust native panel transforms speculatively.

## No-PSRAM provisioning version boundary

v3.0.2 fixed the unsafe path by requiring registered total SPIRAM before automatic
Validate & Provision / Format + Provision. Without PSRAM it shows OK-only manual
setup guidance for CYM-SD-Assets. It did not implement automatic provisioning on
no-PSRAM boards. Development v3.0.5 implements that separate capability; see
[its qualification checklist](sd-no-psram-v3.0.5.md). The v3.0.4 acceptance above
does not qualify the new provisioning lifecycle.
