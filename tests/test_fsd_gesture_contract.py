"""Structural protections complement the real-LVGL runtime runner; no hardware claims."""
from pathlib import Path
import re,unittest,subprocess,tempfile,os
R=Path(__file__).resolve().parents[1]
class GestureContract(unittest.TestCase):
 def test_idle_has_no_tree_or_timer_work(self):
  s=(R/'ESP32C5/main/fsd_ui.inc').read_text();body=s[s.index('bool cym_fsd_touch_inject'):s.index('static void fsd_inj_reset')]
  self.assertIn('if(!s_fsd_inj_req||s_fsd_inj_pos>=s_fsd_inj_len)return false;',body)
  for forbidden in ['vTaskDelay','sleep(', 'lv_timer_create','fsd_walk','fsd_has_overlay','while(']:self.assertNotIn(forbidden,body)
 def test_physical_and_lock_order(self):
  s=(R/'ESP32C5/main/main.c').read_text();s=s[s.index('void lvgl_touch_read_cb('):s.index('// Screenshot utilities')]
  call=s.index('if (cym_fsd_touch_inject(data,')
  self.assertLess(s.index('xpt2046_read_touch'),call)
  for guard in ['screen_dimmed || ignore_touch_until_release || ui_locked','now_ms < g_radio_settle_until_ms, touched','touch_x_flag = data->point.x','last_input_ms = now_ms']:self.assertIn(guard,s)
 def test_epoch_on_page_and_rotation_not_overlay_scans(self):
  s=(R/'ESP32C5/main/main.c').read_text()
  self.assertIn('run_screen_stop_fn(void) {\n    cym_fsd_input_epoch();',s)
  self.assertIn('cym_fsd_input_epoch(); // orientation ownership boundary',s)
  ui=(R/'ESP32C5/main/fsd_ui.inc').read_text();self.assertIn('lv_indev_reset(s_fsd_inj_indev,NULL)',ui);self.assertIn('LV_EVENT_PRESS_LOST',ui)
 def test_disabled_has_no_state_or_calls(self):
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as d:
   d=Path(d);(d/'sdkconfig.h').write_text('#define CONFIG_ESP_CONSOLE_NONE 1\n');(d/'x.c').write_text('#include <stdbool.h>\n#include "fsd.h"\nvoid f(void){cym_fsd_input_epoch();cym_fsd_poll();(void)cym_fsd_touch_inject(0,1,1);}')
   subprocess.run(['cc','-O2','-I'+str(d),'-I'+str(R/'ESP32C5/main'),'-c',str(d/'x.c'),'-o',str(d/'x.o')],check=True)
   syms=subprocess.check_output(['nm',str(d/'x.o')],text=True);self.assertNotIn('cym_fsd',syms)
 def test_observer_scope_and_teardown(self):
  s=(R/'ESP32C5/main/main.c').read_text();start=s.index('static void show_bt_observer_screen(void)\n{');body=s[start:s.index('ui_locked = false;',start)]
  self.assertIn('lv_spinner_create(function_page, 1000, 60)',body);self.assertIn('lv_obj_set_size(bto_spinner, 18, 18)',body);self.assertIn('g_screen_stop_fn = bto_stop',body)
  rebuild=s[s.index('static void bto_rebuild_list(void)\n{'):s.index('static void bto_refresh_cb(lv_timer_t *t)\n{')];self.assertIn('lv_obj_clean(bto_list);',rebuild);self.assertNotIn('lv_obj_clean(function_page)',rebuild)
if __name__=='__main__':unittest.main()
