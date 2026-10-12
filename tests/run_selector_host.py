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
extern int host_take(SemaphoreHandle_t,int);
extern void host_give(SemaphoreHandle_t);
static inline int xSemaphoreTake(SemaphoreHandle_t h,int t){return host_take(h,t);}
static inline void xSemaphoreGive(SemaphoreHandle_t h){host_give(h);}
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
#include "ui_diagnostics.h"
static cym_ui_diag host_ui_diag;
static uint32_t host_diag_clock;
uint32_t cym_ui_diag_clock(void){return ++host_diag_clock;}
void cym_ui_diag_record(unsigned kind,uint32_t start){cym_ui_diag_add(&host_ui_diag,kind,cym_ui_diag_elapsed(start,cym_ui_diag_clock()));}
void cym_ui_diag_work_record(unsigned kind,uint32_t units){cym_ui_diag_work_add(&host_ui_diag,kind,units);}
int64_t fake_us;
int task_state,task_starts,task_deletes;
#include "doom_ui.c"
doom_metrics_t doom_metrics;
SemaphoreHandle_t sd_spi_mutex=(void*)1;
static unsigned reboots,navigations,restores,rotations,records,engine_calls;
static bool ready,record_fail;
static int width,height;
static lv_disp_drv_t host_disp;
static lv_color_t framebuffer[480*320],native_panel[480*320];
static unsigned char coverage[480*320];
static void *flush_done_sem=(void*)2;
#define ESP_OK 0
#define ESP_ERR_NO_MEM 257
#define ESP_ERR_INVALID_ARG 258
#define ESP_ERR_TIMEOUT 260
#define MALLOC_CAP_DMA 8
#define LCD_HOST 2
static void *host_stage;
static void *spi_bus_dma_memory_alloc(int h,size_t n,unsigned caps){(void)h;(void)caps;host_stage=aligned_alloc(64,(n+63)&~63);return host_stage;}
static void esp_restart(void){abort();}
static bool enqueue_fail;
typedef int esp_err_t;
typedef void *esp_lcd_panel_handle_t;
static const lv_color_t *borrowed;
static lv_area_t pending;
static unsigned waits,lock_tries,transfers;
static int esp_task_wdt_status(void *task){(void)task;return ESP_OK;}
static void esp_task_wdt_reset(void){}
static int esp_lcd_panel_draw_bitmap(void*p,int x1,int y1,int x2,int y2,const void*buf){
 (void)p;assert(!borrowed);if(enqueue_fail)return ESP_ERR_NO_MEM;assert(buf==host_stage&&!((uintptr_t)buf&63));assert((x2-x1)*(y2-y1)*sizeof(lv_color_t)<=4096);borrowed=buf;pending=(lv_area_t){x1,y1,x2-1,y2-1};waits=0;return 0;
}
static void host_completion(void);
int host_take(SemaphoreHandle_t h,int t){
 if(h==flush_done_sem){if(!t)return 0;if(++waits<4)return 0;
  assert(borrowed);
  for(int y=pending.y1;y<=pending.y2;y++)for(int x=pending.x1;x<=pending.x2;x++){
   assert(x>=0&&x<height&&y>=0&&y<width);
   native_panel[y*height+x]=*borrowed;
   framebuffer[(height-1-x)*width+y]=*borrowed++;
   coverage[y*height+x]=1;
  }
  borrowed=NULL;transfers++;host_completion();return 1;
 }
 if(h==sd_spi_mutex&&++lock_tries<=3)return 0;
 return h!=NULL;
}
void host_give(SemaphoreHandle_t h){(void)h;assert(!borrowed);}
#include "game_panel_transport.h"
static void host_completion(void){cym_diag_isr(&s_display_channel,(uint32_t)esp_timer_get_time());}

static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){
 game_panel_transfer(NULL,a->x1,a->y1,a->x2+1,a->y2+1,p);
 assert(!borrowed);lv_disp_flush_ready(d);
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
static unsigned delivered_keys;
void doom_session_set_keys(unsigned k){delivered_keys=k;}
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

static uint16_t buf_native[2048];
static bool native_reject;static unsigned native_polls,native_exit_after;
static bool host_native_send(void *ctx,doom_rect r,const uint16_t *p){
 (void)ctx;if(native_reject)return false;
 return game_panel_transfer(NULL,r.x,r.y,r.x+r.w,r.y+r.h,p)==ESP_OK;
}
static bool host_native_poll(void *ctx){(void)ctx;native_polls++;
 if(native_exit_after&&native_polls==native_exit_after)doom_ui_request_exit();
 return !quitting();
}
int main(int argc,char**argv){
 assert(argc==4);width=atoi(argv[1]);height=atoi(argv[2]);assert((width==320&&height==240)||(width==480&&height==320));
 assert(cym_panel_transport_init()==ESP_OK);
 lv_init();static lv_color_t draw[480*16];static lv_disp_draw_buf_t db;lv_disp_draw_buf_init(&db,draw,NULL,height*15);
 lv_disp_drv_init(&host_disp);host_disp.hor_res=height;host_disp.ver_res=width;host_disp.sw_rotate=1;host_disp.draw_buf=&db;host_disp.flush_cb=flush;lv_disp_t *display=lv_disp_drv_register(&host_disp);lv_disp_set_rotation(display,LV_DISP_ROT_270);
 /* Panel starts with retained old license/button pixels, not blank RAM. */
 for(unsigned i=0;i<480*320;i++)native_panel[i]=lv_color_hex(0xff00ff);
 enqueue_fail=true;assert(game_panel_transfer(NULL,0,0,7,3,draw)==ESP_ERR_NO_MEM);assert(!borrowed);enqueue_fail=false;
 assert(game_panel_clear(NULL,draw,height,width,15)==ESP_OK);
 for(int i=0;i<width*height;i++)assert(native_panel[i].full==0);
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
 memset(coverage,0,sizeof(coverage));doom_ui_boot_start(reboot,true);assert(worker&&surface&&mailbox&&frame_lock&&task_starts==1);
 lv_refr_now(NULL);
 for(int i=0;i<width*height;i++)assert(coverage[i]);
 unsigned buttons=0;lv_obj_update_layout(overlay);
 for(unsigned i=0;i<lv_obj_get_child_cnt(overlay);i++){
  lv_obj_t *obj=lv_obj_get_child(overlay,i);
  if(lv_obj_check_type(obj,&lv_btn_class)){lv_area_t a;lv_obj_get_coords(obj,&a);assert(a.x1>=0&&a.y1>=0&&a.x2<width&&a.y2<height);buttons++;}
 }
 assert(buttons==5);
 char game_path[512];snprintf(game_path,sizeof(game_path),"%s-loading.ppm",argv[3]);capture(game_path);
 uint32_t redraws=ui_updates;fake_us+=250000;update(timer);assert(ui_updates>redraws);
 load_phase=LOAD_HASH;hash_total=100;hash_bytes=25;update(timer);assert(strstr(lv_label_get_text(status),"25% 25/100 B"));
 load_phase=LOAD_INIT;update(timer);assert(strstr(lv_label_get_text(status),"Engine init"));
 /* Regression: real production UI must replace validation text on start. */
 started=true;update(timer);assert(!strstr(lv_label_get_text(status),"Validating"));
 assert(strstr(lv_label_get_text(status),"fps"));
 uint32_t stable_updates=ui_updates;fake_us+=1000000;update(timer);assert(ui_updates==stable_updates);
 int tx[2]={controls.pad.x+controls.pad.w/2,controls.fire.x+8},ty[2]={controls.pad.y+8,controls.fire.y+8};
 assert(doom_ui_touch_snapshot(tx,ty,2));assert(delivered_keys==(DOOM_KEY_FORWARD|DOOM_KEY_FIRE));
 tx[0]=controls.pad.x+4;assert(doom_ui_touch_snapshot(tx,ty,2));assert(delivered_keys==(DOOM_KEY_FORWARD|DOOM_KEY_LEFT|DOOM_KEY_FIRE));
 assert(doom_ui_touch_snapshot(tx,ty,0));assert(!delivered_keys);
 /* Physical Fire combines independently with either touch contact. */
 doom_ui_boot_fire(true);assert(!delivered_keys);fake_us+=10000;
 doom_ui_boot_fire(false);assert(!delivered_keys); /* bounce rejected */
 doom_ui_boot_fire(true);fake_us+=20000;doom_ui_boot_fire(true);
 assert(delivered_keys==DOOM_KEY_FIRE);
 assert(doom_ui_touch_snapshot(tx,ty,1));assert(delivered_keys==(DOOM_KEY_FORWARD|DOOM_KEY_LEFT|DOOM_KEY_FIRE));
 assert(doom_ui_touch_snapshot(tx,ty,0));assert(delivered_keys==DOOM_KEY_FIRE);
 assert(doom_ui_touch_snapshot(tx,ty,2));
 doom_ui_boot_fire(false);fake_us+=20000;doom_ui_boot_fire(false);
 assert(delivered_keys==(DOOM_KEY_FORWARD|DOOM_KEY_LEFT|DOOM_KEY_FIRE)); /* touch Fire remains */
 assert(doom_ui_touch_snapshot(tx,ty,1));assert(delivered_keys==(DOOM_KEY_FORWARD|DOOM_KEY_LEFT));
 assert(doom_ui_touch_snapshot(tx,ty,0));assert(!delivered_keys);
 started=false;doom_ui_boot_fire(true);fake_us+=30000;doom_ui_boot_fire(true);assert(!delivered_keys);started=true;
 /* Test palette copy/scaling with actual production frame callback. */
 uint8_t pixels[320*200];for(unsigned i=0;i<sizeof(pixels);i++)pixels[i]=(i/320)&255;
 frame_ready(pixels,NULL);uint32_t before_displayed=displayed;update(timer);assert(displayed==before_displayed+1);
 assert(surface[0].full==frame_colors[pixels[0]].full);assert(surface[(fit.h-1)*fit.w].full==frame_colors[pixels[scale_y[fit.h-1]*320]].full);
 update(timer);assert(displayed==before_displayed+1);
 snprintf(game_path,sizeof(game_path),"%s-running.ppm",argv[3]);capture(game_path);
 doom_ui_request_exit();
 done=true;task_state=eRunning;update(timer);assert(worker&&surface&&reboots==1&&task_deletes==0);
 task_state=eSuspended;update(timer);assert(!worker&&!surface&&!mailbox&&!frame_lock&&!overlay&&reboots==2&&task_deletes==1);
 doom_ui_boot_start(reboot,true);assert(worker);strcpy(worker_status,"Injected engine init failure - readable recovery");done=true;task_state=eSuspended;update(timer);
 assert(!worker&&status&&strstr(lv_label_get_text(status),"Injected engine init failure"));assert(lv_obj_get_child_cnt(overlay)==2);
 lv_event_send(lv_obj_get_child(overlay,1),LV_EVENT_CLICKED,NULL);assert(!overlay&&!surface&&!mailbox&&!frame_lock&&reboots==3);


 /* New native mode uses SAME production UI/mailbox/join/input code.
  * Retain every preceding LVGL selector/license and ownership assertion. */
 doom_ui_native_configure(NULL,0,NULL,NULL);
 assert(!doom_ui_native_takeover(true));
 doom_ui_boot_start(reboot,true);started=true;
 assert(!doom_ui_native_takeover(false));
 doom_ui_native_configure(buf_native,2048,host_native_send,host_native_poll);
 assert(!doom_ui_native_takeover(false));assert(timer);
 assert(doom_ui_native_takeover(true));assert(!timer&&doom_ui_native_active());
 assert(native_state.completed==0);
 fake_us+=50000;frame_ready(pixels,NULL);frame_ready(pixels,NULL);
 uint32_t seq=frames;doom_ui_native_step();assert(last_sequence==seq&&native_state.completed==1);
 assert(displayed==1&&!borrowed);uint16_t first=doom_native_wire565(snapshot_palette[pixels[0]]);
 int nx,ny;assert(doom_native_point(&native_state,fit.x,fit.y,&nx,&ny));
 assert(native_panel[ny*height+nx].full==first);
 doom_ui_native_step();assert(native_state.completed==1);
 assert(doom_ui_touch_snapshot(tx,ty,2));assert(delivered_keys==(DOOM_KEY_FORWARD|DOOM_KEY_LEFT|DOOM_KEY_FIRE));
 assert(doom_ui_touch_snapshot(tx,ty,1));assert(delivered_keys==(DOOM_KEY_FORWARD|DOOM_KEY_LEFT));
 doom_ui_boot_fire(true);fake_us+=20000;doom_ui_boot_fire(true);assert(delivered_keys&DOOM_KEY_FIRE);
 assert(doom_ui_touch_snapshot(tx,ty,0));assert(delivered_keys==DOOM_KEY_FIRE);
 frame_ready(pixels,NULL);fake_us+=50000;native_reject=true;unsigned poll_before=native_polls;
 doom_ui_native_step();assert(native_state.completed==1&&native_polls>poll_before);
 native_reject=false;fake_us+=50000;doom_ui_native_step();assert(native_state.completed==2);
 frame_ready(pixels,NULL);fake_us+=50000;native_exit_after=2;native_polls=0;
 doom_ui_native_step();assert(quitting()&&!borrowed&&native_state.completed==2);
 done=true;task_state=eRunning;doom_ui_native_step();assert(worker&&mailbox);
 task_state=eSuspended;doom_ui_native_step();assert(!worker&&!mailbox&&reboots==4&&!doom_ui_native_active());
 puts("production UI native takeover/drain/mailbox/latest/palette/no-frame input/BOOT/partial release/SD reject/retry/Exit/join race PASS");
 /* Pixel-exact software rotation on both native panel geometries. Unique RGB565
  * reference includes odd native dirty widths and source ownership across strips. */
 lv_obj_t *screen=lv_scr_act();lv_obj_clean(screen);
 static lv_color_t reference[480*320];
 for(int rotation=0;rotation<4;rotation++){
  lv_disp_set_rotation(display,(lv_disp_rot_t)rotation);
  int logical_w=lv_disp_get_hor_res(display),logical_h=lv_disp_get_ver_res(display);
  for(int y=0;y<logical_h;y++)for(int x=0;x<logical_w;x++)reference[y*logical_w+x].full=(uint16_t)(x*37+y*11+1);
  lv_obj_t *c=lv_canvas_create(screen);lv_canvas_set_buffer(c,reference,logical_w,logical_h,LV_IMG_CF_TRUE_COLOR);lv_obj_set_pos(c,0,0);
  memset(coverage,0,sizeof(coverage));lv_refr_now(display);
  for(int y=0;y<logical_h;y++)for(int x=0;x<logical_w;x++){
   int nx=x,ny=y;
   if(rotation==1){nx=y;ny=width-1-x;}
   if(rotation==2){nx=height-1-x;ny=width-1-y;}
   if(rotation==3){nx=height-1-y;ny=x;}
   assert(coverage[ny*height+nx]);assert(native_panel[ny*height+nx].full==reference[y*logical_w+x].full);
  }
  lv_obj_del(c);
 }
 assert(host_ui_diag.total[CYM_UI_RENDER].count>0&&host_ui_diag.total[CYM_UI_ROTATE].count>0);
 assert(host_ui_diag.total[CYM_UI_ROTATE].us==host_ui_diag.total[CYM_UI_ROTATE].count);
 assert(host_ui_diag.total[CYM_UI_ROTATE].max_us==1);
 assert(host_ui_diag.work_total[CYM_UI_INVALIDATE].count>0);
 assert(host_ui_diag.work_total[CYM_UI_DIRTY_AREA].count>0);
 assert(host_ui_diag.work_total[CYM_UI_RENDER_BAND].count>0);
 assert(host_ui_diag.work_total[CYM_UI_COVER_VISIT].count>0);
 assert(host_ui_diag.work_total[CYM_UI_DRAW_VISIT].count>0);
 unsigned render_total=host_ui_diag.total[CYM_UI_RENDER].count;
 cym_ui_diag_reset_window(&host_ui_diag);assert(!host_ui_diag.window[CYM_UI_RENDER].count&&host_ui_diag.total[CYM_UI_RENDER].count==render_total);
 puts("Real LVGL pinned production render/rotation RAM counts+window reset PASS; simulated clock not timing proof");
 puts("Real LVGL rotations 0/90/180/270: exact RGB565 reference, owned DMA stripes PASS");
 printf("Production UI+real LVGL %dx%d: native bounds/font widths/art decode, five clicks/timer, license/readiness/refusal/cancel, repeated selectors, isolated SD error, join race PASS\n",width,height);
 return 0;
}
"""
def normal_navigation_source():
 text=(ROOT/'ESP32C5/main/main.c').read_text()
 def function(signature):
  a=text.index(signature+'\n{');b=text.index('{',a);depth=1;i=b+1
  while depth:
   depth+=(text[i]=='{')-(text[i]=='}');i+=1
  return text[a:i]
 pre=r"""
#define CONFIG_BOARD_WS_C5_35 1
#define COLOR_MATERIAL_TEAL lv_color_hex(0x009688)
#define COLOR_MATERIAL_ORANGE lv_color_hex(0xff9800)
#define COLOR_MATERIAL_AMBER lv_color_hex(0xffc107)
static lv_obj_t *screen_popup,*screen_home_classic_radio,*screen_home_4cat_radio,*timeout_dropdown,*brightness_slider,*brightness_value_label,*orient_dropdown;
static bool g_home_layout_4cat;static uint8_t brightness_before_popup,screen_brightness_pct=80,screen_orientation;static uint32_t screen_timeout_ms=60000;
static const bool SCREEN_HOME_LAYOUT_CHOICE[2]={false,true};
static lv_color_t ui_bg_color(void){return lv_color_hex(0x181818);}
static lv_color_t ui_panel_color(void){return lv_color_hex(0x252525);}
static lv_color_t ui_text_color(void){return lv_color_white();}
static int timeout_ms_to_index(uint32_t ms){(void)ms;return 2;}
static void set_backlight_percent(unsigned pct){assert(pct==80);}
static void screen_popup_save_cb(lv_event_t*e){(void)e;} /* NVS/rotation services not exercised here. */
static void brightness_slider_event_cb(lv_event_t*e){(void)e;}
static void show_screen_popup_measured(void);
"""
 pre+='\n'.join(function(sig) for sig in ['static void screen_home_layout_radio_cb(lv_event_t *e)','static void screen_popup_close_cb(lv_event_t *e)','static void show_screen_popup(void)','static void show_screen_popup_measured(void)'])
 pre+=r"""
#undef CONFIG_BOARD_WS_C5_35
static void normal_navigation_smoke(lv_disp_t*d){
 for(int rotation=0;rotation<4;rotation++){
  lv_disp_set_rotation(d,(lv_disp_rot_t)rotation);screen_orientation=rotation;
  for(int modern=0;modern<2;modern++)for(int cycle=0;cycle<2;cycle++){
   g_home_layout_4cat=modern;unsigned before=lv_obj_get_child_cnt(lv_scr_act());
   show_screen_popup();assert(screen_popup);lv_obj_t *first=screen_popup;unsigned constructed=lv_obj_get_child_cnt(lv_scr_act());assert(constructed>=before+1);
   show_screen_popup();assert(first==screen_popup);
   assert(lv_obj_get_child_cnt(lv_scr_act())==constructed);
   assert(lv_obj_has_state(modern?screen_home_4cat_radio:screen_home_classic_radio,LV_STATE_CHECKED));
   assert(lv_dropdown_get_selected(orient_dropdown)==rotation);
   lv_refr_now(d);uint32_t count=host_ui_diag.work_total[CYM_UI_RENDER_BAND].count;
   lv_refr_now(d);assert(host_ui_diag.work_total[CYM_UI_RENDER_BAND].count==count); /* settled popup does not redraw spontaneously */
   screen_popup_close_cb(NULL);assert(!screen_popup&&!timeout_dropdown&&!brightness_slider);
   assert(lv_obj_get_child_cnt(lv_scr_act())==before);
  }
 }
 puts("Production Screen popup Classic/Modern repeat/open/no-duplicate/idle/cancel and saved orientation 0/90/180/270 PASS; hardware and NVS save mocked");
}
"""
 return pre
def run():
 OUT.mkdir(parents=True,exist_ok=True)
 for name,content in STUBS.items():
  p=OUT/'stubs'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
 host=HOST.replace('int main(int argc,char**argv){',normal_navigation_source()+'\nint main(int argc,char**argv){')
 host=host.replace(' lv_obj_t *screen=lv_scr_act();lv_obj_clean(screen);',' normal_navigation_smoke(display);\n lv_obj_t *screen=lv_scr_act();lv_obj_clean(screen);')
 (OUT/'host.c').write_text(host)
 flags=['-std=gnu11','-O1','-g','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_16=1','-DLV_FONT_MONTSERRAT_12=1','-DLV_FONT_MONTSERRAT_18=1','-DLV_FONT_MONTSERRAT_20=1','-I'+str(LVGL),'-I'+str(OUT/'stubs'),'-I'+str(COMP/'include'),'-I'+str(COMP),'-I'+str(ROOT/'ESP32C5/main')]
 diag_src=OUT/'lv_refr.c'
 r=subprocess.run(['python3',str(ROOT/'scripts/lvgl-diag-copy.py'),str(LVGL/'src/core/lv_refr.c'),str(diag_src)],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr)
 flags+=['-I'+str(LVGL/'src/core')]
 sources=[str(diag_src) if x==LVGL/'src/core/lv_refr.c' else str(x) for x in (LVGL/'src').rglob('*.c')]
 cmd=['cc',*flags,str(OUT/'host.c'),str(COMP/'doom_contracts.c'),str(COMP/'selector_art.c'),*sources,'-lm','-o',str(OUT/'host')]
 r=subprocess.run(cmd,capture_output=True,text=True);(OUT/'compile.log').write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 logs=[]
 for w,h,board in [(320,240,'ws28'),(480,320,'ws35')]:
  ppm=OUT/(board+'.ppm');r=subprocess.run([str(OUT/'host'),str(w),str(h),str(ppm)],capture_output=True,text=True,timeout=30)
  logs.append(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError(r.stdout+r.stderr)
  im=Image.open(ppm);assert im.size==(w,h)
  for phase in ['loading','running']:
   Image.open(str(ppm)+'-'+phase+'.ppm').save(Path('/home/dev/ws-c5-35-fixes/cycle81')/(board+'-'+phase+'.png'))
  target=Path('/home/dev/ws-c5-35-fixes')/('selector-preview-'+board+'.png');im.save(target)
  digest=__import__('hashlib').sha256(target.read_bytes()).hexdigest()
  target.with_suffix('.txt').write_text('ACTUAL production-code headless LVGL capture, not a Pillow mockup or hardware photograph. Engine/IDF peripherals mocked. Native logical '+str((w,h))+'. SHA256 '+digest+'\n')
  target.with_suffix('.txt').write_text('ACTUAL HEADLESS LVGL render of production doom_ui.c and pinned selector_art.c. Host peripheral/engine stubs; native logical dimensions. Not a hardware photograph.\n')
 (OUT/'runtime.log').write_text(''.join(logs));print(''.join(logs))
if __name__=='__main__':run()
