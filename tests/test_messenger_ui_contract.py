#!/usr/bin/env python3
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
class MessengerUI(unittest.TestCase):
 def test_routes_and_lifecycle(self):
  s=(R/'ESP32C5/main/main.c').read_text()
  self.assertEqual(s.count('"Messenger", UI_ACCENT_CYAN, main_tile_event_cb, "Messenger"'),2)
  self.assertIn('strcmp(tile_name, "Messenger")',s)
  p=R/'ESP32C5/main/cym_messenger_ui.inc';self.assertTrue(p.exists())
  u=p.read_text();self.assertIn('g_screen_stop_fn = messenger_screen_stop;',u)
  for v in ['lv_keyboard_create','lv_textarea_create','160 bytes','Not implemented','g_rf_hat_enabled','lv_label_set_recolor','cym_messenger_send','cym_messenger_stop']:
   self.assertIn(v,u)
  self.assertNotIn('vTaskDelay',u);self.assertNotIn('esp_now_',u)
if __name__=='__main__':unittest.main(verbosity=2)
