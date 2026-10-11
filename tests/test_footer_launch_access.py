from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class FooterAccess(unittest.TestCase):
 def test_five_release_trigger(self):
  s=(ROOT/'ESP32C5/components/cym_doom/doom_contracts.c').read_text()
  self.assertTrue('++t->count==5' in s)
 def test_sd_not_required_for_dialog(self):
  s=(ROOT/'ESP32C5/components/cym_doom/doom_ui.c').read_text();a=s.index('static void selector_dialog(void)\n{');b=s.index('static void license_dialog(void)\n{',a)
  self.assertNotIn('sd_ready_gate',s[a:b]);self.assertNotIn('heap_caps_calloc',s[a:b])
  self.assertIn('doom_ui_tile_click();',(ROOT/'ESP32C5/main/main.c').read_text())
 def test_ws35_in_normal_selector(self):
  s=(ROOT/'ESP32C5/docs/index.html').read_text();a=s.index('const DEFAULT_BOARD_IDS');b=s.index(';',a)
  self.assertIn('"ws-c5-35"',s[a:b])

 def test_missing_sd_warning_before_commit(self):
  s=(ROOT/'ESP32C5/components/cym_doom/doom_ui.c').read_text();a=s.index('static void continue_event');b=s.index('static void doom_card_event',a);f=s[a:b]
  self.assertIn('Missing WAD or SD not mounted',f)
  self.assertLess(f.index('!sd_ready_gate'),f.index('record_reboot()'))
  launch=s[s.index('static void launch_game(void){'):s.index('/* No game allocator')]
  self.assertLess(launch.index('!isolated'),launch.index('heap_caps_calloc'))
