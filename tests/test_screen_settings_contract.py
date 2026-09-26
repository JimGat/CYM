#!/usr/bin/env python3
"""Regression contract for resistive-only touch calibration UI."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "ESP32C5/main/main.c").read_text()


class ScreenSettingsContract(unittest.TestCase):
    def test_recalibration_callback_is_xpt2046_only(self):
        self.assertRegex(
            MAIN,
            re.compile(
                r"#if defined\(CONFIG_BOARD_TOUCH_XPT2046\)\s+"
                r"static void screen_popup_recal_cb\(lv_event_t \*e\).*?"
                r"#endif\s+",
                re.S,
            ),
        )

    def test_recalibration_controls_are_xpt2046_only_but_home_layout_is_global(self):
        self.assertRegex(
            MAIN,
            re.compile(
                r"#if defined\(CONFIG_BOARD_TOUCH_XPT2046\)\s+"
                r"/\* ── Recalibrate Touch section.*?"
                r"screen_popup_recal_cb.*?"
                r"#endif[^\n]*\n\s*"
                r"/\* Home Layout radio choices \*/",
                re.S,
            ),
        )

    def test_home_layout_radios_have_explicit_visible_text_color(self):
        for radio in ("screen_home_classic_radio", "screen_home_4cat_radio"):
            self.assertIn(
                f"lv_obj_set_style_text_color({radio}, lv_color_hex(0x3F51B5), 0);",
                MAIN,
            )

    def test_home_layout_has_one_settings_entry_but_keeps_first_boot_popup(self):
        self.assertNotIn('strcmp(tile_name, "Home Layout")', MAIN)
        self.assertNotIn('"Home\nLayout",', MAIN)
        self.assertIn("static void show_home_layout_popup(void)", MAIN)
        self.assertIn("if (show_home_layout_setup) show_home_layout_popup();", MAIN)


if __name__ == "__main__":
    unittest.main()
