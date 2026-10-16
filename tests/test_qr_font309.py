"""Actual production cmap/bitmap coverage; preserve all 92 prior glyphs bytewise."""
from pathlib import Path
import importlib.util,json,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fontgen',ROOT/'tools/generate_extra_symbols.py');fontgen=importlib.util.module_from_spec(spec);spec.loader.exec_module(fontgen)
class CameraGlyph(unittest.TestCase):
 def test_camera_and_every_existing_bitmap(self):
  actual=fontgen.glyphs((ROOT/'ESP32C5/main/lv_extra_symbols.c').read_text())
  baseline=json.loads((ROOT/'tests/extra_symbols_baseline.json').read_text());self.assertEqual(len(baseline),92)
  for cp,value in baseline.items():self.assertEqual(actual.get(cp),value,cp)
  self.assertIn(str(0xF030),actual,'camera absent from custom cmap/bitmap')
  self.assertEqual(len(actual),93)
 def test_both_tiles_use_the_camera_macro(self):
  t=(ROOT/'ESP32C5/main/main.c').read_text()
  self.assertIn('#define MY_SYMBOL_CAMERA',t)
  self.assertEqual(t.count('MY_SYMBOL_CAMERA, "QR\\nDecoder"'),2)
if __name__=='__main__':unittest.main()
