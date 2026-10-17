"""Production matched output and terminal marker regression."""
import ctypes as C, subprocess, tempfile, unittest
from pathlib import Path
import test_qr311 as legacy
_original=legacy.Lifecycle311.run_case
def paired_case(self,case):
 old=legacy.PRE
 legacy.PRE=old.replace('static int64_t esp_timer_get_time', 'static int pair_calls,raw_alloc_fail;static size_t snapshot_base;\nstatic int64_t esp_timer_get_time').replace('size_t *f=(caps','if(n==153600){if(raw_alloc_fail)return NULL;snapshot_base=psram_free;}\n size_t *f=(caps')
 pair=r"""
int pair_save(const uint8_t *g,const uint8_t *rgb,int w,int h,size_t gs,size_t rs,const char *m,char *out,size_t cap,qr_ui_capture_valid_fn valid,void *ctx){
 assert(valid(ctx)&&!session->camera&&esp_ptr_external_ram(g)&&esp_ptr_external_ram(rgb));assert(w==240&&h==320&&gs==240&&rs==480);assert(strstr(m,"frame_id=1")||strstr(m,"frame_id="));assert(save_calls==1||!decode_valid);assert(snapshot_base-psram_free==230400);pair_calls++;snprintf(out,cap,"frame-0000.pgm");return frame_error;
}
"""
 try:
  # A local function declaration lets the harness define its callback after the
  # production module; no changes to legacy test behavior.
  patched=case
  if 'pair_save' in case:patched=pair+case
  # GCC accepts a block-scoped callback in this host-only harness.
  _original(self,patched)
 finally:legacy.PRE=old

ROOT=Path(__file__).resolve().parents[1]
class Lifecycle312(legacy.Lifecycle311):
 run_case=paired_case
 def test_capture_is_not_error(self):
  self.run_case('decode_valid=0;pending();run_worker();poll(NULL);assert(strstr(diagnostics,"stage=capture_displayed value=5"));assert(!strstr(diagnostics,"stage=error_displayed value=5"));')
 def test_matched_snapshot_and_result_priority(self):
  self.run_case("session->options.save_pair=pair_save;pending();run_worker();assert(pair_calls==1&&save_calls==1&&!session->camera&&!session->raw_snapshot);")
 def test_raw_alloc_failure_does_not_save_gray_alone(self):
  self.run_case("session->options.save_pair=pair_save;raw_alloc_fail=1;pending();run_worker();assert(!pair_calls&&save_calls==1&&!session->raw_snapshot);")
 def test_pair_close_failure_blocks_all_sd(self):
  self.run_case("session->options.save_pair=pair_save;close_fail=1;pending();run_worker();assert(!pair_calls&&!save_calls&&session->camera&&!session->raw_snapshot);")
 def test_pair_repeated_no_queue_or_growth(self):
  self.run_case("session->options.save_pair=pair_save;decode_valid=0;acquire_request=1;size_t base=psram_free;for(int i=0;i<8;i++){run_worker();assert(pair_calls==i+1&&!session->camera&&!session->raw_snapshot&&psram_free==base);poll(NULL);if(i<7)retry(NULL);}")
class Pair312(unittest.TestCase):
 def test_real_pair_collision_and_pixels(self):
  b=ROOT/'ESP32C5/components/cym_qr'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);so=p/'r.so'
   subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror','-I',str(b/'include'),str(b/'qr_record.c'),'-o',str(so)],check=True)
   lib=C.CDLL(str(so))
   self.assertTrue(hasattr(lib,'cym_qr_debug_pair'),'matched raw RGB565 + grayscale writer missing')
   f=lib.cym_qr_debug_pair
   f.argtypes=[C.c_char_p,C.c_void_p,C.c_void_p,C.c_int,C.c_int,C.c_size_t,C.c_size_t,C.c_char_p,C.c_void_p,C.c_size_t]
   card=p/'card';(card/'lab/QR/debug').mkdir(parents=True)
   folder=card/'lab/QR/debug';(folder/'frame-0000.rgb565').write_bytes(b'prior raw');(folder/'frame-0001.pgm').write_bytes(b'prior gray')
   gray=bytes([0,76,149,28,255,17]);raw=bytes([0,0,0,248,224,7,31,0,255,255,123,0])
   name=C.create_string_buffer(40)
   self.assertEqual(f(str(card).encode(),gray,raw,3,2,3,6,b'frame_id=7 format=RGB565_LE',name,40),0)
   self.assertEqual(name.value,b'frame-0002.pgm')
   self.assertEqual((folder/'frame-0002.rgb565').read_bytes(),raw)
   data=(folder/'frame-0002.pgm').read_bytes();self.assertTrue(data.endswith(gray));self.assertIn(b'frame_id=7',data)
   self.assertEqual((folder/'frame-0000.rgb565').read_bytes(),b'prior raw')
   self.assertEqual((folder/'frame-0001.pgm').read_bytes(),b'prior gray')
   self.assertEqual(f(str(card).encode(),gray,raw,3,2,3,5,b'frame_id=8',name,40),22)
   self.assertEqual(name.value,b'')
class Completion312(unittest.TestCase):
 def test_production_completion_claim_and_short_counts(self):
  from test_qr_ui_stop import body
  src=(ROOT/'ESP32C5/components/cym_camera/camera_ws_c5_35.c').read_text()
  fn=body(src.replace('static bool receive_done(', 'void receive_done('),'receive_done').replace('void receive_done(', 'static bool receive_done(')
  code=r"""
#include <assert.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#define PACKET_BYTES 155524
#define pdFALSE 0
#define pdTRUE 1
typedef int BaseType_t;
typedef void *parlio_rx_unit_handle_t;
typedef struct {size_t recv_bytes;} parlio_rx_event_data_t;
typedef struct {atomic_bool armed,frame_complete;atomic_uint recv_bytes,done_events;void *done;size_t packet_size;} ws_camera_t;
static int wakes;
static void xSemaphoreGiveFromISR(void *s,int *w){(void)s;*w=1;wakes++;}
"""+fn+r"""
int main(void){ws_camera_t c={.packet_size=155584};parlio_rx_event_data_t e={155524};atomic_store(&c.armed,true);assert(receive_done(NULL,&e,&c));assert(!atomic_load(&c.armed));assert(atomic_load(&c.frame_complete));assert(!receive_done(NULL,&e,&c)&&wakes==1);unsigned short_counts[]={0,4092,151404};for(unsigned i=0;i<3;i++){atomic_store(&c.armed,true);e.recv_bytes=short_counts[i];receive_done(NULL,&e,&c);assert(!atomic_load(&c.frame_complete));}atomic_store(&c.armed,true);e.recv_bytes=155585;receive_done(NULL,&e,&c);assert(!atomic_load(&c.frame_complete));return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code);subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True);subprocess.run([str(p/'t')],check=True)
class Pixels312(unittest.TestCase):
 def test_known_pixels_through_packet_and_gray(self):
  from test_qr_decoder_contract import DecoderTests
  b=ROOT/'ESP32C5/components/cym_camera'
  DecoderTests.setUpClass()
  try:
   lib=DecoderTests.lib
   with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'esp_err.h').write_text('typedef int esp_err_t;\n')
    subprocess.run(['cc','-shared','-fPIC','-I',str(p),'-I',str(b/'include'),str(b/'camera_packet.c'),'-o',str(p/'p.so')],check=True)
    unpack=C.CDLL(str(p/'p.so')).cym_camera_unpack_bf3901;unpack.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t]
    values=[0x0000,0xFFFF,0xF800,0x07E0,0x001F,0x7BEF]
    row=b''.join(v.to_bytes(2,'little') for v in values)*40
    packet=b'\xff\xff\xff\x00'+b''.join(b'\xff\xff\xff\x40'+bytes([y&255,99])+row for y in range(320))
    rgb=C.create_string_buffer(153600);gray=C.create_string_buffer(76800)
    self.assertEqual(unpack(packet,len(packet),rgb,153600),0)
    self.assertEqual(rgb.raw,row*320)
    lib.cym_qr_rgb565_gray.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_int,C.c_int]
    self.assertEqual(lib.cym_qr_rgb565_gray(rgb,480,gray,240,320),0)
    expected=bytes([(77*(((v>>11)&31)*255//31)+150*(((v>>5)&63)*255//63)+29*((v&31)*255//31))>>8 for v in values])*40*320
    self.assertEqual(gray.raw,expected)
    self.assertEqual(list(gray.raw[:5]),[0,255,76,149,28])
  finally:DecoderTests.tearDownClass()
class Readback312(unittest.TestCase):
 def test_format_readback_is_bounded_quiet_and_observational(self):
  from test_qr_ui_stop import body
  src=(ROOT/'ESP32C5/components/cym_camera/camera_ws_c5_35.c').read_text()
  self.assertIn('static void format_readback(',src,'documented format readback diagnostic missing')
  fn=body(src,'format_readback')
  code=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int esp_err_t;
typedef struct {void *sensor;} ws_camera_t;
static bool debug;static int reads,logs,fail_at=-1;static uint8_t values[]={0x04,0x05,0x03,0x13};static char output[300];
static bool cym_debug_enabled(void){return debug;}
static int i2c_master_transmit_receive(void *h,const void *tx,size_t tn,void *rx,size_t rn,int ms){(void)tx;assert(h&&tn==1&&rn==1&&ms==100);int n=reads++%4;if(n==fail_at)return 9;*(uint8_t *)rx=values[n];return 0;}
#define ESP_LOGI(tag,fmt,...) do{(void)(tag);logs++;snprintf(output,sizeof(output),fmt,__VA_ARGS__);}while(0)
"""+fn+r"""
int main(void){ws_camera_t c={(void*)1};format_readback(&c);assert(!reads&&!logs);debug=true;format_readback(&c);assert(reads==4&&logs==1&&strstr(output,"match=1"));values[0]=0;format_readback(&c);assert(reads==8&&logs==2&&strstr(output,"match=0"));fail_at=1;format_readback(&c);assert(reads==12&&logs==3&&strstr(output,"errors=0,9,0,0"));return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code);subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True);subprocess.run([str(p/'t')],check=True)
if __name__=='__main__':unittest.main()
