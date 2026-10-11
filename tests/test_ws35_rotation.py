from pathlib import Path
import unittest,re
ROOT=Path(__file__).resolve().parents[1]
class WS35Rotation(unittest.TestCase):
 def test_rotation_gates_include_ws35(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text()
  gates=re.findall(r'#if defined\(CONFIG_BOARD_NM_CYD_C5\) \|\| defined\(CONFIG_BOARD_WS_C5_28\)[^\n]*',s)
  self.assertEqual(len(gates),7)
  for g in gates:self.assertIn('CONFIG_BOARD_WS_C5_35',g)
 def test_missing_sd_precedes_idle_refusal(self):
  s=(ROOT/'ESP32C5/components/cym_doom/doom_ui.c').read_text();s=s[s.index('static void continue_event('):s.index('static void cancel_event(')]
  self.assertLess(s.index('!sd_ready_gate'),s.index('!idle_gate'))
  self.assertIn('Launch refused',s)
