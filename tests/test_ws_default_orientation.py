from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class Defaults(unittest.TestCase):
 def test_ws_boards_default_270(self):
  for name in ('ws_c5_28','ws_c5_35'):
   self.assertIn('#define BOARD_DEFAULT_ORIENTATION 3',(ROOT/('ESP32C5/components/board_hal/include/boards/'+name+'.h')).read_text())
 def test_nvs_overrides_board_default(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text()
  self.assertIn('static uint8_t screen_orientation = BOARD_DEFAULT_ORIENTATION;',s)
  self.assertIn('nvs_get_u8(h, NVS_KEY_ORIENT, &orient) == ESP_OK && orient <= 3',s)
