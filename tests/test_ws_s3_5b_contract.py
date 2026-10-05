from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
# Host executables/logs remain task-local; a fresh checkout has no .hermes directory.
SCRATCH=ROOT/".hermes/ws-s3-5b"
SCRATCH.mkdir(parents=True, exist_ok=True)
class Waveshare5B(unittest.TestCase):
 def test_executed_viewport(self):
  with tempfile.TemporaryDirectory(dir=SCRATCH) as d:
   binary=Path(d)/"viewport"
   subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-fsanitize=address,undefined","-I"+str(ROOT/"ESP32C5/main"),str(ROOT/"tests/ws_s3_viewport_test.c"),"-o",str(binary)],check=True)
   subprocess.run([str(binary)],check=True)
 def test_executed_rtc_gate(self):
  with tempfile.TemporaryDirectory(dir=SCRATCH) as d:
   binary=Path(d)/"rtc"
   subprocess.run(["cc","-std=c11","-Wall","-Werror","-fsanitize=address,undefined","-I"+str(ROOT/"ESP32C5/components/cym_timekeeper/include"),str(ROOT/"tests/ws_s3_rtc_gate_test.c"),"-o",str(binary)],check=True)
   subprocess.run([str(binary)],check=True)
 def test_safe_profile(self):
  p=(ROOT/"ESP32C5/components/board_hal/include/boards/ws_s3_5b.h").read_text()
  for text in ["BOARD_LCD_PHYSICAL_WIDTH 1024","BOARD_LCD_PHYSICAL_HEIGHT 600","BOARD_UI_SCALE 2","BOARD_LCD_WIDTH 512","BOARD_LCD_HEIGHT 300","BOARD_BOOT_BTN_GPIO -1","BOARD_TIME_HAS_RTC 1","BOARD_TIME_HAS_GPS_UART 0","BOARD_HAS_GPS 0","BOARD_RTC_I2C_ADDR 0x51","BOARD_I2C_SDA 8","BOARD_I2C_SCL 9"]: self.assertIn(text,p)
 def test_canonical_transport(self):
  main=(ROOT/"ESP32C5/main/main.c").read_text();port=(ROOT/"ESP32S3/main/ws_s3_5b_port.c").read_text()
  self.assertIn("ws_s3_5b_flush",main);self.assertIn("ws_s3_5b_bus_init(s_i2c_bus)",main)
  for text in ["on_frame_buf_complete",".num_fbs = 2",".bounce_buffer_size_px","esp_cache_msync","cym_viewport_expand_rgb565","pending_boundary","xSemaphoreTake"]: self.assertIn(text,port)
  self.assertNotIn("on_color_trans_done",port);self.assertIn("cym_timekeeper_init(s_i2c_bus)",main)
 def test_expander_and_sd(self):
  port=(ROOT/"ESP32S3/main/ws_s3_5b_port.c").read_text()
  for text in ["0x24","0x38","outputs & ~mask"]: self.assertIn(text,port)
  sd=(ROOT/"ESP32C5/components/wifi_wardrive/wifi_wardrive.c").read_text()
  self.assertIn("host.do_transaction = ws_s3_sd_transaction",sd);self.assertIn("board_sd_set_selected(false)",sd)
 def test_beta_and_colour(self):
  config=(ROOT/"ESP32S3/sdkconfig.defaults.ws-s3-5b").read_text()
  for text in ["CONFIG_LV_COLOR_16_SWAP=n","CONFIG_SPIRAM_MODE_OCT=y","CONFIG_BOARD_WS_S3_5B=y"]:self.assertIn(text,config)
  self.assertIn("\"ws-s3-5b\": {",(ROOT/"ESP32C5/docs/index.html").read_text())
 def test_rtc_startup_gate(self):
  tk=(ROOT/"ESP32C5/components/cym_timekeeper/cym_timekeeper.c").read_text()
  self.assertIn("pcf85063_startup_epoch_valid",tk);self.assertIn("!os_flag",tk)

 def test_download_boot_offset(self):
  page=(ROOT/"ESP32C5/docs/index.html").read_text()
  self.assertIn('ui.dlBoot.querySelector("span").textContent = `Bootloader (${bd.bootOffset})`;',page)
