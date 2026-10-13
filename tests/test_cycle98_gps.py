from pathlib import Path
import subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
class Receive98(unittest.TestCase):
 def test_actual_receive_framer(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'.hermes') as out:
   p=Path(out); (p/'rx.c').write_text(r"""#include "gps_rx_ws35.h"
#include <assert.h>
#include <string.h>
int main(void){
 gps_rx_ws35_t f={0}; unsigned done=0;
 const char *s="noise$GPGGA,123";
 for(;*s;s++) assert(!gps_rx_ws35_push(&f,*s));
 s=",456*00\r\n$GNRMC,7*01\n";
 for(;*s;s++) if(gps_rx_ws35_push(&f,*s)){done++; if(done==1)assert(!strcmp(f.line,"$GPGGA,123,456*00"));else assert(!strcmp(f.line,"$GNRMC,7*01"));}
 assert(done==2);
 assert(!gps_rx_ws35_push(&f,'$'));
 for(unsigned i=0;i<sizeof(f.line)+10;i++)assert(!gps_rx_ws35_push(&f,'x'));
 assert(!gps_rx_ws35_push(&f,'\n'));
 s="$bad$GPRMC,ok*00\n"; done=0;
 for(;*s;s++)if(gps_rx_ws35_push(&f,*s)){done++;assert(!strcmp(f.line,"$GPRMC,ok*00"));}
 assert(done==1);return 0;}
"""); subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(ROOT/'ESP32C5/main'),str(p/'rx.c'),'-o',str(p/'rx')],check=True,capture_output=True)
   subprocess.run([str(p/'rx')],check=True,capture_output=True)
 def test_single_reader_receive_only_contract(self):
  t=(ROOT/'ESP32C5/main/main.c').read_text()
  init=t[t.index('static esp_err_t init_gps_uart(void)\n{'):t.index('static bool parse_gps_nmea(const char *nmea_sentence)\n{')]
  self.assertIn('gps_rx_only_ws35',init)
  self.assertIn('gpio_reset_pin(GPS_TX_PIN)',init)
  self.assertIn('GPS_RX_OWNER board=WS35',t)
  self.assertIn('gps_uart_consumer_read',t)
  self.assertEqual(t.count('uart_read_bytes(GPS_UART_NUM,'),2)
  self.assertIn('gps_rx_ws35_push(&ws35_rx',t)
  self.assertIn('GPS_RAW_RX board=WS35',t)
if __name__=='__main__':unittest.main(verbosity=2)
