#!/usr/bin/env python3
from pathlib import Path
import re, unittest
ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/"ESP32C5/main/main.c").read_text()
HAL=(ROOT/"ESP32C5/components/board_hal/include/board_hal.h").read_text()
WS28=(ROOT/"ESP32C5/components/board_hal/include/boards/ws_c5_28.h").read_text()
def fn(sig):
 match=re.search(re.escape(sig)+r"\s*\{",MAIN)
 if not match: raise AssertionError(sig)
 start=match.start(); brace=MAIN.index("{",match.start()); depth=0
 for pos in range(brace,len(MAIN)):
  if MAIN[pos]=="{": depth+=1
  elif MAIN[pos]=="}":
   depth-=1
   if depth==0:return MAIN[start:pos+1]
 raise AssertionError(sig)
class Camera(unittest.TestCase):
 def test_lvgl_gesture_latch(self):
  cb=fn("static void cam_row_tap_cb(lv_event_t *e)")
  for x in ("LV_EVENT_PRESSED","LV_EVENT_PRESS_LOST","LV_EVENT_CLICKED","s_cam_gesture_active = true","s_cam_gesture_active = false"):self.assertIn(x,cb)
  self.assertIn("LV_EVENT_ALL",fn("static void cam_render_list(void)"))
 def test_entire_rebuild_deferred_and_rssi_live(self):
  t=fn("static void cam_ui_timer_cb(lv_timer_t *t)")
  self.assertIn("rebuild_allowed = !s_cam_gesture_active",t);self.assertNotIn("touch_pressed_flag",t)
  g=re.search(r"if \(cam_changed && rebuild_allowed\)\s*\{(.*?)cam_render_list\(\);\s*\}",t,re.S)
  self.assertIsNotNone(g);self.assertIn("memcpy(s_cam_snap",g.group(1));self.assertIn("cam_refresh_rssi_labels();",t)
 def test_reentry_teardown(self):
  for body in (fn("static void hidden_camera_stop(void)"),fn("static void show_hidden_camera_screen(void)")):self.assertIn("s_cam_gesture_active = false",body)
  self.assertIn("cam_clear_row_refs();",fn("static void hidden_camera_stop(void)"))
class Battery(unittest.TestCase):
 def test_lvgl_mutex_ownership(self):
  g=MAIN[MAIN.index("static lv_obj_t *battery_label"):MAIN.index("static uint8_t bt_tracking_mac")]
  self.assertNotRegex(g,r"volatile\s+bool\s+batt_")
  m=fn("static void battery_monitor_task(void *arg)");read=m.index("read_battery_voltage()",m.index("for (;;)"));lock=m.index("xSemaphoreTake(lvgl_mutex",read)
  self.assertLess(read,lock);pub=m[lock:m.index("xSemaphoreGive(lvgl_mutex)",lock)]
  for x in ("last_batt_color","batt_color_valid","batt_is_critical","last_voltage_str"):self.assertIn(x,pub)
 def test_timer_retry_and_label_lifecycle(self):
  self.assertIn("BATTERY_TIMER_INIT_RETRIES",MAIN);self.assertIn("battery_ensure_blink_timer_locked",fn("static void battery_monitor_task(void *arg)"));self.assertIn("battery_label_delete_cb",MAIN)
  self.assertGreaterEqual(MAIN.count("lv_obj_add_event_cb(battery_label, battery_label_delete_cb, LV_EVENT_DELETE"),2)
  t=fn("static void battery_blink_timer_cb(lv_timer_t *t)");self.assertIn("battery_label == NULL",t);self.assertNotIn("batt_is_charging",t)
 def test_voltage_estimate_not_charger_state(self):
  self.assertIn("BATTERY_VOLTAGE_FULL",MAIN);self.assertNotIn("batt_is_charging",MAIN);self.assertNotIn("BATTERY_COLOR_CHARGE",MAIN);self.assertIn("voltage estimate",MAIN.lower())
class Hardware(unittest.TestCase):
 def test_ws28_opt_in(self):
  self.assertIn("BOARD_BATTERY_VIA_EXPANDER",HAL)
  for x in ("#define BOARD_HAS_BATTERY_ADC       1","#define BOARD_BATTERY_VIA_EXPANDER  1","#define BOARD_BATTERY_DIVIDER_NUM   3","#define BOARD_BATTERY_DIVIDER_DEN   1","#define BOARD_BATTERY_CAL_SCALE     1.0f","EXIO_ADC"):self.assertIn(x,WS28)
 def test_read_error_and_range(self):
  r=fn("static float read_battery_voltage(void)")
  for x in ("custom_io_expander_get_adc","adc_raw > 1023","BOARD_BATTERY_CAL_SCALE","BOARD_BATTERY_DIVIDER_DEN","Battery ADC read failed"):self.assertIn(x,r)
 def test_ws35_unsupported(self):
  s=(ROOT/"ESP32C5/components/board_hal/include/boards/ws_c5_35.h").read_text();self.assertRegex(s,r"#define\s+BOARD_HAS_BATTERY_ADC\s+0\b");self.assertNotIn("BOARD_BATTERY_VIA_EXPANDER",s)
class Layout(unittest.TestCase):
 def test_both_header_paths(self):
  h=fn("static void create_home_ui(void)");p=fn("static void create_function_page_base(const char *name)")
  for b in (h,p):self.assertIn("battery_label_delete_cb",b);self.assertIn("LV_ALIGN_RIGHT_MID",b)
  self.assertIn("hb_hor - 112",h);self.assertIn("ptb_hor - 68 - 112",p);self.assertIn("LV_ALIGN_RIGHT_MID, -60",p)
if __name__=="__main__":unittest.main()
