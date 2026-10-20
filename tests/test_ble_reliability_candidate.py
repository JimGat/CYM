"""Boundary contracts; actual executable regressions are separate host runners."""
from pathlib import Path
import re,unittest
R=Path(__file__).resolve().parents[1]
class BleReliabilityCandidate(unittest.TestCase):
 def test_stage_boundaries(self):
  s=(R/'ESP32C5/main/main.c').read_text();h=(R/'ESP32C5/main/ble_stage_diag.h').read_text()
  names=re.findall(r'\bBT_ST_[A-Z_]+',h[h.index('typedef enum'):h.index('} bt_stage_t;')])
  for name in names:
   if name!='BT_ST_END':self.assertIn('bt_stage('+name,s,name)
  self.assertIn('BT_STAGE_ENABLED()',h);self.assertIn('bt_stage_valid',h)
  for forbidden in ['malloc(', 'nvs_', 'fopen(', 'xTaskCreate', 'vTaskDelete']:self.assertNotIn(forbidden,h)
 def test_clock_before_transition(self):
  s=(R/'ESP32C5/main/main.c').read_text()
  for n in ['ensure_wifi_mode','ensure_ble_mode']:
   self.assertRegex(s,r'static bool '+n+r'\(void\)\s*\{\s*if \(!clock_radio_admit\(\)\) return false;\s*if \(!bt_transition_enter\(\)\) return false;')
 def test_target_tick_matrix(self):
  builds=['ESP32C5/build_'+n for n in ['nm-cyd-c5','ws-c5-28','ws-c5-35','pancake-c5']]+['ESP32/build_cyd2usb','ESP32/build_hackerbox-cyd','ESP32S3/build_hosyond-s3-35','ESP32S3/build_ws-s3-5b']
  for name in builds:
   p=R/name/'config/sdkconfig.h';m=re.search(r'#define CONFIG_FREERTOS_HZ (\d+)',p.read_text());self.assertIsNotNone(m);self.assertIn(int(m.group(1)),[100,1000],str(p))
 def test_numeric_stage_map(self):
  h=(R/'ESP32C5/main/ble_stage_diag.h').read_text();names=re.findall(r'\bBT_ST_[A-Z_]+',h[h.index('typedef enum'):h.index('} bt_stage_t;')]);self.assertEqual(names.index('BT_ST_UI_RETURN')+1,27);self.assertEqual(names.index('BT_ST_GAP_START')+1,19)
