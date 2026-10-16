"""Extracted production worker ownership and failure contracts; no hardware claim."""
from pathlib import Path
import os, subprocess, tempfile, unittest
from test_sd_psram_led_capabilities import body
ROOT=Path(__file__).resolve().parents[1]
MAIN=Path(os.environ.get("CYM_SD_TEST_SOURCE",str(ROOT/"ESP32C5/main/main.c")))
PRE=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_INTERNAL 2
#define MALLOC_CAP_8BIT 4
#define SD_PROV_STACK_BYTES 4096
#define pdTRUE 1
#define eSuspended 3
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
typedef uint8_t StackType_t;
typedef int StaticTask_t;
typedef void *TaskHandle_t;
typedef void *QueueHandle_t;
typedef struct {char line[96];} sd_prov_update_t;
static QueueHandle_t sd_prov_queue;
static StackType_t *sd_provision_task_stack;
static StaticTask_t sd_provision_task_buf;
static TaskHandle_t sd_provision_task_handle;
static volatile bool sd_provision_active;
static char sd_prov_summary[96];
static bool sd_prov_failed;
static int state,fail,allocs,frees,queues,deletes,task_deletes,caps_seen;
static size_t total;
static size_t heap_caps_get_total_size(int caps){assert(caps==1);return total;}
static void *heap_caps_malloc(size_t n,int caps){assert(n==4096);caps_seen=caps;if(fail==1)return NULL;allocs++;return malloc(n);}
static void heap_caps_free(void *p){assert(p);frees++;free(p);}
static void *xQueueCreate(int n,size_t z){assert(n==32&&z==96);if(fail==2)return NULL;queues++;return (void*)2;}
static void vQueueDelete(void *q){assert(q==(void*)2);deletes++;}
static int xPortGetCoreID(void){return 0;}
static void sd_provision_task(void *p){(void)p;}
static void *xTaskCreateStaticPinnedToCore(void(*f)(void*),const char*n,int bytes,void*p,int pri,StackType_t*s,StaticTask_t*t,int core){assert(f==sd_provision_task&&strcmp(n,"sd_prov")==0&&bytes==4096&&pri==2&&s&&t&&core==0);(void)p;return fail==3?NULL:(void*)3;}
static int eTaskGetState(void *h){assert(h==(void*)3);return state;}
static void vTaskDelete(void *h){assert(h==(void*)3&&state==eSuspended);task_deletes++;}
"""
class SdNoPsram305(unittest.TestCase):
 def test_native_allocation_failures_repeated_runs_and_quiescence(self):
  s=MAIN.read_text()
  start=body(s,"sd_prov_start_worker");reap=body(s,"sd_prov_reap_worker")
  program=PRE+"static bool sd_prov_start_worker(bool after_format){"+start+"}\
static bool sd_prov_reap_worker(void){"+reap+"}\
"+r"""
int main(void){
 for(int ram=0;ram<2;ram++)for(fail=0;fail<4;fail++)for(int run=0;run<20;run++){
  total=ram?8388608:0;state=0;
  int a=allocs,f=frees,q=queues,d=deletes,td=task_deletes;
  bool started=sd_prov_start_worker(run%2);
  assert(started==(fail==0));
  if(fail!=2)assert(caps_seen==(ram?MALLOC_CAP_SPIRAM:(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)));
  if(started){
   assert(sd_provision_active);assert(!sd_prov_start_worker(false));
   assert(!sd_prov_reap_worker());assert(frees==f&&deletes==d);
   state=eSuspended;assert(sd_prov_reap_worker());assert(!sd_prov_reap_worker());
   assert(task_deletes==td+1);
  }
  assert(!sd_provision_active&&!sd_prov_queue&&!sd_provision_task_stack&&!sd_provision_task_handle);
  assert(allocs-a==frees-f&&queues-q==deletes-d);
 }
 return 0;
}
"""
  with tempfile.TemporaryDirectory(dir=os.environ.get("CYM_WD_TEST_TMPDIR")) as d:
   p=Path(d);(p/"host.c").write_text(program)
   subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror",str(p/"host.c"),"-o",str(p/"host")],check=True)
   subprocess.run([str(p/"host")],check=True)
 def test_worker_has_no_lvgl_or_completion_allocation(self):
  s=MAIN.read_text();b=body(s,"sd_provision_task")
  self.assertNotIn("lv_async_call",b);self.assertNotIn("malloc(64)",b)
  self.assertIn("vTaskSuspend(NULL)",b);self.assertNotIn("vTaskDelete(NULL)",b)
  self.assertIn("uxTaskGetStackHighWaterMark(NULL)",b)
  self.assertIn("sd_prov_failed = true",b)
 def test_stack_byte_accounting_and_screen_stop(self):
  s=MAIN.read_text();self.assertIn("#define SD_PROV_STACK_BYTES 4096",s)
  self.assertIn("sizeof(StackType_t) == 1",s)
  b=body(s,"show_sd_provision_running_screen")
  self.assertIn("g_screen_stop_fn = sd_prov_screen_stop",b)
  for p in ["sd_provision_log_ta","sd_provision_status_label","sd_prov_back_btn"]:
   self.assertIn(p+" = NULL",body(s,"sd_prov_screen_stop"))
 def test_preallocated_resources_before_format(self):
  s=MAIN.read_text();b=body(s,"sd_prov_start_worker")
  self.assertLess(b.index("xQueueCreate"),b.index("xTaskCreateStaticPinnedToCore"))
  self.assertLess(b.index("heap_caps_malloc"),b.index("xTaskCreateStaticPinnedToCore"))
  self.assertNotIn("xQueueCreate",body(s,"sd_provision_task"))
  self.assertIn("wifi_wardrive_format_sd()",body(s,"sd_provision_task"))
  for n in ["show_sd_format_confirm1","show_sd_format_confirm2"]: self.assertIn("create_function_page_base",body(s,n))
  # The production screens bind NO at each stage and YES to the next stage.
  for name,yes in [("show_sd_format_confirm1","sd_format_confirm1_yes_cb"),("show_sd_format_confirm2","sd_format_confirm2_yes_cb")]:
   self.assertIn("sd_back_to_menu_cb",body(s,name));self.assertIn(yes,body(s,name))
  program=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#define ESP_LOGI(...) ((void)0)
typedef struct {void *data;} lv_event_t;
static bool sd_prov_pending_start,sd_prov_pending_after_format;
static int menu,second,launch;
static void *lv_event_get_user_data(lv_event_t *e){return e->data;}
static void show_sd_card_screen(void){menu++;}
static void show_sd_format_confirm2(void){second++;}
static void show_sd_provision_running_screen(bool f){assert(f);launch++;}
"""
  for name in ["sd_back_to_menu_cb","sd_prov_confirm_no_cb","sd_prov_confirm_yes_cb","sd_format_confirm1_yes_cb","sd_format_confirm2_yes_cb"]:
   program+="static void "+name+"(lv_event_t *e){"+body(s,name)+"}\n"
  program+=r"""
int main(void){
 lv_event_t e={0};
 sd_back_to_menu_cb(&e);assert(menu==1&&!second&&!launch&&!sd_prov_pending_start);
 sd_format_confirm1_yes_cb(&e);assert(second==1&&!launch);
 sd_back_to_menu_cb(&e);assert(menu==2&&!launch);
 sd_format_confirm1_yes_cb(&e);sd_format_confirm2_yes_cb(&e);assert(second==2&&launch==1);
 sd_prov_confirm_no_cb(&e);assert(menu==3&&!sd_prov_pending_start);
 sd_prov_confirm_yes_cb(&e);assert(sd_prov_pending_start&&!sd_prov_pending_after_format);
 sd_prov_pending_start=false;e.data=(void*)1;sd_prov_confirm_yes_cb(&e);
 assert(sd_prov_pending_start&&sd_prov_pending_after_format);return 0;
}
"""
  with tempfile.TemporaryDirectory(dir=os.environ.get("CYM_WD_TEST_TMPDIR")) as d:
   p=Path(d);(p/"consent.c").write_text(program)
   subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror",str(p/"consent.c"),"-o",str(p/"consent")],check=True)
   subprocess.run([str(p/"consent")],check=True)
 def test_truthful_manual_fallback_and_failure_status(self):
  s=MAIN.read_text();copy=s[s.index("static const char SD_MANUAL_SETUP_TEXT"):s.index("static void sd_manual_setup_ok_cb")]
  self.assertNotIn("No files have been changed",copy);self.assertNotIn("This device has no PSRAM",copy)
  self.assertIn("sd_prov_summary",body(s,"sd_prov_finish_ui"));self.assertIn("sd_prov_failed",body(s,"sd_prov_finish_ui"))
 def test_same_shared_handler_and_additive_items(self):
  s=MAIN.read_text();items=s[s.index("static const sd_provision_item_t SD_ITEMS"):s.index("#define SD_ITEMS_COUNT")]
  import re
  self.assertEqual(len(re.findall(r"\{ SD_ITEM_(?:DIR|FILE),",items)),62)
  self.assertGreaterEqual(s.count("show_sd_card_screen();"),2)
  b=body(s,"sd_prov_do_item");self.assertIn("fwrite",b);self.assertIn("fclose",b)
  self.assertIn("EIO",b);self.assertIn("sd_prov_failed = true",b)


IO_PRE=r"""
#include <stdio.h>
#include <errno.h>
#include <sys/stat.h>
#include <stdarg.h>
#include <setjmp.h>
#define ESP_LOGW(...) ((void)0)
#define CYM_DEBUG_LOGD(...) ((void)0)
#define ESP_OK 0
#define pdMS_TO_TICKS(x) (x)
#define SD_ITEMS_COUNT 2
#define PROV_TAKE_MUTEX() (mutex_ok)
#define PROV_POST(...) ((void)0)
typedef int esp_err_t;
typedef enum {SD_ITEM_DIR,SD_ITEM_FILE} sd_item_type_t;
typedef struct {sd_item_type_t type;const char *path,*content;} sd_provision_item_t;
static const sd_provision_item_t SD_ITEMS[]={{SD_ITEM_DIR,"/sdcard/lab",NULL},{SD_ITEM_FILE,"/sdcard/lab/config/config.conf","seed"}};
static void *sd_spi_mutex=(void*)4;
static bool mutex_ok=true;
static int fault_io,existing,wrong_type,format_rc,mount_rc,format_calls,mount_calls,writes,closes,opens,watch_del;
static jmp_buf finished;
static uint64_t esp_timer_get_time(void){static uint64_t t;return t+=1000;}
static void xSemaphoreGive(void *p){assert(p==sd_spi_mutex);}
static int host_stat(const char*p,struct stat*st){(void)p;if(existing){st->st_mode=wrong_type?S_IFCHR:S_IFREG;return 0;}errno=fault_io==1?EIO:ENOENT;return -1;}
static int host_mkdir(const char*p,int mode){(void)p;(void)mode;if(fault_io==2){errno=EIO;return -1;}return 0;}
static FILE *host_fopen(const char*p,const char*m){(void)p;(void)m;opens++;if(fault_io==3){errno=EIO;return NULL;}return (FILE*)5;}
static size_t host_fwrite(const void*p,size_t z,size_t n,FILE*f){(void)p;assert(z==1&&f==(FILE*)5);writes++;return fault_io==4?n-1:n;}
static int host_fclose(FILE*f){assert(f==(FILE*)5);closes++;return fault_io==5?-1:0;}
static int host_fprintf(FILE*f,const char*fmt,...){(void)f;(void)fmt;return 0;}
static int host_fflush(FILE*f){(void)f;return 0;}
#define stat(p,s) host_stat(p,s)
#define mkdir host_mkdir
#define fopen host_fopen
#define fwrite host_fwrite
#define fclose host_fclose
#define fprintf host_fprintf
#define fflush host_fflush
static int esp_task_wdt_add(void*p){(void)p;return 0;}
static int esp_task_wdt_reset(void){return 0;}
static int esp_task_wdt_delete(void*p){(void)p;watch_del++;return 0;}
static int uxTaskPriorityGet(void*p){(void)p;return 2;}
static void vTaskDelay(int n){(void)n;}
static int wifi_wardrive_format_sd(void){assert(sd_prov_queue&&sd_provision_task_stack);format_calls++;return format_rc;}
static int wifi_wardrive_init_sd(void){mount_calls++;return mount_rc;}
static int xQueueSend(void*q,const void*p,int t){(void)q;(void)p;(void)t;return 1;}
static unsigned uxTaskGetStackHighWaterMark(void*p){(void)p;return 777;}
static void vTaskSuspend(void*p){assert(!p);longjmp(finished,1);}
"""
class SdWorkerExecution305(unittest.TestCase):
 def test_real_items_and_worker_error_summary_format_order(self):
  s=MAIN.read_text()
  # SDK/filesystem boundaries are stubbed; actual item and orchestration bodies run.
  pre=PRE[:PRE.index("static void sd_provision_task(void *p)")]
  program=pre+IO_PRE+"static void sd_prov_do_item(const sd_provision_item_t *item,int idx,int *created,int *ok_count,uint64_t task_start_us,char *batch_buffer,size_t batch_size,int *batch_len){"+body(s,"sd_prov_do_item")+"}\nstatic void sd_provision_task(void *pvParams){"+body(s,"sd_provision_task")+"}\n"+r"""
int main(void){
 char batch[1024];int n,c,o;
 for(fault_io=0;fault_io<=5;fault_io++){
  n=c=o=0;sd_prov_failed=false;mutex_ok=true;existing=0;writes=closes=opens=0;
  sd_prov_do_item(&SD_ITEMS[fault_io==2?0:1],0,&c,&o,0,batch,sizeof(batch),&n);
  assert(sd_prov_failed==(fault_io!=0));assert(c==(fault_io==0)&&o==0);
  if(fault_io==4||fault_io==5)assert(writes==1&&closes==1);
 }
 fault_io=0;existing=1;wrong_type=0;n=c=o=0;sd_prov_failed=false;opens=0;
 sd_prov_do_item(&SD_ITEMS[1],0,&c,&o,0,batch,sizeof(batch),&n);
 assert(o==1&&c==0&&!sd_prov_failed&&opens==0);
 wrong_type=1;sd_prov_do_item(&SD_ITEMS[1],0,&c,&o,0,batch,sizeof(batch),&n);assert(sd_prov_failed&&opens==0);
 existing=0;wrong_type=0;mutex_ok=false;sd_prov_failed=false;
 sd_prov_do_item(&SD_ITEMS[1],0,&c,&o,0,batch,sizeof(batch),&n);assert(sd_prov_failed);
 sd_prov_queue=(void*)2;sd_provision_task_stack=(void*)6;
 for(int scenario=0;scenario<6;scenario++){
  format_calls=mount_calls=watch_del=0;format_rc=scenario==2?1:0;mount_rc=scenario==3?1:0;
  mutex_ok=scenario!=4;fault_io=scenario==5?4:0;sd_prov_failed=false;
  if(!setjmp(finished))sd_provision_task((void*)(uintptr_t)(scenario!=0));
  assert(watch_del==1);assert(!strncmp(sd_prov_summary,scenario<2?"Done":"Failed",scenario<2?4:6));
  assert(format_calls==(scenario!=0&&scenario!=4));
  assert(mount_calls==(scenario!=0&&scenario!=2&&scenario!=4));
 }
 return 0;
}
"""
  with tempfile.TemporaryDirectory(dir=os.environ.get("CYM_WD_TEST_TMPDIR")) as d:
   p=Path(d);(p/"host.c").write_text(program)
   subprocess.run(["cc","-std=gnu11","-Wno-unused-function","-Wno-unused-variable",str(p/"host.c"),"-o",str(p/"host")],check=True)
   subprocess.run([str(p/"host")],check=True)
 def test_main_only_finish_ui_and_deleted_screen(self):
  s=MAIN.read_text()
  program=r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#define COLOR_MATERIAL_RED 1
#define COLOR_MATERIAL_GREEN 2
#define COLOR_MATERIAL_TEAL 3
#define LV_STATE_DISABLED 4
#define LV_STATE_DEFAULT 0
static void *sd_provision_log_ta=(void*)1,*sd_provision_status_label=(void*)2,*sd_prov_back_btn=(void*)3;
static bool sd_prov_failed;
static char sd_prov_summary[96]="Failed - insufficient worker resources";
static int updates,color,enabled;
static void lv_label_set_text(void*p,const char*s){assert(p==(void*)2&&s==sd_prov_summary);updates++;}
static void lv_obj_set_style_text_color(void*p,int c,int state){assert(p==(void*)2&&!state);color=c;}
static void lv_obj_clear_state(void*p,int s){assert(p==(void*)3&&s==LV_STATE_DISABLED);enabled++;}
static void lv_obj_set_style_bg_color(void*p,int c,int s){assert(p==(void*)3&&c==3&&!s);}
"""+"static void sd_prov_finish_ui(void){"+body(s,"sd_prov_finish_ui")+"}\nstatic void sd_prov_screen_stop(void){"+body(s,"sd_prov_screen_stop")+"}\n"+r"""
int main(void){
 sd_prov_failed=true;sd_prov_finish_ui();assert(updates==1&&enabled==1&&color==1);
 sd_prov_failed=false;sd_prov_finish_ui();assert(updates==2&&enabled==2&&color==2);
 sd_prov_screen_stop();assert(!sd_provision_log_ta&&!sd_provision_status_label&&!sd_prov_back_btn);
 sd_prov_finish_ui();assert(updates==2&&enabled==2);return 0;
}
"""
  with tempfile.TemporaryDirectory(dir=os.environ.get("CYM_WD_TEST_TMPDIR")) as d:
   p=Path(d);(p/"host.c").write_text(program)
   subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror",str(p/"host.c"),"-o",str(p/"host")],check=True)
   subprocess.run([str(p/"host")],check=True)
