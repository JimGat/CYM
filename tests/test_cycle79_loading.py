from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class Loading(unittest.TestCase):
 def test_worker_progress_and_bounded_hash_yield(self):
  s=(ROOT/'ESP32C5/components/cym_doom/doom_ui.c').read_text()
  self.assertIn('HASH_BEGIN',s);self.assertIn('STRUCTURE_BEGIN',s);self.assertIn('INIT_BEGIN',s)
  self.assertIn('__atomic_store_n(&hash_bytes',s)
  self.assertNotIn('off+=n;vTaskDelay(1)',s)
 def test_engine_metrics_timer_dependency(self):
  s=(ROOT/'ESP32C5/components/cym_doom/CMakeLists.txt').read_text()
  self.assertIn('target_link_libraries(cym_doom_engine PRIVATE idf::heap idf::esp_timer',s)
 def test_secondary_result_rows_shared_main_owner(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text()
  self.assertIn('gw_metadata_rows(scrl,r,ui_text_color())',s)
if __name__=='__main__':unittest.main(verbosity=2)
