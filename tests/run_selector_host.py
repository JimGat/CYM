#!/usr/bin/env python3
"""Exercise complete production UI against real pinned LVGL; capture logical screens.
Engine/IDF peripherals mocked here; genuine engine/WAD/PCM gate is separate.
"""
from pathlib import Path
import subprocess,json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.hermes/doom-prototype/selector-host'
COMP=ROOT/'ESP32C5/components/cym_doom'
LVGL=ROOT/'ESP32C5/managed_components/lvgl__lvgl'
STUBS={
'esp_heap_caps.h':r"""#include <stdlib.h>
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_8BIT 2
#define MALLOC_CAP_INTERNAL 4
static inline void *heap_caps_calloc(size_t n,size_t s,int caps){(void)caps;return calloc(n,s);}
static inline size_t heap_caps_get_free_size(int caps){(void)caps;return 8*1024*1024;}
static inline size_t heap_caps_get_largest_free_block(int caps){(void)caps;return 8*1024*1024;}
""",
'esp_timer.h':r"""#include <stdint.h>
extern int64_t fake_us;
static inline int64_t esp_timer_get_time(void){return fake_us;}
""",
'esp_log.h':r"""#include <stdio.h>
#define ESP_LOGI(tag,fmt,...) printf("%s: " fmt "\n",tag,##__VA_ARGS__)
#define ESP_LOGW ESP_LOGI
#define ESP_LOGE ESP_LOGI
""",
'freertos/FreeRTOS.h':r"""#include <stdbool.h>
#include <stdint.h>
#define pdTRUE 1
#define pdPASS 1
#define pdMS_TO_TICKS(x) (x)
""",
'freertos/task.h':r"""typedef void *TaskHandle_t;
enum{eRunning,eSuspended};
extern int task_state,task_starts,task_deletes;
static inline int eTaskGetState(TaskHandle_t h){(void)h;return task_state;}
static inline void vTaskDelete(TaskHandle_t h){(void)h;task_deletes++;}
static inline void vTaskDelay(int t){(void)t;}
static inline void vTaskSuspend(void *h){(void)h;}
static inline int xTaskCreate(void(*fn)(void*),const char*n,int st,void*a,int pri,TaskHandle_t*h){(void)fn;(void)n;(void)st;(void)a;(void)pri;task_starts++;*h=(void*)1;return pdPASS;}
""",
'freertos/semphr.h':r"""#include <stdlib.h>
typedef void *SemaphoreHandle_t;
static inline int xSemaphoreTake(SemaphoreHandle_t h,int t){(void)t;return h!=NULL;}
static inline void xSemaphoreGive(SemaphoreHandle_t h){(void)h;}
static inline void *xSemaphoreCreateMutex(void){return malloc(1);}
static inline void vSemaphoreDelete(void *h){free(h);}
""",
'psa/crypto.h':r"""#include <stdint.h>
#include <stddef.h>
typedef int psa_hash_operation_t;
#define PSA_HASH_OPERATION_INIT 0
#define PSA_SUCCESS 0
#define PSA_ALG_SHA_256 0
static inline int psa_crypto_init(void){return 0;}
static inline int psa_hash_setup(int*h,int alg){(void)h;(void)alg;return 0;}
static inline int psa_hash_update(int*h,const void*p,size_t n){(void)h;(void)p;(void)n;return 0;}
static inline int psa_hash_finish(int*h,void*p,size_t n,size_t*out){(void)h;(void)p;(void)n;*out=32;return 0;}
static inline int psa_hash_abort(int*h){(void)h;return 0;}
"""}
HOST=r"""
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "lvgl.h"
int64_t fake_us;
int task_state,task_starts,task_deletes;
#include "doom_ui.c"
SemaphoreHandle_t sd_spi_mutex=(void*)1;
static unsigned reboots,navigations,restores,rotations,records,engine_calls;
static bool ready,record_fail;
static int width,height;
static lv_disp_drv_t host_disp;
static lv_color_t framebuffer[480*320];
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){
 for(int y=a->y1;y<=a->y2;y++)for(int x=a->x1;x<=a->x2;x++){assert(x>=0&&x<width&&y>=0&&y<height);framebuffer[y*width+x]=*p++;}
 lv_disp_flush_ready(d);
}
static bool gate(void){return true;}
static bool sd_ready(void){return ready;}
static void reboot(void){reboots++;}
static void normal(void){navigations++;}
static void back(void){restores++;}
static const char *record(void){records++;return record_fail?"s_fileserv_httpd":"NVS intent commit simulated failure";}
static void rotate(bool enter){if(enter)rotations++;else restores++;}
void doom_session_set_frame(doom_frame_fn f,void*c){(void)f;(void)c;engine_calls++;}
int doom_session_start(const char*p){(void)p;engine_calls++;return 0;}
int doom_session_tick(void){engine_calls++;return 0;}
int doom_session_stop(void){return 0;}
void doom_session_request_stop(void){}
const char *doom_session_error(void){return "host fault";}
size_t doom_session_owned(void){return 0;}
size_t doom_session_state_bytes(void){return 0;}
void doom_session_set_keys(unsigned k){(void)k;}
uint16_t doom_session_color565(uint8_t p){return p;}
static void check_bounds(lv_obj_t *obj){
 for(uint32_t i=0;i<lv_obj_get_child_cnt(obj);i++){
  lv_obj_t *c=lv_obj_get_child(obj,i);lv_area_t a;lv_obj_get_coords(c,&a);
  assert(a.x1>=0&&a.y1>=0&&a.x2<width&&a.y2<height);
  if(lv_obj_check_type(c,&lv_label_class)){
   lv_point_t text_size;lv_txt_get_size(&text_size,lv_label_get_text(c),lv_obj_get_style_text_font(c,0),0,0,LV_COORD_MAX,LV_TEXT_FLAG_NONE);
   assert(text_size.x<=lv_obj_get_width(c)); /* exact compiled font glyph width */
  }
  check_bounds(c);
 }
}
static void capture(const char *path){
 lv_obj_update_layout(overlay);check_bounds(overlay);lv_refr_now(NULL);
 FILE*f=fopen(path,"wb");assert(f);fprintf(f,"P6\n%d %d\n255\n",width,height);
 for(int i=0;i<width*height;i++){
  lv_color32_t c;c.full=lv_color_to32(framebuffer[i]);unsigned char rgb[3]={c.ch.red,c.ch.green,c.ch.blue};assert(fwrite(rgb,1,3,f)==3);
 }fclose(f);
}
int main(int argc,char**argv){
 assert(argc==4);width=atoi(argv[1]);height=atoi(argv[2]);assert((width==320&&height==240)||(width==480&&height==320));
 lv_init();static lv_color_t draw[480*16];static lv_disp_draw_buf_t db;lv_disp_draw_buf_init(&db,draw,NULL,width*16);
 lv_disp_drv_init(&host_disp);host_disp.hor_res=width;host_disp.ver_res=height;host_disp.draw_buf=&db;host_disp.flush_cb=flush;lv_disp_drv_register(&host_disp);
 doom_ui_configure(gate,reboot,sd_ready,normal);doom_ui_configure_selector(rotate,back,record);
 doom_ui_tile_click();assert(navigation_timer&&!overlay);lv_tick_inc(810);fake_us+=810000;lv_timer_handler();assert(navigations==1&&!navigation_timer);
 for(int cycle=0;cycle<3;cycle++){
  for(int i=0;i<5;i++){fake_us+=500000;lv_tick_inc(500);doom_ui_tile_click();}
  assert(overlay&&!navigation_timer&&!worker&&!surface&&!mailbox&&!frame_lock);assert(!engine_calls&&!task_starts);
  if(cycle==0)capture(argv[3]);
  /* Exact selector hierarchy: artwork/header/card/card/back. Arduboy disabled. */
  lv_obj_t*doom=lv_obj_get_child(overlay,2);lv_obj_t*arduboy=lv_obj_get_child(overlay,3);
  assert(lv_obj_has_flag(doom,LV_OBJ_FLAG_CLICKABLE));assert(!lv_obj_has_flag(arduboy,LV_OBJ_FLAG_CLICKABLE));
  lv_event_send(doom,LV_EVENT_CLICKED,NULL);assert(status);assert(strstr(lv_label_get_text(status),"GPL version 2"));
  unsigned before=records;ready=false;lv_event_send(lv_obj_get_child(overlay,1),LV_EVENT_CLICKED,NULL);assert(records==before);assert(strstr(lv_label_get_text(status),"Missing WAD"));
  ready=true;record_fail=true;lv_event_send(lv_obj_get_child(overlay,1),LV_EVENT_CLICKED,NULL);assert(records==before+1);assert(strstr(lv_label_get_text(status),"s_fileserv_httpd"));assert(!reboots);
  lv_event_send(lv_obj_get_child(overlay,2),LV_EVENT_CLICKED,NULL);assert(!status);assert(overlay);assert(!surface&&!mailbox&&!worker);
  lv_event_send(lv_obj_get_child(overlay,4),LV_EVENT_CLICKED,NULL);assert(!overlay);assert(!engine_calls&&!task_starts);
 }
 assert(navigations==1&&records==3&&reboots==0);
 doom_ui_boot_start(reboot,false);assert(isolated&&strstr(lv_label_get_text(status),"SD unavailable"));assert(!worker&&!surface);doom_ui_request_exit();assert(reboots==1&&!overlay);
 doom_ui_boot_start(reboot,true);assert(worker&&surface&&mailbox&&frame_lock&&task_starts==1);doom_ui_request_exit();
 done=true;task_state=eRunning;update(timer);assert(worker&&surface&&reboots==1&&task_deletes==0);
 task_state=eSuspended;update(timer);assert(!worker&&!surface&&!mailbox&&!frame_lock&&!overlay&&reboots==2&&task_deletes==1);
 doom_ui_boot_start(reboot,true);assert(worker);strcpy(worker_status,"Injected engine init failure - readable recovery");done=true;task_state=eSuspended;update(timer);
 assert(!worker&&status&&strstr(lv_label_get_text(status),"Injected engine init failure"));assert(lv_obj_get_child_cnt(overlay)==2);
 lv_event_send(lv_obj_get_child(overlay,1),LV_EVENT_CLICKED,NULL);assert(!overlay&&!surface&&!mailbox&&!frame_lock&&reboots==3);
 printf("Production UI+real LVGL %dx%d: native bounds/font widths/art decode, five clicks/timer, license/readiness/refusal/cancel, repeated selectors, isolated SD error, join race PASS\n",width,height);
 return 0;
}
"""
def run():
 OUT.mkdir(parents=True,exist_ok=True)
 for name,content in STUBS.items():
  p=OUT/'stubs'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
 (OUT/'host.c').write_text(HOST)
 flags=['-std=gnu11','-O1','-g','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_16=1','-DLV_FONT_MONTSERRAT_12=1','-DLV_FONT_MONTSERRAT_18=1','-DLV_FONT_MONTSERRAT_20=1','-I'+str(LVGL),'-I'+str(OUT/'stubs'),'-I'+str(COMP/'include'),'-I'+str(COMP)]
 sources=[str(x) for x in (LVGL/'src').rglob('*.c')]
 cmd=['cc',*flags,str(OUT/'host.c'),str(COMP/'doom_contracts.c'),str(COMP/'selector_art.c'),*sources,'-lm','-o',str(OUT/'host')]
 r=subprocess.run(cmd,capture_output=True,text=True);(OUT/'compile.log').write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 logs=[]
 for w,h,board in [(320,240,'ws28'),(480,320,'ws35')]:
  ppm=OUT/(board+'.ppm');r=subprocess.run([str(OUT/'host'),str(w),str(h),str(ppm)],capture_output=True,text=True,timeout=30)
  logs.append(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError(r.stdout+r.stderr)
  im=Image.open(ppm);assert im.size==(w,h)
  target=Path('/home/dev/ws-c5-35-fixes')/('selector-preview-'+board+'.png');im.save(target)
  digest=__import__('hashlib').sha256(target.read_bytes()).hexdigest()
  target.with_suffix('.txt').write_text('ACTUAL production-code headless LVGL capture, not a Pillow mockup or hardware photograph. Engine/IDF peripherals mocked. Native logical '+str((w,h))+'. SHA256 '+digest+'\n')
  target.with_suffix('.txt').write_text('ACTUAL HEADLESS LVGL render of production doom_ui.c and pinned selector_art.c. Host peripheral/engine stubs; native logical dimensions. Not a hardware photograph.\n')
 (OUT/'runtime.log').write_text(''.join(logs));print(''.join(logs))
if __name__=='__main__':run()
