"""v3.0.11: execute complete production QR UI, not a copied state machine."""
from pathlib import Path
import subprocess,tempfile,unittest
from test_qr_worker309 import PRE as LOW_MEMORY_PRE,ROOT
# Successful decoder scenarios must meet production 8192/4096 admission.
# Worker309 separately exercises the original low-memory profile.
PRE=LOW_MEMORY_PRE.replace("internal_free=4734,internal_largest=2304","internal_free=32768,internal_largest=16384")

def production():
 text=(ROOT/'ESP32C5/main/qr_decoder_ui.c').read_text()
 source='\n'.join(l for l in (ROOT/'ESP32C5/main/qr_preview.h').read_text().splitlines() if not l.startswith(('#include','#pragma')))+'\n'+'\n'.join(l for l in text.splitlines() if not l.startswith('#include'))
 record=(ROOT/'ESP32C5/components/cym_qr/qr_record.c').read_text()
 return 'static const char hex[]="0123456789ABCDEF";\n'+record[record.index('size_t cym_qr_escape('):record.index('static int all(')]+'\n'+source

class Lifecycle311(unittest.TestCase):
 def run_case(self,case):
  pre=PRE.replace('static int64_t esp_timer_get_time', 'static int snapshot_cancel,close_cancel,write_cancel,decode_valid=1,alloc_fail,release_calls,close_calls,worker_priority,acquire_request,schedule_decode,ui_dispatches;\nstatic void inject_cancel(void);\nstatic void inject_request(void);\nstatic void schedule_ui(void);\nstatic int64_t esp_timer_get_time')
  pre=pre.replace('size_t *f=(caps', 'if(n==240*320 && snapshot_cancel){inject_cancel();}\n if(n==240*320 && alloc_fail)return NULL;\n size_t *f=(caps')
  pre=pre.replace('(void)n;(void)prio;assert(bytes', '(void)n;worker_priority=prio;assert(bytes')
  pre=pre.replace('if(close_fail)return ESP_FAIL;*c=NULL;', 'close_calls++;if(close_cancel)inject_cancel();if(close_fail)return ESP_FAIL;*c=NULL;')
  pre=pre.replace('if(acquire_error)return acquire_error;', 'if(acquire_request)inject_request();if(acquire_error)return acquire_error;')
  pre=pre.replace('static void cym_camera_release(cym_camera_t*c){(void)c;}', 'static void cym_camera_release(cym_camera_t*c){assert(c);release_calls++;}')
  pre=pre.replace('memset(stats,0,sizeof(*stats));stats->valid=', 'if(schedule_decode)schedule_ui();memset(stats,0,sizeof(*stats));stats->valid=')
  pre=pre.replace('stats->payload_length=test_length;return cym_qr_decode_gray', 'stats->valid=decode_valid;stats->payload_length=test_length;return cym_qr_decode_gray')
  post=r"""
static void inject_cancel(void){atomic_store(&session->cancel,true);}
static int save(const uint8_t*p,size_t n,char*out,size_t cap){(void)p;(void)n;assert(!session->camera);save_calls++;poll(NULL);snprintf(out,cap,"test.json");return save_error;}
static int frame_save(const uint8_t*g,int w,int h,size_t stride,const char*m,char*out,size_t cap,qr_ui_capture_valid_fn valid,void *ctx){
 assert(valid(ctx));assert(!session->camera);assert(esp_ptr_external_ram(g));assert(w==240&&h==320&&stride==240);assert(g[0]==17&&g[76799]==91);assert(strstr(m,"source_stride=480"));assert(strstr(m,"rotation=270"));frame_calls++;if(write_cancel)inject_cancel();snprintf(out,cap,"frame-0000.pgm");return frame_error;
}
static void setup(void){debug_on=1;scan_success=1;qr_ui_options_t opts={.rotation=3,.save_frame=frame_save};qr_decoder_ui_open(&obj,(void*)1,save,&opts);assert(session);session->stride=480;session->gray[0]=17;session->gray[76799]=91;atomic_store(&session->phase,QR_SCANNING);}
static void pending(void){request_capture(NULL);request_capture(NULL);assert(atomic_load(&session->capture)==1);}
static void inject_request(void){request_capture(NULL);}
/* Deterministic FreeRTOS READY policy replay, NOT a silicon timing test.
 * Run actual UI poll during a long mocked decode and cancel from that peer.
 * A priority2 worker prevents all priority1 READY UI dispatches. */
static void schedule_ui(void){for(unsigned tick=0;tick<176;tick++){
 if(worker_priority<1||(worker_priority==1&&tick%2==0)){
  ui_dispatches++;poll(NULL);if(ui_dispatches==4)inject_cancel();
 }
}}

static void cleanup(void){close_fail=0;session->camera=NULL;atomic_store(&session->cancel,true);if(!atomic_load(&session->done))run_worker();qr_decoder_ui_stop();assert(!session&&!live);}
int main(void){setup();
"""+case+r"""
cleanup();puts("PASS production capture case");return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(pre+'\n'+production()+'\n'+post)
   subprocess.run(['cc','-std=c11','-O1','-g','-fsanitize=undefined',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)
 def test_snapshot_closes_before_sd(self):self.run_case('session->camera=(void*)1;pending();cym_qr_stats_t st={0};capture_frame(session,&st);assert(frame_calls==1&&!session->camera&&close_calls==1);')
 def test_close_failure_blocks_sd_and_retains_ownership(self):self.run_case('session->camera=(void*)1;close_fail=1;pending();cym_qr_stats_t st={0};capture_frame(session,&st);assert(session->camera&&frame_calls==0);')
 def test_cancel_before_capture(self):self.run_case('pending();inject_cancel();cym_qr_stats_t st={0};capture_frame(session,&st);assert(!frame_calls&&!close_calls);')
 def test_cancel_during_snapshot(self):self.run_case('pending();snapshot_cancel=1;cym_qr_stats_t st={0};capture_frame(session,&st);assert(!frame_calls);')
 def test_cancel_during_close(self):self.run_case('session->camera=(void*)1;pending();close_cancel=1;cym_qr_stats_t st={0};capture_frame(session,&st);assert(!frame_calls&&!session->camera);')
 def test_cancel_during_sd_retains_until_return(self):self.run_case('session->camera=(void*)1;pending();write_cancel=1;cym_qr_stats_t st={0};capture_frame(session,&st);assert(frame_calls==1&&atomic_load(&session->cancel));')
 def test_sd_failure_then_explicit_retry(self):self.run_case('pending();decode_valid=0;frame_error=ENOSPC;run_worker();assert(frame_calls==1&&!session->camera&&atomic_load(&session->done));poll(NULL);retry(NULL);frame_error=0;acquire_request=1;run_worker();assert(frame_calls==2&&!session->camera);')
 def test_resume_open_failure_is_reported(self):self.run_case('pending();decode_valid=0;run_worker();poll(NULL);scan_success=0;retry(NULL);run_worker();assert(atomic_load(&session->phase)==QR_ERROR&&!session->camera);')
 def test_successful_scan_has_priority_and_saves_once(self):self.run_case('pending();run_worker();assert(save_calls==1&&frame_calls==1&&atomic_load(&session->phase)==QR_RESULT&&!strcmp(session->text,"x"));assert(close_calls==1);')
 def test_scan_close_failure_no_sd(self):self.run_case('pending();close_fail=1;run_worker();assert(save_calls==0&&frame_calls==0&&session->camera&&atomic_load(&session->phase)==QR_RESULT&&!strcmp(session->text,"x"));')
 def test_debug_off_and_generation_cancel(self):self.run_case('pending();debug_on=0;cym_qr_stats_t st={0};capture_frame(session,&st);assert(!frame_calls);debug_on=1;pending();debug_generation+=2;capture_frame(session,&st);assert(!frame_calls&&!close_calls);')
 def test_back_reentry(self):self.run_case('pending();finish_at=3;qr_decoder_ui_stop();assert(!session&&!live);setup();pending();run_worker();assert(save_calls==1&&frame_calls==1);')
 def test_snapshot_allocation_failure_no_close_or_sd(self):self.run_case('pending();alloc_fail=1;cym_qr_stats_t st={0};capture_frame(session,&st);assert(!frame_calls&&!close_calls);')
 def test_repeated_capture_scan_again(self):self.run_case('decode_valid=0;acquire_request=1;for(int i=0;i<8;i++){run_worker();assert(frame_calls==i+1&&!session->camera);poll(NULL);if(i<7)retry(NULL);}')
 def test_priority_allows_ui_timeslices_during_cpu_decode(self):self.run_case('pending();schedule_decode=1;run_worker();assert(worker_priority==1&&ui_dispatches==88&&atomic_load(&session->cancel)&&save_calls==0&&frame_calls==0&&!session->camera);')

class SdAdmission311(unittest.TestCase):
 def test_actual_main_callback_rechecks_cancel_after_bus_wait(self):
  from test_qr_ui_stop import body
  text=(ROOT/'ESP32C5/main/main.c').read_text()
  fn=body(text.replace('static int qr_save_debug_frame(', 'void qr_save_debug_frame('),'qr_save_debug_frame').replace('void qr_save_debug_frame(', 'static int qr_save_debug_frame(')
  call='qr_save_debug_frame(gray,240,320,240,"numeric",name,sizeof(name)'+(',allowed,NULL' if 'qr_ui_capture_valid_fn' in fn else '')+')'
  code=r"""
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <errno.h>
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
typedef bool (*qr_ui_capture_valid_fn)(void *);
static bool enabled=true,valid=true,cancel_on_lock=true,mounted=true;static int writes,lock_ok=1,unlocks;static void *sd_spi_mutex=(void*)1;
static bool cym_debug_enabled(void){return enabled;}
static bool allowed(void *ctx){(void)ctx;return valid;}
static bool wifi_wardrive_is_sd_mounted(void){return mounted;}
static int xSemaphoreTake(void *p,int ticks){assert(p&&ticks==500);if(cancel_on_lock)valid=false;return lock_ok;}
static void xSemaphoreGive(void *p){assert(p);unlocks++;}
static int cym_qr_debug_frame(const char*r,const uint8_t*g,int w,int h,size_t s,const char*m,char*n,size_t c){(void)r;(void)g;(void)w;(void)h;(void)s;(void)m;(void)n;(void)c;writes++;return 0;}
"""+fn+'\nint main(void){uint8_t gray[1];char name[40];int e='+call+r""";assert(e==ECANCELED&&writes==0&&unlocks==1);cancel_on_lock=false;valid=true;e="""+call+r""";assert(e==0&&writes==1&&unlocks==2);valid=false;e="""+call+r""";assert(e==ECANCELED&&writes==1);valid=true;lock_ok=0;e="""+call+r""";assert(e==EBUSY&&writes==1);lock_ok=1;mounted=false;e="""+call+r""";assert(e==ENODEV&&writes==1);return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=c11','-O1','-fsanitize=undefined',str(p/'t.c'),'-o',str(p/'t')],check=True);subprocess.run([str(p/'t')],check=True)
if __name__=='__main__':unittest.main()
