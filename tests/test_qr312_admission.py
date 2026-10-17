"""Execute production callbacks under controlled SD/ISR schedules; no hardware claim."""
import subprocess,tempfile,unittest
from pathlib import Path
import test_qr312 as base
from test_qr_ui_stop import body
ROOT=Path(__file__).resolve().parents[1]
class PairedEdges312(unittest.TestCase):
 run_case=base.paired_case
 def test_debug_off_no_pair_and_result_kept(self):self.run_case('session->options.save_pair=pair_save;pending();debug_on=0;run_worker();assert(!pair_calls&&save_calls==1&&!session->raw_snapshot&&atomic_load(&session->phase)==QR_RESULT);')
 def test_debug_generation_changed_no_pair(self):self.run_case('session->options.save_pair=pair_save;pending();debug_generation+=2;run_worker();assert(!pair_calls&&save_calls==1&&!session->raw_snapshot);')
 def test_gray_alloc_failure_frees_raw_and_keeps_result(self):self.run_case('session->options.save_pair=pair_save;pending();alloc_fail=1;size_t before=psram_free;run_worker();assert(!pair_calls&&save_calls==1&&!session->raw_snapshot&&psram_free==before&&!strcmp(session->text,"x"));')
 def test_pair_sd_failure_keeps_result(self):self.run_case('session->options.save_pair=pair_save;pending();frame_error=ENOSPC;run_worker();assert(pair_calls==1&&save_calls==1&&!session->raw_snapshot&&atomic_load(&session->phase)==QR_RESULT&&!strcmp(session->text,"x"));')
 def test_close_cancellation_blocks_both_writes(self):self.run_case('session->options.save_pair=pair_save;pending();close_cancel=1;run_worker();assert(!pair_calls&&!save_calls&&!session->raw_snapshot);')
 def test_pair_bytes_are_from_the_same_acquisition(self):
  old=base.legacy.PRE
  base.legacy.PRE=old.replace('static uint8_t rgb[153600];','static uint8_t rgb[153600];rgb[0]=17;rgb[153599]=91;')
  try:self.run_case('int identity(const uint8_t*g,const uint8_t*r,int w,int h,size_t gs,size_t rs,const char*m,char*n,size_t cap,qr_ui_capture_valid_fn valid,void*ctx){assert(valid(ctx)&&w==240&&h==320&&gs==240&&rs==480);assert(g[0]==r[0]&&g[76799]==r[153599]&&r[0]==17&&r[153599]==91);assert(strstr(m,"frame_id=1 "));assert(!session->camera);pair_calls++;snprintf(n,cap,"frame-0000.pgm");return 0;} session->options.save_pair=identity;pending();run_worker();assert(pair_calls==1&&save_calls==1);')
  finally:base.legacy.PRE=old
class SdAdmission312(unittest.TestCase):
 def test_pair_and_record_recheck_under_sd_mutex(self):
  src=(ROOT/'ESP32C5/main/main.c').read_text()
  funcs='\n'.join(body(src.replace('static int '+name+'(', 'void '+name+'('),name).replace('void '+name+'(', 'static int '+name+'(') for name in ['qr_save_debug_pair','qr_save_record_checked'])
  pre=r"""
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <errno.h>
#include <time.h>
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
#define FW_VERSION "v3.0.12"
typedef bool (*qr_ui_capture_valid_fn)(void*);
static bool enabled=true,valid=true,mounted=true;static int on_lock,lock_ok=1,writes,unlocks;static void *sd_spi_mutex=(void*)1;
static bool cym_debug_enabled(void){return enabled;}static bool allowed(void*p){(void)p;return valid;}
static bool wifi_wardrive_is_sd_mounted(void){return mounted;}
static int xSemaphoreTake(void*p,int t){assert(p&&t==500);if(on_lock==1)valid=false;if(on_lock==2)enabled=false;return lock_ok;}
static void xSemaphoreGive(void*p){assert(p);unlocks++;}
static int64_t esp_timer_get_time(void){return 0;}
static int cym_qr_debug_pair(const char*r,const uint8_t*g,const uint8_t*b,int w,int h,size_t gs,size_t rs,const char*m,char*n,size_t cap){(void)r;(void)g;(void)b;(void)w;(void)h;(void)gs;(void)rs;(void)m;(void)n;(void)cap;writes++;return 0;}
static int cym_qr_record(const char*r,const uint8_t*p,size_t n,const char*v,int64_t t,uint64_t u,char*o,size_t c){(void)r;(void)p;(void)n;(void)v;(void)t;(void)u;(void)o;(void)c;writes++;return 0;}
"""
  pair='qr_save_debug_pair(gray,gray,240,320,240,480,"frame_id=1",name,sizeof(name),allowed,NULL)'
  record='qr_save_record_checked(gray,1,name,sizeof(name),allowed,NULL)'
  code=pre+funcs+'\nint main(void){uint8_t gray[1]={0};char name[40];'
  for call in [pair,record]:
   code+='valid=enabled=mounted=true;on_lock=1;'+('int before=writes;int e=' if call==pair else 'before=writes;e=')+call+';assert(e==ECANCELED&&writes==before);valid=true;on_lock=0;e='+call+';assert(!e&&writes==before+1);valid=false;e='+call+';assert(e==ECANCELED&&writes==before+1);valid=true;lock_ok=0;e='+call+';assert(e==EBUSY);lock_ok=1;mounted=false;e='+call+';assert(e==ENODEV);'
  code+='valid=mounted=enabled=true;on_lock=2;int before2=writes;assert('+pair+'==ECANCELED&&writes==before2);return 0;}'
  self.compile_run(code)
 def compile_run(self,code):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code);subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p/'t.c'),'-o',str(p/'t')],check=True);subprocess.run([str(p/'t')],check=True)
class Isr312(SdAdmission312):
 def test_production_fake_eof_partial_and_done_order(self):
  src=(ROOT/'ESP32C5/components/cym_camera/camera_ws_c5_35.c').read_text();funcs=''
  for name in ['receive_done','receive_partial']:
   funcs+=body(src.replace('static bool '+name+'(', 'void '+name+'('),name).replace('void '+name+'(', 'static bool '+name+'(')+'\n'
  funcs+=body(src,'end_frame')
  code=r"""
#include <assert.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#define PACKET_BYTES 155524
#define pdFALSE 0
#define pdTRUE 1
#define portYIELD_FROM_ISR() do{yields++;}while(0)
typedef int BaseType_t;typedef int esp_err_t;typedef void *parlio_rx_unit_handle_t;
typedef struct {size_t recv_bytes;}parlio_rx_event_data_t;
typedef struct {atomic_bool armed,frame_complete;atomic_uint recv_bytes,partial_events,partial_bytes,last_partial,fake_eofs,done_events;atomic_int fake_error;void *done,*rx;size_t packet_size;}ws_camera_t;
static int wakes,yields,fake_calls,fake_error;static size_t fake_bytes=155524;
static void xSemaphoreGiveFromISR(void*p,int*w){(void)p;wakes++;*w=1;}
static esp_err_t parlio_rx_unit_trigger_fake_eof(void *rx,bool*wake);
"""+funcs+r"""
static esp_err_t parlio_rx_unit_trigger_fake_eof(void*rx,bool*wake){ws_camera_t*c=rx;fake_calls++;if(fake_error)return fake_error;parlio_rx_event_data_t part={64},done={fake_bytes};receive_partial(rx,&part,c);*wake=receive_done(rx,&done,c);return 0;}
int main(void){ws_camera_t c={.packet_size=155584};c.rx=&c;parlio_rx_event_data_t full={155524},part={4092};
atomic_store(&c.armed,true);receive_partial(NULL,&part,&c);receive_done(NULL,&full,&c);end_frame(&c);assert(!fake_calls&&wakes==1&&atomic_load(&c.partial_bytes)==4092);
atomic_store(&c.armed,true);fake_bytes=151404;end_frame(&c);assert(fake_calls==1&&!atomic_load(&c.armed)&&!atomic_load(&c.frame_complete)&&atomic_load(&c.recv_bytes)==151404&&atomic_load(&c.last_partial)==64);
atomic_store(&c.armed,true);fake_bytes=155524;end_frame(&c);assert(fake_calls==2&&atomic_load(&c.frame_complete));
atomic_store(&c.armed,true);atomic_store(&c.frame_complete,false);fake_error=7;end_frame(&c);assert(fake_calls==3&&atomic_load(&c.fake_error)==7&&!atomic_load(&c.armed)&&!atomic_load(&c.frame_complete));int events=atomic_load(&c.partial_events);receive_partial(NULL,&part,&c);assert(atomic_load(&c.partial_events)==(unsigned)events);return 0;}
"""
  self.compile_run(code)
if __name__=='__main__':unittest.main()
