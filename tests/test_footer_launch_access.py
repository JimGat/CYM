from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class FooterAccess(unittest.TestCase):
 def test_five_release_trigger(self):
  s=(ROOT/'ESP32C5/components/cym_doom/doom_contracts.c').read_text()
  self.assertTrue('++t->count==5' in s)
 def test_sd_not_required_for_dialog(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text();a=s.index('static bool doom_prototype_idle(void)\n{');b=s.index('/* Engine resources',a)
  self.assertFalse('!sd_mounted_lazy' in s[a:b])
  self.assertTrue('lv_obj_set_size(ver_area, lv_pct(100), 36)' in s)
 def test_ws35_in_normal_selector(self):
  s=(ROOT/'ESP32C5/docs/index.html').read_text();a=s.index('const DEFAULT_BOARD_IDS');b=s.index(';',a)
  self.assertIn('"ws-c5-35"',s[a:b])

 def test_missing_sd_warning_before_allocations(self):
  s=(ROOT/'ESP32C5/components/cym_doom/doom_ui.c').read_text();a=s.index('static void continue_event');b=s.index('static void cancel_event',a);f=s[a:b]
  self.assertTrue('Missing WAD or SD not mounted' in f)
  self.assertLess(f.index('!sd_ready_gate'),f.index('heap_caps_calloc'))
  self.assertTrue('!idle_gate||!idle_gate()' in f)
