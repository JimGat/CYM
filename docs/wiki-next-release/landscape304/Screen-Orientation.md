# Screen Orientation (Landscape Mode)

> STAGED DEVELOPMENT UPDATE — not published to the live Wiki. Stable remains unchanged.

NM-CYD-C5 and WS-C5-28/35 retain their existing orientation support. Development v3.0.4 adds **Classic CYD** via Patch #10 from co-developer [@birolt29](https://github.com/birolt29), plus a narrow **HackerBox-CYD owner-test candidate**. The contributor reports render, touch, recalibration and WiFi-scan heap checks on Classic at all four angles. He deliberately excluded HackerBox because he lacks its hardware. Neither that report nor host/build tests qualify our exact integrated builds or HackerBox; owner acceptance is pending.

HackerBox retains its existing panel reflection, BGR color order, native touch solver and separate calibration storage. LVGL software rotation sits above those native mappings; no second touch rotation or panel transform change is added. Landscape uses a temporary LVGL rotation buffer, so measure heap under real workload rather than assuming universal headroom.

Use the Development branch `docs/testing/landscape-v3.0.4.md` checklist on both boards, both layouts and all four angles. The historical screenshot gallery below illustrates the existing shared layouts, not newly measured HackerBox results.

---

## How to enable it

1. Classic layout: **Settings → Screen**. Modern layout: **Tools → Settings → Screen**.
2. Under **Orientation**, pick one of:
   - `0 Portrait` (default)
   - `90 Landscape`
   - `180 Portrait flipped`
   - `270 Landscape flipped`
3. Tap **Save**.

The device saves the setting and reboots so screens are recreated using the new logical dimensions. Check representative lists, keyboards and overlays on the actual board; reboot alone is not a guarantee that every layout has been physically qualified.

The setting is saved to NVS and persists across reboots and firmware updates.

> On NM-CYD-C5, Classic CYD and HackerBox-CYD, resistive touch calibration forces native portrait and restores the chosen orientation on completion or timeout. The stored calibration remains native. Capacitive WS-C5-28/35 touch needs no such calibration.

---

## Main Menu

![Main Menu — landscape and portrait](images/Main_Menu_Landscape_and_Portrait.jpg)

The home/menu background now scales to fill the entire screen in landscape instead of leaving empty strips on the sides.

## Screen Settings

![Screen Settings — landscape and portrait](images/Screen_Settings_Landscape_and_Portrait.jpg)

The Orientation selector lives in Settings → Screen, alongside Timeout, Brightness, and Recalibrate Touch. In landscape the dialog switches to a two-column layout so all four sections fit without scrolling.

---

## Redesigned screens

A representative sample of the screens that got dedicated landscape layouts (portrait → landscape):

| Screen | Notes |
|---|---|
| Universal Remote | Button grid reflowed for the wider aspect ratio |
| LED Remote | 28 buttons reflowed to fit landscape without scrolling |
| Bluetooth Lookout | List and controls repositioned |
| Evil Portal | The **Start Portal** button, previously clipped off-screen in landscape, is now fully visible |
| Timing Settings | **Cancel**/**Save** buttons, previously unreachable in landscape, are now on-screen |
| Chameleon Ultra | Device list and detail view rebuilt for landscape |
| GPS Info | Coordinate/status layout rebuilt for landscape |

![Universal Remote — before/after](images/Universal_Remote_P_.jpg) ![Universal Remote — landscape](images/Universal_Remote_L_.jpg)

![LED Remote — portrait](images/LED_Remote_P.jpg) ![LED Remote — landscape, 28 buttons reflowed](images/LED_Remote_L_28Buttons_Reflowed.jpg)

![Bluetooth Lookout — portrait](images/Bluetooth_Lookout_P.jpg) ![Bluetooth Lookout — landscape](images/Bluetooth_Lookout_L.jpg)

![Evil Portal — portrait, Start Portal clipped](images/Evil_Portal_P.jpg) ![Evil Portal — landscape, Start Portal visible](images/Evil_Portal_L.jpg)

![Timing Settings — portrait](images/Timing_Settings_P.jpg) ![Timing Settings — landscape, Cancel/Save reachable](images/Timing_Settings_L.jpg)

![Chameleon Ultra — landscape](images/Chameleon_Ultra_L_.jpg)

![GPS Info — landscape](images/GPS_Info_L.jpg)

Portrait behavior across the whole firmware is unchanged — landscape support was added as additional branches alongside the existing portrait code, not a replacement for it.

---

## WiFi Scan & Attack list redesign

Independent of orientation, the WiFi Scan & Attack list was reworked into a wardrive-style row layout: a fixed band badge (2.4/5 GHz), the SSID flexing to fill available width, and Channel/RSSI/Auth held tight on the right. The Auth column is color-coded by how deauth-able the target is:

- **Red** — WPA3/OWE (Management Frame Protection active, deauth ignored)
- **Amber** — WPA2
- **Green** — Open/WEP/WPA (no MFP)

Multi-select checkboxes let you queue several targets at once. This layout is used in both portrait and landscape.

---

## Also in this release

Alongside the orientation work, this patch (v2.15.00) fixed several standing bugs found during the screen-by-screen landscape testing pass: a MITM active-capture crash from a missing screen teardown hook, PN532 Clone/Write/Emulate crashes from main-task stack exhaustion, and two Chameleon Ultra BLE reconnect bugs (a benign disconnect was incorrectly deleting a valid bond, and a bond-reuse reconnect could hang forever waiting for an encryption event that never fires). See the [release notes](https://github.com/JimGat/CYM/releases) for the full list.

---

*The original orientation implementation and screen gallery were developed and tested by co-developer [@birolt29](https://github.com/birolt29). See [Contributors](Contributors) for the full list of people who've helped build CYM.*
