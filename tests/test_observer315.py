"""Execute production Observer ownership helpers with SDK boundary fault injection."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class Observer315(unittest.TestCase):
 def test_queue_task_ownership(self):
  header=ROOT/'ESP32C5/components/wifi_sniffer/include/observer_runtime.h'
  self.assertTrue(header.exists(), 'production Observer ownership helper not implemented')
  for psram in [0,1]:
   with self.subTest(psram=psram),tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'freertos').mkdir()
    (p/'esp_heap_caps.h').write_text('#define MALLOC_CAP_SPIRAM 1\n#define MALLOC_CAP_INTERNAL 2\n#define MALLOC_CAP_8BIT 4\n')
    (p/'esp_err.h').write_text('')
    for n in ['FreeRTOS.h','task.h','queue.h','idf_additions.h']:(p/'freertos'/n).write_text('')
    pre=r"""
#include <assert.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#define configNUMBER_OF_CORES 2
#define pdPASS 1
#define pdTRUE 1
#define ESP_OK 0
#define ESP_ERR_NO_MEM 1
#define ESP_ERR_INVALID_STATE 2
typedef int esp_err_t;
typedef struct {int state;} task;
typedef task* TaskHandle_t;
typedef unsigned char StackType_t;
typedef struct {int x;} StaticQueue_t;
typedef void* QueueHandle_t;
typedef void (*TaskFunction_t)(void*);
enum {eReady,eSuspended};
static task t;static int fail_alloc,fail_queue,fail_task,allocs,frees,created,deleted,resets;
static unsigned last_caps,last_depth;static void *payload;static size_t payload_bytes;
static void *heap_caps_malloc(size_t n,unsigned caps){last_caps=caps;if(fail_alloc)return NULL;void*p=calloc(1,n);assert(p);allocs++;return p;}
static void heap_caps_free(void*p){if(p){frees++;free(p);}}
static QueueHandle_t xQueueCreateStatic(unsigned depth,unsigned size,uint8_t*p,StaticQueue_t*c){assert(depth==32&&size==160&&c);payload=p;payload_bytes=depth*size;return fail_queue?NULL:c;}
static void xQueueReset(QueueHandle_t q){assert(q);resets++;}
static TaskHandle_t xTaskGetCurrentTaskHandleForCore(unsigned core){(void)core;return NULL;}
static int eTaskGetState(TaskHandle_t h){return h->state;}
static void vTaskDelete(TaskHandle_t h){assert(h&&h->state==eSuspended);deleted++;}
static void vTaskDeleteWithCaps(TaskHandle_t h){vTaskDelete(h);}
static int xTaskCreateWithCaps(TaskFunction_t f,const char*n,unsigned depth,void*a,unsigned pri,TaskHandle_t*out,unsigned caps){assert(f&&n&&!a&&pri==5);created++;last_depth=depth;last_caps=caps;if(fail_task){*out=NULL;return 0;}t.state=eReady;*out=&t;return pdPASS;}
"""
    post=r"""
static void worker(void*p){(void)p;}
int main(void){
 QueueHandle_t q=NULL;uint8_t*storage=NULL;StaticQueue_t control={0};
 fail_alloc=1;assert(observer_log_queue_init(&q,&storage,&control,160)==ESP_ERR_NO_MEM);assert(!q&&!storage);
 fail_alloc=0;fail_queue=1;assert(observer_log_queue_init(&q,&storage,&control,160)==ESP_ERR_NO_MEM);assert(!q&&!storage&&allocs==frees);
 fail_queue=0;assert(observer_log_queue_init(&q,&storage,&control,160)==ESP_OK);assert(payload==storage&&payload_bytes==5120&&last_caps==(observer_heap_caps()|MALLOC_CAP_8BIT));
 void*retained=storage;int n=allocs;
 for(int i=0;i<100;i++){assert(observer_log_queue_init(&q,&storage,&control,160)==ESP_OK);assert(storage==retained);((char*)payload)[5119]=42;}
 assert(allocs==n&&resets==100);heap_caps_free(storage);
 TaskHandle_t h=NULL;StackType_t*stack=NULL;
 fail_task=1;assert(observer_hopper_start(&h,worker,16384)==ESP_ERR_NO_MEM&&!h);
 fail_task=0;assert(observer_hopper_start(&h,worker,16384)==ESP_OK&&h);assert(last_depth==16384&&last_caps==(observer_heap_caps()|MALLOC_CAP_8BIT));
 assert(!observer_task_reap(&h,&stack,true)&&h&&deleted==0);assert(observer_hopper_start(&h,worker,4096)==ESP_ERR_INVALID_STATE);
 t.state=eSuspended;assert(observer_task_reap(&h,&stack,true)&&!h&&deleted==1);
 for(int i=0;i<100;i++){assert(observer_hopper_start(&h,worker,8192)==ESP_OK);t.state=eSuspended;assert(observer_task_reap(&h,&stack,true));}
 stack=heap_caps_malloc(8192,observer_heap_caps());h=&t;t.state=eReady;assert(!observer_task_reap(&h,&stack,false)&&stack);t.state=eSuspended;assert(observer_task_reap(&h,&stack,false)&&!h&&!stack);assert(allocs==frees);
 return 0;}
"""
    (p/'t.c').write_text(pre+'\n#include "'+str(header)+'"\n'+post)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-DCONFIG_BOARD_HAS_PSRAM='+str(psram),'-I'+d,str(p/'t.c'),'-o',str(p/'t')],check=True)
    subprocess.run([str(p/'t')],check=True)

class Session315(unittest.TestCase):
 def test_production_component_stop_release_reentry_and_failed_start(self):
  text=(ROOT/'ESP32C5/components/wifi_sniffer/wifi_sniffer.c').read_text()
  self.assertIn('esp_err_t wifi_sniffer_release_session(void)',text,'session allocations still retained on Home')
  from test_qr_ui_stop import body
  names=['sniffer_callbacks_idle','sniffer_rx_enter','sniffer_rx_leave','wifi_sniffer_start','wifi_sniffer_start_noscan','wifi_sniffer_stop','wifi_sniffer_release_session']
  # Extract exact production definitions; only SDK/radio boundaries are doubled.
  def fn(name):
   import re
   m=re.search(r'^(?:static )?(?:esp_err_t|bool|void) '+name+r'\([^\n]*\)\s*\{',text,re.M);assert m,name
   start=m.start();brace=text.index('{',start);depth=1;i=brace+1
   while depth:
    depth+=(text[i]=='{')-(text[i]=='}');i+=1
   return text[start:i]
  code=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#define ESP_OK 0
#define ESP_ERR_NO_MEM 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_TIMEOUT 3
#define ESP_FAIL 4
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define pdMS_TO_TICKS(x) (x)
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
#define MALLOC_CAP_INTERNAL 2
#define MALLOC_CAP_8BIT 4
#define MAX_SNIFFER_APS 4
#define MAX_PROBE_REQUESTS 4
#define WIFI_PROMIS_FILTER_MASK_MGMT 1
#define WIFI_PROMIS_FILTER_MASK_DATA 2
#define WIFI_SECOND_CHAN_NONE 0
typedef int esp_err_t;
typedef struct {int value;} sniffer_ap_t;
typedef struct {int value;} probe_request_t;
typedef struct {int filter_mask;} wifi_promiscuous_filter_t;
typedef void* TaskHandle_t;typedef unsigned char StackType_t;
static sniffer_ap_t *sniffer_aps;static probe_request_t *probe_requests;
static int sniffer_ap_count,probe_request_count,sniffer_packet_count,sniffer_selected_channels_count,g_shared_selected_count;
static uint8_t sniffer_selected_channels[8];static const uint8_t channel_list[]={1,6,11};
static bool sniffer_active,sniffer_scan_phase,sniffer_selected_mode,sniffer_channel_hop_paused;
static bool sniffer_dog_active;static TaskHandle_t sniffer_dog_task_handle;
static unsigned sniffer_rx_inflight;static bool sniffer_rx_enabled;static int sniffer_rx_mux;
static int sniffer_channel_index,sniffer_current_channel,sniffer_last_channel_hop;
static TaskHandle_t sniffer_channel_task_handle;
static void (*sniffer_new_client_cb)(void);
static int allocs,frees,alloc_call,fail_alloc,fail_task,task_busy,rx_registered,promisc,release_rx_on_delay;
static unsigned observer_heap_caps(void){return 6;}
static void* heap_caps_calloc(unsigned n,unsigned m,unsigned caps){assert(caps==6);alloc_call++;if(alloc_call==fail_alloc)return NULL;allocs++;return calloc(n,m);}
static void heap_caps_free(void*p){if(p){frees++;free(p);}}
static int esp_timer_get_time(void){return 1000;}
static int esp_wifi_set_promiscuous_filter(void*p){assert(p);return 0;}
static int esp_wifi_set_promiscuous(bool on){promisc=on;return 0;}
static void wifi_sniffer_packet_handler(void*a,int b){(void)a;(void)b;}
static int esp_wifi_set_promiscuous_rx_cb(void(*cb)(void*,int)){rx_registered=cb!=NULL;return 0;}
static void esp_wifi_set_channel(int c,int s){(void)c;(void)s;}
static void sniffer_set_channel_verified(int c){(void)c;}
static void sniffer_channel_hop_task(void*p){(void)p;}
static void sniffer_init_selected_networks(void){sniffer_ap_count=1;sniffer_selected_channels_count=1;sniffer_selected_channels[0]=6;}
static bool observer_task_reap(TaskHandle_t*h,StackType_t**s,bool caps){(void)s;assert(caps);if(task_busy)return false;*h=NULL;return true;}
static int observer_hopper_start(TaskHandle_t*h,void(*f)(void*),unsigned bytes){assert(f);assert(bytes==4096||bytes==8192||bytes==16384);if(fail_task)return ESP_ERR_NO_MEM;*h=(void*)1;return ESP_OK;}
static void vTaskDelay(unsigned ticks){(void)ticks;if(release_rx_on_delay)sniffer_rx_inflight=0;}
esp_err_t wifi_sniffer_stop(void);
"""+'\n'.join(fn(n) for n in names)+r"""
int main(void){
 fail_alloc=1;assert(wifi_sniffer_start()==ESP_ERR_NO_MEM);assert(!sniffer_aps&&!probe_requests);
 alloc_call=0;fail_alloc=2;assert(wifi_sniffer_start()==ESP_ERR_NO_MEM);assert(!sniffer_aps&&!probe_requests);
 fail_alloc=0;
 for(int mode=0;mode<3;mode++){
  g_shared_selected_count=mode==1;
  fail_task=1;assert((mode==2?wifi_sniffer_start_noscan():wifi_sniffer_start())==ESP_ERR_NO_MEM);assert(!sniffer_active&&!promisc&&!rx_registered&&!sniffer_channel_task_handle);
  assert(wifi_sniffer_release_session()==ESP_OK);assert(!sniffer_aps&&!probe_requests&&allocs==frees);
  fail_task=0;
  for(int i=0;i<10;i++){
   assert((mode==2?wifi_sniffer_start_noscan():wifi_sniffer_start())==ESP_OK);assert(sniffer_active&&sniffer_aps&&probe_requests);
   sniffer_ap_count=2;probe_request_count=3;sniffer_aps[0].value=42;
   assert(sniffer_rx_enter());task_busy=1;
   assert(wifi_sniffer_stop()==ESP_ERR_TIMEOUT);assert(sniffer_aps&&probe_requests);assert(!sniffer_rx_enter());
   assert(wifi_sniffer_release_session()==ESP_ERR_TIMEOUT);assert(sniffer_aps&&sniffer_aps[0].value==42);
   sniffer_rx_leave();task_busy=0;
   assert(wifi_sniffer_stop()==ESP_OK);assert(sniffer_ap_count==2&&probe_request_count==3&&sniffer_aps[0].value==42);
   assert(wifi_sniffer_release_session()==ESP_OK);assert(!sniffer_aps&&!probe_requests&&!sniffer_ap_count&&!probe_request_count&&allocs==frees);
  }
 }
 return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)
 def test_main_home_owns_release_after_ui_destroy(self):
  t=(ROOT/'ESP32C5/main/main.c').read_text()
  a=t.index('void show_menu(void)\n{');home=t[a:t.index('void show_function_page(',a)]
  self.assertIn('sniffer_session_leave();',home)
  self.assertLess(home.index('lv_obj_del(function_page)'),home.index('sniffer_session_leave();'))
  self.assertIn('sniffer_session_reap();',t)
  start=t[t.index('static void sniffer_yes_btn_cb(lv_event_t *e)\n{'):]
  self.assertIn('g_screen_stop_fn = sniffer_screen_stop;',start[:1800])
  self.assertNotIn('sniffer_sorted_indices = (int *)heap_caps_malloc(MAX_SNIFFER_APS * sizeof(int), MALLOC_CAP_SPIRAM)',t)

class MainLifecycle315(unittest.TestCase):
 def test_actual_main_stop_home_release_failure_and_reentry(self):
  text=(ROOT/'ESP32C5/main/main.c').read_text()
  import re
  def fn(name):
   m=re.search(r'^static (?:void|bool) '+name+r'\([^\n]*\)\s*\{',text,re.M);assert m,name
   start=m.start();i=text.index('{',start)+1;depth=1
   while depth:depth+=(text[i]=='{')-(text[i]=='}');i+=1
   return text[start:i]
  code=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdint.h>
#define ESP_OK 0
#define ESP_ERR_NO_MEM 1
#define ESP_ERR_INVALID_STATE 2
#define MALLOC_CAP_8BIT 4
#define MALLOC_CAP_INTERNAL 2
#define MALLOC_CAP_DMA 8
#define pdMS_TO_TICKS(x) (x)
#define ESP_LOGI(...) ((void)0)
typedef int esp_err_t;
typedef unsigned char StackType_t;
typedef void* TaskHandle_t;
static TaskHandle_t sniffer_task_handle;static StackType_t*sniffer_task_stack;static int sniffer_task_buffer;
static int *sniffer_sorted_indices,sniffer_sorted_count,sniffer_start_time,sniffer_last_sort_time;
static bool sniffer_initial_sort_done,sniffer_release_pending,sniffer_return_pending,sniffer_observe_mode,sniffer_ui_needs_refresh,sniffer_task_active;
static bool sniffer_ui_active;static int sniffer_observe_ap_index,sniffer_start_error;
static int busy,rx_busy,live,alloc_failure,create_failure,log_failure,release_calls,joined,clock_ticks;
static unsigned observer_heap_caps(void){return 6;}
static unsigned observer_stack_bytes(unsigned b){return b;}
static bool cym_debug_enabled(void){return false;}
static void heap_caps_free(void*p){if(p){live--;free(p);}}
static void *heap_caps_malloc(unsigned bytes,unsigned caps){assert(caps==6);if(alloc_failure)return NULL;live++;return calloc(1,bytes);}
static void sniffer_disable_log_capture(void){}
static int sniffer_enable_log_capture(void){return log_failure?ESP_ERR_NO_MEM:ESP_OK;}
static void wifi_sniffer_set_new_client_callback(void*p){assert(!p);}
static unsigned esp_timer_get_time(void){return ++clock_ticks;}
static void vTaskDelay(unsigned n){(void)n;}
static bool observer_task_reap(TaskHandle_t*h,StackType_t**s,bool caps){assert(!caps);if(*h&&busy)return false;if(*h)joined++;*h=NULL;heap_caps_free(*s);*s=NULL;return true;}
static void sniffer_task(void*p){(void)p;}
static TaskHandle_t xTaskCreateStatic(void(*f)(void*),const char*n,unsigned bytes,void*a,unsigned pri,StackType_t*s,void*tcb){assert(f&&n&&!a&&pri==5&&s&&tcb);assert(bytes==8192||bytes==16384);return create_failure?NULL:(void*)1;}
static int wifi_sniffer_release_session(void){release_calls++;return rx_busy?1:ESP_OK;}
static void sniffer_session_reap(void);
"""+'\n'.join(fn(n) for n in ['sniffer_worker_join','sniffer_worker_start','sniffer_session_reap','sniffer_session_leave'])+r"""
int main(void){
 for(int i=0;i<20;i++){
  sniffer_sorted_count=9;sniffer_initial_sort_done=true;
  assert(sniffer_worker_start(8192)&&sniffer_task_handle&&live==1);
  assert(!sniffer_sorted_count&&!sniffer_initial_sort_done);busy=1;
  assert(!sniffer_worker_join()&&sniffer_task_handle&&live==1);
  assert(!sniffer_worker_start(16384)&&sniffer_task_handle&&live==1); // no overwritten stack
  busy=0;assert(sniffer_worker_join()&&!sniffer_task_handle&&!live);
  sniffer_sorted_indices=heap_caps_malloc(32,6);sniffer_sorted_count=8;sniffer_initial_sort_done=true;
  /* Stop keeps view/sort allocations. Home waits for outstanding RX. */
  assert(sniffer_worker_join()&&sniffer_sorted_indices&&live==1);
  rx_busy=1;sniffer_session_leave();assert(sniffer_release_pending&&sniffer_sorted_indices&&live==1);
  assert(!sniffer_worker_start(8192)&&sniffer_release_pending&&live==1);
  rx_busy=0;sniffer_session_reap();assert(!sniffer_release_pending&&!sniffer_sorted_indices&&!live&&!sniffer_sorted_count&&!sniffer_initial_sort_done);
 }
 alloc_failure=1;assert(!sniffer_worker_start(8192)&&!live&&!sniffer_task_handle);alloc_failure=0;
 create_failure=1;assert(!sniffer_worker_start(8192)&&!live&&!sniffer_task_stack);create_failure=0;
 log_failure=1;assert(!sniffer_worker_start(8192)&&!live);log_failure=0;
 assert(sniffer_worker_start(16384));sniffer_task_active=false; // async startup failure parks, handle still owned
 assert(sniffer_worker_start(8192)&&live==1); // reaps failed instance before replacing
 sniffer_session_leave();assert(!live&&!sniffer_release_pending);assert(joined>0&&release_calls>0);return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)
 def test_classic_modern_home_back_contracts(self):
  text=(ROOT/'ESP32C5/main/main.c').read_text()
  self.assertIn('nav_to_menu_flag = true;',text[text.index('static void home_btn_event_cb(lv_event_t *e)\n{'):][:500])
  a=text.index('static void nav_back_cb(lv_event_t *e)\n{');back=text[a:text.index('static void create_function_page_base(',a)]
  self.assertIn('nav_deferred_show_fn = fn;',back);self.assertIn('nav_to_menu_flag = true;',back)
  a=text.index('static void go_home(void)\n{');self.assertIn('show_menu();',text[a:a+200])
  a=text.index('void show_menu(void)\n{');home=text[a:text.index('void show_function_page(',a)]
  self.assertIn('if (g_home_layout_4cat) show_category_home();',home);self.assertIn('else                    show_main_tiles();',home)
  self.assertIn('sniffer_session_leave();',home)
if __name__=='__main__':unittest.main()
