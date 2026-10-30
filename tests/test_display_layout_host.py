"""Focused installed-LVGL gate; mocks only SDK, radio and unrelated route endpoints."""
from pathlib import Path
import os,subprocess,unittest,re
R=Path(__file__).resolve().parents[1]
class DisplayLayout(unittest.TestCase):
 def test_production_lvgl(self):
  subprocess.run(['python3','-B',str(R/'tests/run_display_layout_host.py')],cwd=R,check=True)
 def test_classic_modern_routes(self):
  s=(R/'ESP32C5/main/main.c').read_text()
  self.assertRegex(s,r'create_tile\(tiles_container, LV_SYMBOL_WIFI,\s*"WiFi"[^;]*"WiFi Menu"')
  self.assertRegex(s,r'create_tile\(tiles_container, MY_SYMBOL_CLOCK,\s*"Clock"[^;]*"Clock Classic"')
  self.assertRegex(s,r'create_tile\(tiles, MY_SYMBOL_CLOCK,\s*"Clock"[^;]*"Clock Modern"')
  self.assertIn('show_wifi_scan_attack_screen();',s)
  self.assertIn('show_cc1101_hw_test_screen();',s)
if __name__=='__main__':unittest.main()
