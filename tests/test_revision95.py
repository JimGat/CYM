"""Narrow v95 board defaults and external GPS console isolation contracts."""
from pathlib import Path
import subprocess, unittest
ROOT=Path(__file__).resolve().parents[1]
class Revision95(unittest.TestCase):
 def test_ws35_compiled_gps_route_and_capability(self):
  h=ROOT/'ESP32C5/components/board_hal/include/boards/ws_c5_35.h'
  code='#include "'+str(h)+'"\n_Static_assert(BOARD_HAS_GPS==1 && BOARD_TIME_HAS_GPS_UART==1,"capability");\n_Static_assert(BOARD_GPS_UART_NUM==1 && BOARD_GPS_TX_GPIO==-1 && BOARD_GPS_RX_GPIO==28,"route");\n'
  p=subprocess.run(['cc','-std=c11','-x','c','-fsyntax-only','-'],input=code,text=True,capture_output=True)
  self.assertEqual(p.returncode,0,p.stderr)
 def test_ws35_uses_usb_primary_no_uart_secondary(self):
  s=(ROOT/'ESP32C5/sdkconfig.defaults.ws-c5-35').read_text()
  for token in ['CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y','CONFIG_ESP_CONSOLE_SECONDARY_NONE=y','# CONFIG_ESP_CONSOLE_UART_DEFAULT is not set']:
   self.assertIn(token,s)
 def test_only_classic_default90_preserves_nvs(self):
  s=(ROOT/'ESP32C5/components/board_hal/Kconfig').read_text()
  block=s[s.index('config BOARD_LCD_BRIGHTNESS_DEFAULT'):s.index('config BOARD_HAS_DUAL_SPI_BUS')]
  self.assertIn('default 90 if BOARD_CYD2USB',block);self.assertIn('default 80',block)
  m=(ROOT/'ESP32C5/main/main.c').read_text()
  self.assertIn('nvs_get_u8(h, NVS_KEY_BRIGHTNESS, &b) == ESP_OK',m)
  self.assertIn('screen_brightness_pct = b;',m)
if __name__=='__main__':unittest.main()
