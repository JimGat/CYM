"""Execute production QR UI start/worker/reap/stop against deterministic SDK doubles.
The allocation profile comes from the owner's USB diagnostics, not a parallel
lifecycle model. A done publication and an actual task suspension are separate.
"""
from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
PRE=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <setjmp.h>
#include <errno.h>
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_SPIRAM 2
#define MALLOC_CAP_8BIT 4
#define MALLOC_CAP_DMA 8
#define pdTRUE 1
#define pdFALSE 0
#define pdPASS 1
#define pdMS_TO_TICKS(x) (x)
#define configNUMBER_OF_CORES 1
#define CONFIG_FREERTOS_UNICORE 1
#define CONFIG_IDF_TARGET_ESP32C5 1
#define CONFIG_FREERTOS_TASK_CREATE_ALLOW_EXT_MEM 1
#define CYM_QR_MAX_PAYLOAD 8896
#define ESP_OK 0
#define ESP_ERR_NO_MEM 1
#define ESP_FAIL 2
#define ESP_ERR_TIMEOUT 3
#define ESP_ERR_INVALID_RESPONSE 4
#define CYM_CAMERA_RGB565_LE 0
#define LV_STATE_PRESSED 1
#define LV_STATE_DISABLED 2
#define LV_PART_SCROLLBAR 1
#define LV_OBJ_FLAG_HIDDEN 1
#define LV_OBJ_FLAG_SCROLLABLE 2
#define LV_IMG_CF_TRUE_COLOR 1
#define LV_ALIGN_BOTTOM_MID 0
#define LV_FLEX_FLOW_COLUMN 0
#define LV_DIR_VER 0
#define LV_SCROLLBAR_MODE_AUTO 0
#define LV_LABEL_LONG_WRAP 0
#define LV_EVENT_CLICKED 0
#define LV_LOG_USER(...) ((void)0)
typedef int esp_err_t;
typedef int lv_color_t;
typedef int lv_font_t;
typedef struct {int unused;} lv_obj_t;
typedef struct {int unused;} lv_timer_t;
typedef struct {int unused;} lv_event_t;
typedef struct {struct {int cf,w,h;} header;size_t data_size;const uint8_t *data;} lv_img_dsc_t;
typedef struct {uint8_t bytes[96];} StaticTask_t;
typedef uint8_t StackType_t;
typedef void (*TaskFunction_t)(void*);
typedef struct {int state;TaskFunction_t fn;void *arg;} task;
typedef task *TaskHandle_t;
typedef void *SemaphoreHandle_t;
typedef int BaseType_t;
typedef unsigned UBaseType_t;
enum {eRunning,eReady,eSuspended};
typedef struct {int x;} cym_camera_t;
typedef struct {int x;} cym_qr_t;
typedef struct {uint8_t *data;size_t stride;int width,height;int format;} cym_camera_frame_t;
typedef int (*qr_ui_save_fn)(const uint8_t*,size_t,char*,size_t);
typedef bool (*qr_ui_capture_valid_fn)(void *);
typedef int (*qr_ui_frame_save_fn)(const uint8_t *,int,int,size_t,const char *,char *,size_t,qr_ui_capture_valid_fn,void *);
typedef struct {unsigned rotation;lv_color_t panel,card,pressed,border,text,muted,accent;const lv_font_t *font;qr_ui_frame_save_fn save_frame;} qr_ui_options_t;
#define CYM_QR_ERROR_COUNT 8
typedef struct {uint32_t candidates,normal_attempts,mirror_attempts,valid,payload_length;uint32_t errors[8];} cym_qr_stats_t;
static int64_t esp_timer_get_time(void){static int64_t t;return t+=10000;}
static int debug_on,diag_calls,open_calls,close_fail,create_fail,live,deletes,ticks,finish_at;
static int stop_before_suspend,hold_camera,scan_success,save_error,save_calls,frame_calls,frame_error,acquire_error;
static const uint8_t *test_payload=(const uint8_t*)"x";static size_t test_length=1;
static size_t internal_free=4734,internal_largest=2304,psram_free=5723232,psram_largest=5636096;
static task fake_task;
static jmp_buf parked;
static struct {void *p;size_t n;unsigned caps;} allocs[128];
static void *heap_caps_malloc(size_t n,unsigned caps){
 size_t *f=(caps&MALLOC_CAP_INTERNAL)?&internal_free:&psram_free;
 size_t largest=(caps&MALLOC_CAP_INTERNAL)?internal_largest:psram_largest;
 if(n>*f||n>largest)return NULL;
 void *p=calloc(1,n);assert(p);*f-=n;
 for(int i=0;i<128;i++)if(!allocs[i].p){allocs[i].p=p;allocs[i].n=n;allocs[i].caps=caps;live++;return p;}
 abort();
}
static void *heap_caps_calloc(size_t n,size_t m,unsigned caps){return heap_caps_malloc(n*m,caps);}
static void host_free(void *p){if(!p)return;for(int i=0;i<128;i++)if(allocs[i].p==p){if(allocs[i].caps&MALLOC_CAP_INTERNAL)internal_free+=allocs[i].n;else psram_free+=allocs[i].n;allocs[i].p=NULL;live--;free(p);return;}assert(!"unknown/double free");}
#define free host_free
static size_t heap_caps_get_free_size(unsigned caps){return caps&MALLOC_CAP_SPIRAM?psram_free:internal_free;}
static size_t heap_caps_get_largest_free_block(unsigned caps){return caps&MALLOC_CAP_SPIRAM?psram_largest:internal_largest;}
static bool cym_debug_enabled(void){return debug_on;}
static uint32_t debug_generation=2;
static uint32_t cym_debug_generation(void){return debug_generation;}
static char diagnostics[16384];
#define ESP_LOGI(tag,fmt,...) do { (void)(tag);size_t at=strlen(diagnostics);snprintf(diagnostics+at,sizeof(diagnostics)-at,fmt "\n",__VA_ARGS__);diag_calls++; } while(0)
static bool esp_ptr_external_ram(const void *p){for(int i=0;i<128;i++)if(allocs[i].p==p)return allocs[i].caps&MALLOC_CAP_SPIRAM;return false;}
static unsigned uxTaskGetStackHighWaterMark(TaskHandle_t t){(void)t;return 13000;}
static const char *esp_err_to_name(int e){(void)e;return "TEST_ERROR";}
static BaseType_t xTaskCreate(TaskFunction_t f,const char*n,unsigned bytes,void*a,unsigned prio,TaskHandle_t*out){(void)f;(void)n;(void)a;(void)prio;(void)out;void*p=heap_caps_malloc(bytes,MALLOC_CAP_INTERNAL);if(!p)return 0;free(p);return 1;}
static TaskHandle_t xTaskCreateStatic(TaskFunction_t f,const char*n,unsigned bytes,void*a,unsigned prio,StackType_t*stack,StaticTask_t*tcb){(void)n;(void)prio;assert(bytes==24576&&esp_ptr_external_ram(stack));assert(!esp_ptr_external_ram(tcb));if(create_fail)return NULL;fake_task=(task){eReady,f,a};return &fake_task;}
static int eTaskGetState(TaskHandle_t t){assert(t);return t->state;}
static void vTaskDelete(TaskHandle_t t){assert(t==&fake_task&&t->state==eSuspended);deletes++;t->state=-1;}
static void vTaskSuspend(TaskHandle_t t){assert(!t);if(!stop_before_suspend)fake_task.state=eSuspended;longjmp(parked,1);}
static void run_worker(void){assert(fake_task.fn);fake_task.state=eRunning;if(!setjmp(parked))fake_task.fn(fake_task.arg);}
static void vTaskDelay(unsigned n){(void)n;ticks++;if(finish_at&&ticks==finish_at)run_worker();}
static SemaphoreHandle_t xSemaphoreCreateMutex(void){return heap_caps_malloc(80,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);}
static void vSemaphoreDelete(void*p){free(p);}
static int xSemaphoreTake(void*p,unsigned t){(void)p;(void)t;return 1;}
static void xSemaphoreGive(void*p){(void)p;}
static int cym_camera_open(cym_camera_t **c,void*b){(void)b;open_calls++;if(hold_camera||scan_success)*c=(void*)1;return scan_success?0:ESP_FAIL;}
static int cym_camera_close(cym_camera_t **c){if(close_fail)return ESP_FAIL;*c=NULL;return 0;}
static int cym_camera_acquire(cym_camera_t*c,cym_camera_frame_t*f,unsigned ms){(void)c;(void)ms;if(acquire_error)return acquire_error;static uint8_t rgb[153600];*f=(cym_camera_frame_t){rgb,480,240,320};return 0;}
static void cym_camera_release(cym_camera_t*c){(void)c;}
static cym_qr_t *cym_qr_create(int w,int h){(void)w;(void)h;return (void*)1;}
static void cym_qr_destroy(cym_qr_t*q){(void)q;}
static void cym_qr_rgb565_gray(const void*a,size_t b,void*c,int d,int e){(void)a;(void)b;(void)c;(void)d;(void)e;}
static int cym_qr_decode_gray(cym_qr_t*a,void*b,int c,uint8_t*d,int e){(void)a;(void)b;(void)c;(void)e;memcpy(d,test_payload,test_length);return (int)test_length;}
static size_t cym_qr_escape(const uint8_t *data,size_t len,char *out,size_t cap);

static int cym_qr_decode_gray_ex(cym_qr_t*a,void*b,int c,uint8_t*d,int e,cym_qr_stats_t *stats){memset(stats,0,sizeof(*stats));stats->valid=stats->candidates=stats->normal_attempts=stats->errors[0]=1;stats->payload_length=test_length;return cym_qr_decode_gray(a,b,c,d,e);}
static lv_obj_t obj;
#define lv_obj_set_style_bg_color(...) ((void)0)
#define lv_obj_set_style_text_color(...) ((void)0)
#define lv_obj_set_style_text_font(...) ((void)0)
#define lv_obj_set_style_radius(...) ((void)0)
#define lv_obj_set_style_pad_all(...) ((void)0)
#define lv_obj_set_style_pad_gap(...) ((void)0)
#define lv_obj_add_state(...) ((void)0)
#define lv_obj_clear_state(...) ((void)0)

#define lv_label_create(...) (&obj)
#define lv_obj_create(...) (&obj)
#define lv_img_create(...) (&obj)
#define lv_btn_create(...) (&obj)
#define lv_obj_set_width(...) ((void)0)
#define lv_obj_set_height(...) ((void)0)
#define lv_obj_align(...) ((void)0)
#define lv_obj_set_flex_flow(...) ((void)0)
#define lv_obj_set_scroll_dir(...) ((void)0)
#define lv_obj_set_scrollbar_mode(...) ((void)0)
#define lv_label_set_long_mode(...) ((void)0)
#define lv_label_set_recolor(...) ((void)0)
#define lv_img_set_src(...) ((void)0)
#define lv_img_cache_invalidate_src(...) ((void)0)
#define lv_obj_set_style_border_width(...) ((void)0)
#define lv_obj_set_style_border_color(...) ((void)0)
#define lv_obj_add_event_cb(...) ((void)0)
#define lv_timer_create(...) ((lv_timer_t*)&obj)
#define lv_timer_del(...) ((void)0)
#define lv_obj_invalidate(...) ((void)0)
#define lv_obj_add_flag(...) ((void)0)
#define lv_obj_clear_flag(...) ((void)0)
static char displayed[256];
static void lv_label_set_text(lv_obj_t*p,const char*s){(void)p;snprintf(displayed,sizeof(displayed),"%s",s);}
#define lv_label_set_text_static lv_label_set_text
"""
POST=r"""
static int save(const uint8_t*p,size_t n,char*out,size_t cap){save_calls++;assert(atomic_load(&session->phase)==QR_SAVING);poll(NULL);assert(strstr(displayed,"Saving"));assert(n==test_length&&!memcmp(p,test_payload,n));snprintf(out,cap,"test.txt");return save_error;}
static int frame_save(const uint8_t *gray,int w,int h,size_t stride,const char *meta,char *name,size_t cap,qr_ui_capture_valid_fn valid,void *ctx){assert(valid(ctx));assert(esp_ptr_external_ram(gray));assert(w==240&&h==320&&stride==240);assert(strstr(meta,"decoder_rotation=0"));assert(cym_debug_enabled());frame_calls++;snprintf(name,cap,"frame-0000.pgm");return frame_error;}
static void reset(void){assert(!session&&!live);internal_free=4734;internal_largest=2304;psram_free=5723232;psram_largest=5636096;create_fail=close_fail=hold_camera=scan_success=stop_before_suspend=finish_at=ticks=save_error=save_calls=frame_calls=frame_error=acquire_error=0;test_payload=(const uint8_t*)"x";test_length=1;}
static void start_open(void){qr_ui_options_t opts={.save_frame=frame_save};qr_decoder_ui_open(&obj,(void*)1,save,&opts);}
int main(void){
 reset();start_open();assert(session&&atomic_load(&session->phase)==QR_STARTING);assert(!open_calls); /* RED: dynamic internal 24KB fails here */
 run_worker();poll(NULL);assert(atomic_load(&session->done));qr_decoder_ui_stop();assert(!session&&!live&&deletes==1);
 /* Partial start failures must release allocations, permit retry, no extra task. */
 reset();start_open();run_worker();poll(NULL);psram_largest=20000;retry(NULL);assert(session&&atomic_load(&session->phase)==QR_ERROR);qr_decoder_ui_stop();assert(!session&&!live);
 reset();start_open();run_worker();poll(NULL);size_t base=internal_free;internal_largest=64;retry(NULL);assert(atomic_load(&session->phase)==QR_ERROR);assert(internal_free==base);internal_largest=2304;retry(NULL);assert(atomic_load(&session->phase)==QR_STARTING);run_worker();qr_decoder_ui_stop();assert(!session&&!live);
 reset();create_fail=1;start_open();assert(atomic_load(&session->phase)==QR_ERROR);create_fail=0;retry(NULL);run_worker();qr_decoder_ui_stop();assert(!session&&!live);
 /* done is not a join: preempt immediately before self-suspension. */
 reset();start_open();stop_before_suspend=1;run_worker();int old=deletes;qr_decoder_ui_stop();assert(session&&ticks==300&&deletes==old&&live);start_open();assert(session&&deletes==old);retry(NULL);assert(deletes==old);poll(NULL);assert(deletes==old);fake_task.state=eSuspended;qr_decoder_ui_stop();assert(!session&&!live&&deletes==old+1);
 /* Stop/cancel before completion, bounded 3s, then later reopen/reap. */
 reset();start_open();finish_at=5;qr_decoder_ui_stop();assert(!session&&!live&&ticks==5);
 reset();start_open();qr_decoder_ui_stop();assert(session&&ticks==300&&atomic_load(&session->cancel));run_worker();start_open();assert(session&&atomic_load(&session->phase)==QR_STARTING);run_worker();qr_decoder_ui_stop();assert(!session&&!live);
 /* Successful capture/save, repeated reopen; no payload diagnostics. */
 for(int i=0;i<40;i++){reset();scan_success=1;start_open();run_worker();poll(NULL);assert(atomic_load(&session->phase)==QR_RESULT);qr_decoder_ui_stop();assert(!session&&!live);}
 reset();internal_free=4846;psram_free=5924276;start_open();run_worker();qr_decoder_ui_stop();assert(!session&&!live&&internal_free==4846&&psram_free==5924276);
 reset();debug_on=0;int logs=diag_calls;start_open();run_worker();qr_decoder_ui_stop();assert(diag_calls==logs);debug_on=1;start_open();run_worker();qr_decoder_ui_stop();assert(diag_calls>logs);assert(strstr(diagnostics,"stage=worker_enter stack_psram=1 stack_bytes=24576")&&strstr(diagnostics,"internal_largest=")&&strstr(diagnostics,"DMA_largest=")&&strstr(diagnostics,"psram_largest=")&&strstr(diagnostics,"stack_hwm="));
 reset();start_open();run_worker();poll(NULL);internal_largest=64;retry(NULL);assert(strstr(diagnostics,"stage=tcb_alloc error=1 caps=0x5 bytes=96"));qr_decoder_ui_stop();assert(!session&&!live);
 reset();start_open();run_worker();poll(NULL);psram_largest=20000;retry(NULL);assert(strstr(diagnostics,"stage=stack_alloc error=1 caps=0x6 bytes=24576"));qr_decoder_ui_stop();assert(!session&&!live);
 /* Real escape with long binary/inert content and empty payload. */
 reset();scan_success=1;uint8_t long_payload[8896];memset(long_payload,'#',sizeof(long_payload));memcpy(long_payload,"https://example.com/SYNTHETIC_PRIVATE",37);long_payload[40]=0;long_payload[41]=255;test_payload=long_payload;test_length=sizeof(long_payload);start_open();run_worker();poll(NULL);assert(atomic_load(&session->phase)==QR_RESULT);assert(strlen(session->text)==8902);assert(strstr(session->text,"\\x00\\xFF"));assert(!strstr(diagnostics,"SYNTHETIC_PRIVATE"));qr_decoder_ui_stop();assert(!session&&!live);
 reset();scan_success=1;test_length=0;start_open();run_worker();poll(NULL);assert(atomic_load(&session->phase)==QR_RESULT&&save_calls==1&&!session->text[0]);qr_decoder_ui_stop();assert(!session&&!live);
 /* No-frame timeout path remains bounded and emits one final aggregate. */
 reset();scan_success=1;acquire_error=ESP_ERR_TIMEOUT;start_open();run_worker();assert(session->timeouts==12&&session->frames==0&&session->processed==0);assert(atomic_load(&session->phase)==QR_ERROR);qr_decoder_ui_stop();assert(!session&&!live);
 reset();start_open();session->started=session->report_at=esp_timer_get_time();int before_logs=diag_calls;for(int i=0;i<100;i++)report(session,false);assert(diag_calls==before_logs);report(session,true);assert(diag_calls==before_logs+2);run_worker();qr_decoder_ui_stop();assert(!session&&!live);
 /* Slow/failed save retains immutable inert result; close failure retains owner. */
 reset();scan_success=1;save_error=ENOSPC;start_open();run_worker();assert(save_calls==1&&atomic_load(&session->phase)==QR_RESULT);assert(strstr(session->status,"Not saved"));assert(!strcmp(session->text,"x"));qr_decoder_ui_stop();assert(!session&&!live);
 reset();scan_success=1;close_fail=1;start_open();run_worker();poll(NULL);assert(atomic_load(&session->phase)==QR_RESULT&&session->camera);assert(strstr(session->status,"Camera stop incomplete"));assert(!strcmp(session->text,"x"));close_fail=0;session->camera=NULL;qr_decoder_ui_stop();assert(!session&&!live);
 /* Explicit capture is bounded, snapshot is PSRAM, debug-off cancels pending. */
 reset();debug_on=1;start_open();atomic_store(&session->phase,QR_SCANNING);request_capture(NULL);request_capture(NULL);assert(atomic_load(&session->capture)==1);cym_qr_stats_t stats={0};session->stride=480;capture_frame(session,&stats);assert(frame_calls==1&&atomic_load(&session->capture)==3);poll(NULL);assert(atomic_load(&session->capture)==0);
 request_capture(NULL);debug_on=0;capture_frame(session,&stats);assert(frame_calls==1&&atomic_load(&session->capture)==0);
 debug_on=1;request_capture(NULL);debug_generation+=2;capture_frame(session,&stats);assert(frame_calls==1&&atomic_load(&session->capture)==0);
 request_capture(NULL);atomic_store(&session->cancel,true);capture_frame(session,&stats);assert(frame_calls==1&&atomic_load(&session->capture)==0);atomic_store(&session->cancel,false);
 request_capture(NULL);psram_largest=100;capture_frame(session,&stats);assert(strstr(session->capture_status,"Frame not saved")&&frame_calls==1);psram_largest=5636096;poll(NULL);
 frame_error=ENODEV;request_capture(NULL);capture_frame(session,&stats);assert(frame_calls==2&&strstr(session->capture_status,"Frame not saved"));poll(NULL);frame_error=0;request_capture(NULL);capture_frame(session,&stats);assert(frame_calls==3&&strstr(session->capture_status,"Saved debug/"));
 run_worker();qr_decoder_ui_stop();assert(!session&&!live);
 /* Retained camera may own live ISR/DMA resources: only stack/TCB may reap. */
 reset();hold_camera=close_fail=1;start_open();run_worker();qr_decoder_ui_stop();assert(session&&session->camera&&live);old=open_calls;start_open();assert(strstr(displayed,"reboot required")&&open_calls==old);retry(NULL);assert(open_calls==old);
 close_fail=0;session->camera=NULL;qr_decoder_ui_stop();assert(!session&&!live);
 puts("PASS production QR lifecycle: low-memory start, failure/retry, delayed suspension, cancellation, retained camera, 40 reopens, debug gating");return 0;
}
"""
class Worker309(unittest.TestCase):
 def test_real_ui_low_memory_lifecycle(self):
  text=(ROOT/'ESP32C5/main/qr_decoder_ui.c').read_text()
  # SDK/LVGL boundaries are doubled; compile every actual production UI function.
  source='\n'.join(l for l in (ROOT/'ESP32C5/main/qr_preview.h').read_text().splitlines() if not l.startswith('#include') and not l.startswith('#pragma'))+'\n'+'\n'.join(l for l in text.splitlines() if not l.startswith('#include'))
  record=(ROOT/'ESP32C5/components/cym_qr/qr_record.c').read_text();source='static const char hex[]=\"0123456789ABCDEF\";\n'+record[record.index('size_t cym_qr_escape('):record.index('static int all(')]+'\n'+source
  helper=ROOT/'ESP32C5/main/qr_worker_lifecycle.h'
  if helper.exists():
   source='\n'.join(l for l in helper.read_text().splitlines() if not l.startswith('#include') and not l.startswith('#pragma'))+'\n'+source
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(PRE+'\n'+source+'\n'+POST)
   subprocess.run(['cc','-std=c11','-O1','-g','-fsanitize=undefined','-I',str(ROOT/'ESP32C5/main'),str(p/'test.c'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
