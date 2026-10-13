import pathlib, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class DiagnosticTests(unittest.TestCase):
 def test_pcm_and_sequence(self):
  self.assertTrue((ROOT/'main/diag_core.c').exists(), 'bounded PCM and policy implementation missing')
  with tempfile.TemporaryDirectory(dir='/home/dev/ws-c5-35-fixes/ws28-audio-diag') as d:
   exe=pathlib.Path(d)/'host'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'main'),str(ROOT/'tests/host.c'),str(ROOT/'main/diag_core.c'),'-lm','-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
 def test_project_contract(self):
  for f in ['CMakeLists.txt','main/CMakeLists.txt','main/WS28AudioDiag.c','sdkconfig.defaults','partitions.csv','build.sh']:
   self.assertTrue((ROOT/f).exists(), f+' missing')
  cfg=(ROOT/'sdkconfig.defaults').read_text()
  for s in ['CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y','CONFIG_ESP_CONSOLE_SECONDARY_NONE=y','CONFIG_ESPTOOLPY_FLASHSIZE_32MB=y']: self.assertIn(s,cfg)
  parts=(ROOT/'partitions.csv').read_text()
  for line in ['nvs,data,nvs,0x9000,0x6000','phy_init,data,phy,0xf000,0x1000','factory,app,factory,0x10000,0x700000','storage,data,fat,0x710000,0xf0000']: self.assertIn(line,parts)
  cm=(ROOT/'main/CMakeLists.txt').read_text()
  for comp in ['esp_driver_i2c','esp_driver_i2s','esp_driver_gpio','esp_timer','freertos','esp_codec_dev']: self.assertIn(comp,cm)
  src=(ROOT/'main/WS28AudioDiag.c').read_text()
  for bad in ['nvs_flash_init','vTaskDelete','esp_wifi_init','lvgl','doom_audio']: self.assertNotIn(bad,src)
if __name__=='__main__': unittest.main(verbosity=2)
