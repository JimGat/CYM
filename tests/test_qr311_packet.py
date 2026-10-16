"""Production packet validation reasons; no pixels/payload logged."""
from pathlib import Path
import ctypes as C,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class PacketReasons311(unittest.TestCase):
 def test_reason_codes_and_no_partial_output(self):
  b=ROOT/'ESP32C5/components/cym_camera'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'esp_err.h').write_text('typedef int esp_err_t;\n')
   subprocess.run(['cc','-shared','-fPIC','-I',str(p),'-I',str(b/'include'),str(b/'camera_packet.c'),'-o',str(p/'packet.so')],check=True)
   f=C.CDLL(str(p/'packet.so')).cym_camera_unpack_bf3901;f.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t]
   data=bytearray([255,255,255,0]);row=bytes([255,255,255,64,0,0])+bytes(480)
   data+=row*320;out=C.create_string_buffer(bytes([77])*153600,153600)
   self.assertEqual(f(bytes(data),len(data)-1,out,len(out)),-1)
   data[0]=0;self.assertEqual(f(bytes(data),len(data),out,len(out)),-2);self.assertEqual(out.raw,bytes([77])*153600)
   data[0]=255
   for y in [0,159,319]:
    data[4+y*486]=0;self.assertEqual(f(bytes(data),len(data),out,len(out)),-3);self.assertEqual(out.raw,bytes([77])*153600);data[4+y*486]=255
   self.assertEqual(f(bytes(data),len(data),out,len(out)),0);self.assertEqual(out.raw,bytes(153600))

class BackendDiagnostics311(unittest.TestCase):
 def test_bounded_production_invalid_reason_helper(self):
  from test_qr_ui_stop import body
  text=(ROOT/'ESP32C5/components/cym_camera/camera_ws_c5_35.c').read_text()
  self.assertIn('static esp_err_t invalid_response(',text)
  fn=body(text.replace('static esp_err_t invalid_response(', 'void invalid_response('),'invalid_response').replace('void invalid_response(', 'static esp_err_t invalid_response(')
  source=r"""
#include <assert.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int esp_err_t;
#define ESP_ERR_INVALID_RESPONSE 264
typedef struct {atomic_uint recv_bytes;unsigned incomplete,header_errors,row_errors,shape_errors;int64_t invalid_report_at;} ws_camera_t;
static bool debug;static int64_t now=100000;static unsigned logs;static char output[512];
static bool cym_debug_enabled(void){return debug;}
static int64_t esp_timer_get_time(void){return now;}
#define ESP_LOGI(tag,fmt,...) do {(void)(tag);logs++;snprintf(output,sizeof(output),fmt,__VA_ARGS__);} while(0)
"""+fn+r"""
int main(void){ws_camera_t c={0};atomic_store(&c.recv_bytes,123);debug=false;assert(invalid_response(&c,0)==264&&!logs);debug=true;invalid_response(&c,-2);assert(logs==1&&strstr(output,"header=1"));for(int i=0;i<100;i++)invalid_response(&c,-3);assert(logs==1);now+=5000000;invalid_response(&c,0);assert(logs==2&&strstr(output,"incomplete=2")&&strstr(output,"row=100")&&strstr(output,"recv_bytes=123"));debug=false;now+=5000000;invalid_response(&c,-1);assert(logs==2&&c.shape_errors==1);return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(source)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True);subprocess.run([str(p/'t')],check=True)
if __name__=='__main__':unittest.main()
