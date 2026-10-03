from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class HackerBoxContract(unittest.TestCase):
    def test_profile_and_package_isolation(self):
        self.assertTrue((ROOT / 'ESP32/sdkconfig.defaults.hackerbox-cyd').exists())
        self.assertIn('binaries-hackerbox-cyd', (ROOT / 'ESP32/CMakeLists.txt').read_text())
    def test_display_candidate_is_explicit(self):
        s=(ROOT / 'ESP32C5/main/main.c').read_text()
        self.assertIn('CONFIG_BOARD_HACKERBOX_CYD',s)
        self.assertIn('LCD_RGB_ELEMENT_ORDER_BGR',s)
        self.assertIn('esp_lcd_panel_swap_xy(panel_handle, false)',s)
    def test_calibration_uses_dimensions(self):
        s=(ROOT / 'ESP32C5/main/main.c').read_text()
        self.assertIn('{LCD_H_RES - 1, LCD_V_RES - 1}',s)
        self.assertIn('touch_hb',s)

    def test_hackerbox_mirror_candidate(self):
        s=(ROOT / 'ESP32C5/main/main.c').read_text()
        self.assertTrue('esp_lcd_panel_mirror(panel_handle, true, false)' in s)
