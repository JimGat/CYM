"""Regression contracts for the known-good Classic CYD display path."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "ESP32C5/main/main.c").read_text(encoding="utf-8")


def cyd_display_block() -> str:
    start = MAIN.index("#if defined(CONFIG_BOARD_CYD2USB)", MAIN.index("const esp_lcd_panel_dev_config_t panel_config"))
    end = MAIN.index("static void nvs_settings_load", start)
    return MAIN[start:end]


class Cyd2432s028DisplayContract(unittest.TestCase):
    def test_classic_uses_known_ili9341_driver_not_unsafe_unknown_to_st_fallback(self):
        block = cyd_display_block()
        self.assertIn("esp_lcd_new_panel_ili9341", block)
        self.assertNotIn("esp_lcd_panel_io_rx_param", block)
        self.assertNotIn("esp_lcd_new_panel_st7789", block.split("#else", 1)[0])
        self.assertNotIn("is_ili9341", block)

    def test_classic_preserves_physically_verified_non_inverted_color(self):
        block = cyd_display_block()
        self.assertIn("esp_lcd_panel_invert_color(panel_handle, false)", block)

    def test_classic_preserves_known_good_usb_bottom_portrait_transform(self):
        block = cyd_display_block()
        self.assertIn("esp_lcd_panel_swap_xy(panel_handle, true)", block)
        self.assertIn("esp_lcd_panel_mirror(panel_handle, true, true)", block)

    def test_classic_uses_rgb_element_order(self):
        init_start = MAIN.index("static void init_display(void)")
        init_end = MAIN.index("static void nvs_settings_load", init_start)
        init = MAIN[init_start:init_end]
        self.assertIn(".rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB", init)


if __name__ == "__main__":
    unittest.main()
