"""Compile real Wardrive lifecycle helpers with deterministic SDK boundaries.
Not RF, FreeRTOS scheduling, SD, or physical-board acceptance.
"""
from pathlib import Path
import os,re,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
def function(source,name):
    m=re.search(r'static [^;\n]+\b'+name+r'\([^;]*?\)\s*\{',source)
    if not m: raise AssertionError('Missing function '+name)
    opening=source.index('{',m.start()); depth=1;pos=opening+1
    while depth:
        depth+=(source[pos]=='{')-(source[pos]=='}');pos+=1
    return source[m.start():pos]
PREFIX=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define ESP_OK 0
typedef int esp_err_t;
#define ESP_LOGE(tag,...) do {printf(__VA_ARGS__);puts("");} while(0)
#define ESP_LOGW ESP_LOGE
#define ESP_LOGI ESP_LOGE
#define TAG "test"
#define pdMS_TO_TICKS(x) (x)
#define pdTRUE 1
#define CONFIG_BOARD_HAS_PSRAM 1
#define WDP_BLE_MAX_DEVICES 512
#define WDP_BLE_NOPSRAM_DEVICES 128
#define MALLOC_CAP_INTERNAL 4
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_8BIT 2
#define eSuspended 2
static bool nimble_port_initialized,nimble_deinit_failed,nimble_cleanup_busy;
static bool bt_scan_active,nimble_initialized,nimble_stop_requested,nimble_host_exited;
static void *bt_scan_task_handle,*nimble_host_handle,*lvgl_mutex=(void*)1;
static bool wdp_ble_accepting,g_wd_ble=true;
static bool wardrive_capture_ready,wdp_ble_cleanup_pending;
static unsigned wdp_ble_inflight;
static uint32_t wdp_ble_capacity;
static int wdp_ble_count;
static bool wdp_ble_full_logged;
typedef struct {int value;} wdp_ble_device_t;
static wdp_ble_device_t *wdp_ble_devices;
static volatile bool wardrive_active;
static bool wardrive_task_done;
static void *wardrive_task_handle,*wardrive_task_stack;
enum {WD_RADIO_WIFI_ONLY,WD_RADIO_BLE_ONLY};
static int g_wd_radio_mode;
static int64_t now_ms,lock_at,host_exit_at,callback_exit_at,cancel_at;
static bool locked,alloc_fail;
static int takes,gives,frees,deinits,deinit_result,body_calls,task_state,task_deletes,suspends;
static void advance(int ms) {
 now_ms+=ms;
 if(host_exit_at>=0 && now_ms>=host_exit_at) nimble_host_exited=true;
 if(callback_exit_at>=0 && now_ms>=callback_exit_at) wdp_ble_inflight=0;
 if(cancel_at>=0 && now_ms>=cancel_at) wardrive_active=false;
}
static int64_t esp_timer_get_time(void){return now_ms*1000;}
static void vTaskDelay(int ms){assert(ms>0);advance(ms);}
static int xSemaphoreTake(void*p,int wait) {
 assert(p==lvgl_mutex && !locked);++takes;
 if(lock_at<0 || lock_at>now_ms+wait){advance(wait);return 0;}
 if(lock_at>now_ms)advance((int)(lock_at-now_ms));locked=true;return pdTRUE;
}
static void xSemaphoreGive(void*p){assert(p==lvgl_mutex && locked);locked=false;++gives;}
static void heap_caps_free(void*p){assert(!wdp_ble_inflight);if(p==wdp_ble_devices)assert(locked);++frees;free(p);}
static void *heap_caps_calloc(size_t n,size_t s,int flags){if (alloc_fail || (!CONFIG_BOARD_HAS_PSRAM && (flags & MALLOC_CAP_SPIRAM))) return NULL;return calloc(n,s);}
static void bt_stop_scan(void){}
static int nimble_port_deinit(void){assert(nimble_host_exited);++deinits;return deinit_result;}
struct ble_gap_event {int value;};
static int wdp_ble_gap_body(struct ble_gap_event*e,void*a){(void)e;(void)a;++body_calls;assert(wdp_ble_devices);return 7;}
static unsigned uxTaskGetStackHighWaterMark(void*p){(void)p;return 5692;}
static void vTaskSuspend(void*p){assert(!p);++suspends;}
static int eTaskGetState(void*p){assert(p==wardrive_task_handle);return task_state;}
static void vTaskDelete(void*p){assert(p==wardrive_task_handle && task_state==eSuspended && wardrive_task_done);++task_deletes;}
"""
SUFFIX=r"""
typedef struct {int filter_mask;} wifi_promiscuous_filter_t;
#define WIFI_PROMIS_FILTER_MASK_MGMT 1
#define MALLOC_CAP_DMA 4
static int wifi_fail_at,wifi_calls,country_calls;
static unsigned heap_caps_get_free_size(int caps){(void)caps;return 1374;}
static void wdp_promiscuous_cb(void*a,int b){(void)a;(void)b;}
static int esp_wifi_set_promiscuous_filter(void*p){(void)p;++wifi_calls;return wifi_fail_at==1?-1:0;}
static int esp_wifi_set_promiscuous_rx_cb(void(*p)(void*,int)){(void)p;++wifi_calls;return wifi_fail_at==2?-2:0;}
static int esp_wifi_set_promiscuous(bool on){assert(on);++wifi_calls;return wifi_fail_at==3?-3:0;}
static void wdp_apply_wardrive_country(void){++country_calls;}
SEGMENT_PLACEHOLDER
static void reset(void){
 nimble_port_initialized=nimble_deinit_failed=nimble_cleanup_busy=false;
 nimble_initialized=nimble_stop_requested=nimble_host_exited=bt_scan_active=false;
 bt_scan_task_handle=nimble_host_handle=NULL;wdp_ble_devices=NULL;
 wdp_ble_inflight=wdp_ble_capacity=wdp_ble_count=0;wdp_ble_full_logged=wdp_ble_accepting=false;
 wardrive_active=true;wardrive_task_done=false;wardrive_task_handle=wardrive_task_stack=NULL;
 g_wd_radio_mode=WD_RADIO_WIFI_ONLY;now_ms=0;lock_at=0;
 host_exit_at=callback_exit_at=cancel_at=-1;locked=alloc_fail=false;
 takes=gives=frees=deinits=deinit_result=body_calls=task_deletes=suspends=0;task_state=0;
}
static void table(void){wdp_ble_devices=calloc(8,sizeof(*wdp_ble_devices));wdp_ble_capacity=8;wdp_ble_count=3;wdp_ble_accepting=true;}
int main(int argc,char**argv){setvbuf(stdout,NULL,_IONBF,0);assert(argc==2);reset();const char*k=argv[1];
 if(!strcmp(k,"empty_locked")){
  lock_at=350;bool ok=wdp_ble_session_begin();
  printf("empty locked: ok=%d lock_takes=%d elapsed_ms=%lld active=%d\n",ok,takes,(long long)now_ms,wardrive_active);
  assert(ok && takes==0 && now_ms==0 && !wdp_ble_devices);
 } else if(!strcmp(k,"empty_immediate")){assert(wdp_ble_session_begin());assert(!wdp_ble_devices);}
 else if(!strcmp(k,"live_immediate")){table();assert(wdp_ble_session_begin());assert(frees==1 && gives==1);}
 else if(!strcmp(k,"live_delayed")){table();lock_at=350;assert(wdp_ble_session_begin());assert(now_ms>=350 && frees==1 && gives==1 && takes>1);}
 else if(!strcmp(k,"live_never")){table();lock_at=-1;assert(!wdp_ble_session_begin());assert(wdp_ble_devices && frees==0 && now_ms<=1200);}
 else if(!strcmp(k,"host_delayed")){table();nimble_port_initialized=true;host_exit_at=200;assert(wdp_ble_session_begin());assert(deinits==1 && frees==1 && !nimble_port_initialized);}
 else if(!strcmp(k,"host_never")){table();nimble_port_initialized=true;assert(!wdp_ble_session_begin());assert(deinits==0 && frees==0 && wdp_ble_devices && nimble_port_initialized && now_ms<=5400);}
 else if(!strcmp(k,"deinit_failed")){table();nimble_port_initialized=true;nimble_host_exited=true;deinit_result=-1;assert(!wdp_ble_session_begin());assert(deinits==1 && frees==0 && nimble_deinit_failed);}
 else if(!strcmp(k,"callbacks_delayed")){table();wdp_ble_inflight=1;callback_exit_at=350;assert(wdp_ble_session_begin());assert(frees==1 && now_ms>=350);}
 else if(!strcmp(k,"callbacks_never")){table();wdp_ble_inflight=1;assert(!wdp_ble_session_begin());assert(frees==0 && wdp_ble_devices && now_ms<=1400);}
 else if(!strcmp(k,"cancel")){table();lock_at=-1;cancel_at=120;assert(!wdp_ble_session_begin());assert(!wardrive_active && frees==0 && now_ms<=240);}
 else if(!strcmp(k,"ble_restarts")){g_wd_radio_mode=WD_RADIO_BLE_ONLY;for(int i=0;i<5;i++){assert(wdp_ble_session_begin());assert(wdp_ble_devices && wdp_ble_accepting && wdp_ble_count==0);struct ble_gap_event e={0};assert(wdp_ble_gap_cb(&e,NULL)==7);assert(wdp_ble_inflight==0);assert(wdp_ble_session_end());assert(!wdp_ble_devices && !wdp_ble_accepting);assert(wdp_ble_gap_cb(&e,NULL)==0);}assert(frees==5 && body_calls==5);}
 else if(!strcmp(k,"allocation_failure")){g_wd_radio_mode=WD_RADIO_BLE_ONLY;alloc_fail=true;assert(!wdp_ble_session_begin());assert(!wdp_ble_devices && !wdp_ble_accepting);}
 else if(!strcmp(k,"empty_stop_locked")){lock_at=-1;assert(wdp_ble_session_end());assert(takes==0);}
 else if(!strcmp(k,"reap")){wardrive_task_handle=(void*)1;wardrive_task_stack=malloc(16);assert(!wardrive_reap_task());assert(frees==0 && task_deletes==0);wardrive_task_finish();assert(suspends==1);assert(!wardrive_reap_task());task_state=eSuspended;assert(wardrive_reap_task());assert(task_deletes==1 && frees==1 && !wardrive_task_stack);}
 else if(!strcmp(k,"wifi_ok")){start_wifi_segment();assert(wardrive_active && country_calls==1 && wifi_calls==3);}
 else if(!strcmp(k,"wifi_filter_fail")){wifi_fail_at=1;start_wifi_segment();assert(!wardrive_active && country_calls==0 && wifi_calls==1);}
 else if(!strcmp(k,"wifi_callback_fail")){wifi_fail_at=2;start_wifi_segment();assert(!wardrive_active && country_calls==0 && wifi_calls==2);}
 else if(!strcmp(k,"wifi_enable_fail")){wifi_fail_at=3;start_wifi_segment();assert(!wardrive_active && country_calls==0 && wifi_calls==3);}
 else if(!strcmp(k,"wifi_cancelled")){wardrive_active=false;start_wifi_segment();assert(wifi_calls==0 && country_calls==0);}
 else if(!strcmp(k,"status")){assert(!strcmp(wardrive_channel_status(),"START"));wardrive_capture_ready=true;assert(wardrive_channel_status()==NULL);g_wd_radio_mode=WD_RADIO_BLE_ONLY;assert(!strcmp(wardrive_channel_status(),"SCAN"));wardrive_active=false;wardrive_task_handle=(void*)1;assert(!strcmp(wardrive_channel_status(),"STOPPING"));wardrive_task_done=true;assert(!strcmp(wardrive_channel_status(),"STOPPED"));wdp_ble_cleanup_pending=true;assert(!strcmp(wardrive_channel_status(),"CLEANUP"));nimble_deinit_failed=true;assert(!strcmp(wardrive_channel_status(),"FAILED"));}
 else assert(0);
 printf("PASS %s elapsed_ms=%lld takes=%d frees=%d deinits=%d\n",k,(long long)now_ms,takes,frees,deinits);return 0;
}
"""
class WardriveStartupProduction(unittest.TestCase):
 HAS_PSRAM=1
 @classmethod
 def setUpClass(cls):
  source=Path(os.environ.get('CYM_WD_SOURCE',ROOT/'ESP32C5/main/main.c')).read_text()
  cls.work=tempfile.TemporaryDirectory(prefix='cym-wd-',dir=os.environ.get('CYM_WD_TEST_TMPDIR'))
  cls.path=Path(cls.work.name)
  # Only dependency boundaries are mocked; production lifecycle bodies execute verbatim.
  names=['bt_nimble_cleanup_bounded','wdp_ble_gap_cb','wdp_ble_session_end','wdp_ble_session_begin','wardrive_task_finish','wardrive_reap_task','wardrive_channel_status']
  declarations=''
  for name in ['wdp_ble_cleanup_reason']:
   m=re.search(r'static const char \*'+name+r'[^;]*;',source)
   if m:declarations+=m.group(0)+'\n'
  worker=function(source,'wardrive_promisc_task')
  segment=worker[worker.index('    wifi_promiscuous_filter_t filt'):worker.index('    // Start BLE scan only')]
  cls.c=PREFIX.replace('#define CONFIG_BOARD_HAS_PSRAM 1',f'#define CONFIG_BOARD_HAS_PSRAM {cls.HAS_PSRAM}')+declarations+'\n'.join(function(source,n) for n in names)+SUFFIX.replace('SEGMENT_PLACEHOLDER','static void start_wifi_segment(void){size_t dma_before=1374;'+segment+'}')
  (cls.path/'lifecycle.c').write_text(cls.c)
  subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Wno-unused-function','-Wno-misleading-indentation',str(cls.path/'lifecycle.c'),'-o',str(cls.path/'lifecycle')],check=True)
 @classmethod
 def tearDownClass(cls):cls.work.cleanup()
 def run_case(self,name):
  p=subprocess.run([str(self.path/'lifecycle'),name],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  print(p.stdout.strip())
 def test_empty_locked(self): self.run_case('empty_locked')
 def test_empty_immediate(self): self.run_case('empty_immediate')
 def test_live_immediate(self): self.run_case('live_immediate')
 def test_live_delayed(self): self.run_case('live_delayed')
 def test_live_never(self): self.run_case('live_never')
 def test_host_delayed(self): self.run_case('host_delayed')
 def test_host_never(self): self.run_case('host_never')
 def test_deinit_failed(self): self.run_case('deinit_failed')
 def test_callbacks_delayed(self): self.run_case('callbacks_delayed')
 def test_callbacks_never(self): self.run_case('callbacks_never')
 def test_cancel(self): self.run_case('cancel')
 def test_ble_restarts(self): self.run_case('ble_restarts')
 def test_allocation_failure(self): self.run_case('allocation_failure')
 def test_empty_stop_locked(self): self.run_case('empty_stop_locked')
 def test_reap(self): self.run_case('reap')
 def test_wifi_ok(self): self.run_case('wifi_ok')
 def test_wifi_filter_fail(self): self.run_case('wifi_filter_fail')
 def test_wifi_callback_fail(self): self.run_case('wifi_callback_fail')
 def test_wifi_enable_fail(self): self.run_case('wifi_enable_fail')
 def test_wifi_cancelled(self): self.run_case('wifi_cancelled')
 def test_status(self): self.run_case("status")

class WardriveStartupNoPsram(WardriveStartupProduction):
 HAS_PSRAM=0
