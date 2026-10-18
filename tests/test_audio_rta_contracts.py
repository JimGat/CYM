import pathlib,unittest,re
R=pathlib.Path(__file__).resolve().parents[1];D=R/"ESP32C5/main"
class Contracts(unittest.TestCase):
 def test_separate_modules(self):
  for n in ["audio_rta.c","audio_rta.h","audio_rta_board.c","audio_rta_board.h","audio_rta_ui.inc"]:self.assertTrue((D/n).is_file(),n)
 def test_gate_and_menu_routes(self):
  s=(D/"main.c").read_text();self.assertGreaterEqual(s.count('"Audio RTA"'),4)
  self.assertIn('BOARD_HAS_AUDIO_RTA',(R/"ESP32C5/components/board_hal/include/board_hal.h").read_text())
  b=(R/"ESP32C5/components/board_hal/include/boards/ws_c5_35.h").read_text();self.assertIn('#define BOARD_HAS_AUDIO_RTA 1',b);self.assertIn('#define BOARD_HAS_AUDIO      0',b)
 def test_ui_stop_parent_and_no_global_poll(self):
  s=(D/"audio_rta_ui.inc").read_text();self.assertRegex(s,r'create_function_page_base\("Audio RTA"\);\s*g_screen_stop_fn = audio_rta_ui_stop;')
  self.assertIn('g_home_layout_4cat ? show_cat_tools : show_main_tiles',s)
  self.assertIn('lv_timer_del',s);self.assertIn('LV_DIR_VER',s);self.assertNotIn('nvs_',s)
 def test_no_worker_lvgl_or_external_ram_stack(self):
  s=(D/"audio_rta.c").read_text();self.assertNotIn('lv_',s);self.assertNotIn('vTaskDeleteWithCaps',s);self.assertIn('MALLOC_CAP_SPIRAM',s)
  self.assertIn('vTaskDelete(NULL)',s)
 def test_adapter_never_owns_shared_bus_power(self):
  s=(D/"audio_rta_board.c").read_text()
  for x in ['i2c_new_master_bus','i2c_del_master_bus','EXIO','gpio_set_level','portMAX_DELAY']:self.assertNotIn(x,s)
  self.assertIn('48000',s);self.assertIn('i2s_new_channel',s)
if __name__=='__main__':unittest.main()
