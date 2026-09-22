# CYM-NM28C5 — new screens must support landscape (2026-09-22+)

As of 2026-09-22, **every new screen** added to the firmware must work correctly in
both portrait and landscape on boards that support [Screen Orientation](../../ESP32C5/main/main.c)
(currently NM-CYD-C5 and WS-C5-28) — not portrait-only with landscape as a follow-up patch.
This applies going forward to all new screens, not just ones that look form-heavy.

## The two failure patterns already hit (know these before writing a new screen)

1. **Fixed-height, non-scrollable content that only fits by accident.** The GPS Info
   screen and the "Set Fallback Position" popup both shipped with hardcoded, un-scaled
   spacing that fit portrait's 320px height with room to spare, but overflowed landscape's
   240px height — in the popup's case, badly enough that the Save/Cancel buttons rendered
   off the physical display entirely. Both bugs passed a full portrait test cycle and were
   only caught by a user running landscape mode on hardware (2026-09-22 field reports).
2. **Static content that assumes portrait's aspect ratio** (e.g. a card sized `LV_SIZE_CONTENT`
   with a fixed set of stacked rows, given no way to reclaim space or scroll if it runs long).

## The fix, and the pattern to build NEW screens with from the start

**List/scroll-based screens** (a device list, a category list, a log — most screens in this
codebase) are the easy case and need no special-casing if built the way ESP-NOW Scout,
Passive Log, and the OT Survey results screens (`show_ot_results_summary_from_loaded`,
`show_ot_results_drill_screen`, `show_ot_results_browser_screen`) already are:

- Container width: `lv_pct(100)`, never a hardcoded pixel width tied to one orientation.
- Container height: `lv_disp_get_ver_res(NULL) - <fixed title-bar offset, typically 34>`,
  never `LCD_V_RES` or a bare portrait-derived number.
- Leave the list container's default scrollability ON (don't
  `lv_obj_clear_flag(list, LV_OBJ_FLAG_SCROLLABLE)`), and set
  `lv_obj_set_scrollbar_mode(list, LV_SCROLLBAR_MODE_AUTO)`. Individual row/card children
  inside it can be `LV_SIZE_CONTENT` height and don't need scrolling of their own — the
  list scrolls, so content that runs long in a narrower orientation just makes the list
  taller, never invisible/clipped.
- Row text: `LV_LABEL_LONG_CLIP` for single-line MAC/label rows (matches existing list
  screens), `LV_LABEL_LONG_WRAP` + `lv_obj_set_width(label, lv_pct(100))` for anything that
  might run long (site names, notable-device summaries). Never a hardcoded label width
  tuned to one orientation's available space.

Built this way, a list screen needs **no `landscape` branch at all** — it already reflows
correctly in both orientations because nothing in it assumes a fixed aspect ratio, and the
scrollable container is the safety net against `LV_SIZE_CONTENT` under/over-estimating.

**Fixed-layout / form-style screens** (a popup with several label+field rows and action
buttons, a settings dialog) are the hard case and DO need an explicit `landscape` branch —
follow the pattern in `gps_show_edit_overlay()` and `show_screen_popup()`:

```c
int hor = lv_disp_get_hor_res(NULL);
int ver = lv_disp_get_ver_res(NULL);
bool landscape = hor > ver;
```

- Give the outer card/dialog an explicit bounded height in landscape (not `LV_SIZE_CONTENT`
  left to overflow) AND enable vertical scrolling on it as a safety net — do both, don't
  rely on tightened spacing alone to guarantee a fit. `gps_show_edit_overlay()`'s landscape
  branch is the reference: bounded height + `lv_obj_set_scroll_dir(card, LV_DIR_VER)` +
  `lv_obj_set_scrollbar_mode(card, LV_SCROLLBAR_MODE_AUTO)`, plus a side-by-side two-column
  layout for paired fields (Lat/Lon) to cut vertical stacking before scrolling is even needed.
- Recompute the actual content height for landscape's shorter screen before picking spacing
  constants — don't just carry over portrait's numbers and hope. Show the arithmetic in a
  comment (see the GPS Info card's landscape comment) so the next person doesn't have to
  re-derive it from scratch when the screen grows a new field.

## Consistency

New screens should default to the **list-screen pattern** whenever the content is
naturally a list (which is most of this codebase — device lists, log views, category
breakdowns). Only reach for the fixed-layout/form pattern when the screen is genuinely a
form (text entry, several distinct settings) — and even then, prefer wrapping the whole
form in a scrollable container over hand-tuning fixed heights per orientation.

Portrait-only testing is not sufficient sign-off for a new screen on NM-CYD-C5 or WS-C5-28.
If landscape can't be hand-tested before shipping, at minimum verify the height math on
paper (interior height vs. worst-case content height) the way the GPS Info fix's commit
message does, and say so explicitly when handing the build off for testing.
