"""Compile startup consent UI against pinned real LVGL; no hardware claim."""
from pathlib import Path
import subprocess,unittest
from test_cycle84_dma_timekeeper import function
ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/home/dev/ws-c5-35-fixes/cycle85/ui-host')
PRE=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "lvgl.h"
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
#define COLOR_MATERIAL_TEAL lv_color_hex(0x009688)
static void *lvgl_mutex=(void*)1;
static unsigned choice,polls,hidden;static int width,height;
static size_t psram_total;
#define MALLOC_CAP_SPIRAM 1
static size_t heap_caps_get_total_size(int caps){assert(caps==1);return psram_total;}
static int xSemaphoreTake(void*m,int t){(void)t;assert(m==lvgl_mutex);return 1;}
static void xSemaphoreGive(void*m){assert(m==lvgl_mutex);}
static void vTaskDelay(int t){(void)t;}
static void hide_sd_loading_popup(void){hidden++;}
static lv_color_t ui_bg_color(void){return lv_color_black();}
static lv_color_t ui_text_color(void){return lv_color_white();}
static lv_color_t ui_panel_color(void){return lv_color_hex(0x303030);}
static volatile int s_sd_startup_choice;
static const char *const sd_startup_paths[]={"/sdcard/lab/deauths","/sdcard/lab/gattwalker","/sdcard/lab/otsurvey"};
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){(void)a;(void)p;lv_disp_flush_ready(d);}
static void s_poll_lvgl_until(volatile int *flag,int sentinel){
 polls++;assert(*flag==sentinel);
 lv_obj_t *o=lv_obj_get_child(lv_layer_top(),0);assert(o);
 if(!psram_total){
  assert(lv_obj_get_child_cnt(o)==2);lv_obj_update_layout(o);
  lv_obj_t *label=lv_obj_get_child(o,0),*ok=lv_obj_get_child(o,1);
  const char *text=lv_label_get_text(label);assert(strstr(text,"no PSRAM")&&strstr(text,"CYM-SD-Assets"));
  lv_point_t size;lv_txt_get_size(&size,text,&lv_font_montserrat_12,0,0,lv_obj_get_content_width(label),LV_TEXT_FLAG_NONE);
  assert(size.y<=lv_obj_get_content_height(label));assert(!strcmp(lv_label_get_text(lv_obj_get_child(ok,0)),"OK"));
  lv_event_send(ok,LV_EVENT_CLICKED,NULL);assert(*flag==1);return;
 }
 assert(lv_obj_get_child_cnt(o)==3);
 lv_obj_t *label=lv_obj_get_child(o,0),*later=lv_obj_get_child(o,1),*provision=lv_obj_get_child(o,2);
 lv_obj_update_layout(o);
 const char *text=lv_label_get_text(label);
 assert(strstr(text,"/sdcard/lab/deauths")&&strstr(text,"/sdcard/lab/gattwalker")&&strstr(text,"/sdcard/lab/otsurvey"));
 lv_point_t text_size;lv_txt_get_size(&text_size,text,&lv_font_montserrat_12,0,0,lv_obj_get_content_width(label),LV_TEXT_FLAG_NONE);
 assert(text_size.y<=lv_obj_get_content_height(label));
 lv_area_t a,b;lv_obj_get_coords(later,&a);lv_obj_get_coords(provision,&b);
 assert(a.x1>=0&&a.y1>=0&&a.x2<width&&a.y2<height&&b.x1>=0&&b.y1>=0&&b.x2<width&&b.y2<height&&a.x2<b.x1);
 assert(!strcmp(lv_label_get_text(lv_obj_get_child(later,0)),"Later"));
 assert(!strcmp(lv_label_get_text(lv_obj_get_child(provision,0)),"Provision"));
 lv_event_send(choice==1?later:provision,LV_EVENT_CLICKED,NULL);assert(*flag==(int)choice);
}
"""
POST=r"""
int main(void){
 lv_init();static lv_color_t pixels[800*20];static lv_disp_draw_buf_t buf;lv_disp_draw_buf_init(&buf,pixels,NULL,800*20);
 static lv_disp_drv_t drv;lv_disp_drv_init(&drv);drv.hor_res=240;drv.ver_res=320;drv.draw_buf=&buf;drv.flush_cb=flush;
 lv_disp_t *d=lv_disp_drv_register(&drv);
 int sizes[][2]={{240,320},{320,240},{320,480},{480,320},{480,800},{800,480}};
 for(int i=0;i<6;i++)for(int layout=0;layout<2;layout++)for(int ram=0;ram<2;ram++){
  psram_total=ram?8388608:0;
  width=sizes[i][0];height=sizes[i][1];drv.hor_res=width;drv.ver_res=height;lv_disp_drv_update(d,&drv);
  for(choice=1;choice<=2;choice++){
   unsigned before=polls;assert(!show_sd_startup_provision_prompt(0));assert(polls==before);
   assert(show_sd_startup_provision_prompt(7)==(psram_total && choice==2));assert(polls==before+1);
   assert(!lv_obj_get_child_cnt(lv_layer_top()));
  }
 }
 assert(polls==48&&hidden==48);
 for(int i=0;i<6;i++){
  width=sizes[i][0];height=sizes[i][1];drv.hor_res=width;drv.ver_res=height;lv_disp_drv_update(d,&drv);
  show_sd_manual_setup_popup();lv_obj_t *overlay=lv_obj_get_child(lv_layer_top(),-1);assert(overlay);
  lv_obj_t *mbox=lv_obj_get_child(overlay,0);assert(mbox);lv_obj_update_layout(mbox);
  lv_area_t area;lv_obj_get_coords(mbox,&area);assert(area.x1>=0&&area.y1>=0&&area.x2<width&&area.y2<height);
  lv_obj_t *label=lv_msgbox_get_text(mbox);const char *text=lv_label_get_text(label);
  lv_point_t size;lv_txt_get_size(&size,text,&lv_font_montserrat_12,0,0,lv_obj_get_content_width(label),LV_TEXT_FLAG_NONE);
  assert(size.y<=lv_obj_get_content_height(label));
  lv_event_send(mbox,LV_EVENT_VALUE_CHANGED,NULL);for(int j=0;j<3;j++){lv_tick_inc(10);lv_timer_handler();}
  assert(!lv_obj_get_child_cnt(lv_layer_top()));
 }
puts("Real LVGL: six geometries, both layout-independent flows, PSRAM present/absent, manual modal geometry and async OK cleanup PASS");
}
"""
class StartupUI(unittest.TestCase):
 def test_real_lvgl_prompt_geometry_and_consent(self):
  OUT.mkdir(parents=True,exist_ok=True)
  s=(ROOT/'ESP32C5/main/main.c').read_text()
  helpers=s[s.index('static bool sd_auto_provision_available(void)'):s.index('/* Startup owns LVGL;')]
  source=PRE+helpers+function(s,'static void sd_startup_choice_cb(lv_event_t *e)\n{')+'\n'+function(s,'static bool show_sd_startup_provision_prompt(unsigned missing)\n{')+'\n'+POST
  (OUT/'host.c').write_text(source)
  lvgl=ROOT/'ESP32C5/managed_components/lvgl__lvgl'
  flags=['-std=gnu11','-O1','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-I'+str(lvgl)]
  r=subprocess.run(['cc',*flags,str(OUT/'host.c'),*[str(p) for p in (lvgl/'src').rglob('*.c')],'-lm','-o',str(OUT/'host')],capture_output=True,text=True)
  (OUT/'compile.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(OUT/'host')],capture_output=True,text=True,timeout=30)
  (OUT/'runtime.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  print(r.stdout)
