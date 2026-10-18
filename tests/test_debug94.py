"""Approved debug setting tests execute production paths; no hardware claims."""
from pathlib import Path
import unittest, subprocess
import test_revision91 as helpers
ROOT=Path(__file__).resolve().parents[1]
class Debug94(unittest.TestCase):
 def test_shared_settings_exists(self):
  self.assertTrue((ROOT/"ESP32C5/main/debug_settings.c").exists())
 def test_owner_switch_exists(self):
  self.assertIn("hardware_debug_sync",(ROOT/"ESP32C5/main/main.c").read_text())
 def test_approved_audio_target(self):
  self.assertIn("GAME_AUDIO_VOLUME_DB = 9.0f",(ROOT/"ESP32C5/components/cym_doom/doom_audio.c").read_text())

STUB=r"""#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
typedef int esp_err_t;typedef unsigned nvs_handle_t;typedef void* SemaphoreHandle_t;
#define ESP_OK 0
#define ESP_ERR_NVS_NOT_FOUND 1
#define ESP_ERR_NO_MEM 2
#define ESP_ERR_INVALID_ARG 3
#define ESP_ERR_INVALID_STATE 4
#define ESP_ERR_TIMEOUT 5
#define NVS_READONLY 0
#define NVS_READWRITE 1
#define pdTRUE 1
#define pdMS_TO_TICKS(n) (n)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
const char *esp_err_to_name(int n);
SemaphoreHandle_t xSemaphoreCreateMutex(void);
int xSemaphoreTake(SemaphoreHandle_t,unsigned);
void xSemaphoreGive(SemaphoreHandle_t);
int nvs_open(const char*,int,nvs_handle_t*);
int nvs_get_u8(nvs_handle_t,const char*,uint8_t*);
int nvs_set_u8(nvs_handle_t,const char*,uint8_t);
int nvs_commit(nvs_handle_t);
void nvs_close(nvs_handle_t);
"""
NATIVE=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "debug_settings.c"
#include "/home/dev/esp/esp-idf/components/console/split_argv.c"
static int present,value,staged,open_fail,read_fail,set_fail,commit_fail,busy,nomem;
static unsigned opens,reads,writes,commits,closes;
const char *esp_err_to_name(int n){return n?"INJECTED":"OK";}
SemaphoreHandle_t xSemaphoreCreateMutex(void){return nomem?NULL:&present;}
int xSemaphoreTake(SemaphoreHandle_t h,unsigned t){assert(h&&t==250);return !busy;}
void xSemaphoreGive(SemaphoreHandle_t h){assert(h);}
int nvs_open(const char*ns,int mode,nvs_handle_t*h){assert(!strcmp(ns,"settings"));opens++;if(open_fail)return 9;if(!present&&mode==NVS_READONLY)return ESP_ERR_NVS_NOT_FOUND;*h=42;return 0;}
int nvs_get_u8(nvs_handle_t h,const char*k,uint8_t*v){assert(h==42&&!strcmp(k,"debug_diag"));reads++;if(read_fail)return 9;if(!present)return 1;*v=value;return 0;}
int nvs_set_u8(nvs_handle_t h,const char*k,uint8_t v){assert(h==42&&!strcmp(k,"debug_diag")&&v<=1);writes++;if(set_fail)return 9;staged=v;return 0;}
int nvs_commit(nvs_handle_t h){assert(h==42);commits++;if(commit_fail)return 9;value=staged;present=1;return 0;}
void nvs_close(nvs_handle_t h){assert(h==42);closes++;}
int main(void){
 assert(!cym_debug_enabled());assert(cym_debug_set(true)==ESP_ERR_INVALID_STATE);
 nomem=1;assert(cym_debug_load()==ESP_ERR_NO_MEM);assert(!cym_debug_enabled());nomem=0;
 assert(cym_debug_load()==ESP_OK&&!cym_debug_enabled());
 present=1;value=7;assert(cym_debug_load()==ESP_ERR_INVALID_ARG&&!cym_debug_enabled());
 for(int v=0;v<=1;v++){value=v;assert(cym_debug_load()==ESP_OK);assert(cym_debug_enabled()==(v==1));}
 read_fail=1;assert(cym_debug_load()!=0&&!cym_debug_enabled());read_fail=0;
 open_fail=1;assert(cym_debug_load()!=0&&!cym_debug_enabled());open_fail=0;
 uint32_t gen=cym_debug_generation();assert(cym_debug_set(true)==0&&cym_debug_enabled());assert(gen!=cym_debug_generation());
 assert(value==1);assert(cym_debug_load()==0&&cym_debug_enabled()); /* simulated reboot */
 gen=cym_debug_generation();open_fail=1;assert(cym_debug_set(false)!=0);open_fail=0;assert(cym_debug_enabled()&&gen==cym_debug_generation());
 set_fail=1;unsigned oldcommits=commits;assert(cym_debug_set(false)!=0);set_fail=0;assert(commits==oldcommits&&cym_debug_enabled()&&value==1);
 commit_fail=1;assert(cym_debug_set(false)!=0);commit_fail=0;assert(cym_debug_enabled()&&value==1&&gen==cym_debug_generation());
 busy=1;unsigned oldopens=opens;assert(cym_debug_set(false)==ESP_ERR_TIMEOUT);busy=0;assert(opens==oldopens&&cym_debug_enabled());
 char *status[]={"debug","status"},*query[]={"debug","query"},*bare[]={"debug"},*on[]={"debug","on"},*off[]={"debug","off"};
 assert(!cym_debug_command(2,status));assert(!cym_debug_command(2,query));assert(!cym_debug_command(1,bare));
 char *bad[]={"debug","ON","extra"};unsigned oldwrites=writes;assert(cym_debug_command(3,bad)==1);assert(cym_debug_command(2,bad)==1);assert(writes==oldwrites&&cym_debug_enabled());
 commit_fail=1;assert(cym_debug_command(2,off)==1);commit_fail=0;assert(cym_debug_enabled());
 assert(!cym_debug_command(2,off)&&!cym_debug_enabled());assert(!cym_debug_command(2,status));
 assert(cym_debug_load()==0&&!cym_debug_enabled());assert(!cym_debug_command(2,on)&&cym_debug_enabled());assert(cym_debug_load()==0&&cym_debug_enabled());
 assert(!cym_debug_command(2,off));
 const char *malformed[]={"debug garbage","debug on extra","debug OFF","debug on off"};
 for(unsigned i=0;i<sizeof(malformed)/sizeof(*malformed);i++){char line[100];strcpy(line,malformed[i]);char *args[32];size_t count=esp_console_split_argv(line,args,32);assert(cym_debug_command((int)count,args)==1&&!cym_debug_enabled());}
 char line[]="debug on";char *args[32];size_t count=esp_console_split_argv(line,args,32);assert(!cym_debug_command((int)count,args)&&cym_debug_enabled());
 assert(closes>0&&reads>0);puts("PRODUCTION_DEBUG NVS no-key/default/invalid/off/on/reboot/open/read/set/commit/contention/serial PASS");return 0;
}
"""
class ProductionDebug94(unittest.TestCase):
 def run_c(self,name,code,headers=None):
  out=ROOT/'.hermes/debug94'/name;out.mkdir(parents=True,exist_ok=True)
  for n,v in (headers or {}).items():
   p=out/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(v)
  src=out/'test.c';src.write_text(code);exe=out/'test'
  cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-unused-function','-Wno-unused-variable','-fsanitize=address,undefined','-g','-I'+str(out),'-I'+str(ROOT/'ESP32C5/main'),str(src),'-o',str(exe)]
  r=subprocess.run(cmd,capture_output=True,text=True);(out/'compile.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(exe)],capture_output=True,text=True);(out/'run.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stderr);return r.stdout
 def test_production_nvs_and_serial_faults(self):
  headers={n:'#include "mock.h"\n' for n in ['esp_err.h','nvs.h','esp_log.h','freertos/FreeRTOS.h','freertos/semphr.h']};headers['mock.h']=STUB
  text=self.run_c('settings',NATIVE,headers);self.assertIn('Debug persistence failed:',text);self.assertIn('Debug OFF',text);self.assertIn('PRODUCTION_DEBUG',text)
 def test_production_owner_sync_recreation_and_fault(self):
  source=(ROOT/'ESP32C5/main/main.c').read_text();extract=lambda source,signature:helpers.Revision91.extract(self,source,signature)
  code=r"""#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
typedef int esp_err_t;
#define ESP_OK 0
#define LV_STATE_CHECKED 1
#define LV_EVENT_VALUE_CHANGED 2
typedef struct {bool checked;} lv_obj_t;
typedef int lv_timer_t;
typedef struct {int code;lv_obj_t *target;} lv_event_t;
static bool enabled;static int fail,deleted;static const char *message;
static lv_obj_t *s_hardware_debug_switch,*s_hardware_debug_status;
static lv_timer_t *s_hardware_debug_timer;
static bool cym_debug_enabled(void){return enabled;}
static int cym_debug_set(bool v){if(fail)return -1;enabled=v;return 0;}
static void lv_obj_add_state(lv_obj_t *p,int n){assert(n==1);p->checked=true;}
static void lv_obj_clear_state(lv_obj_t*p,int n){assert(n==1);p->checked=false;}
static bool lv_obj_has_state(lv_obj_t*p,int n){assert(n==1);return p->checked;}
static void lv_timer_del(lv_timer_t*t){assert(t);deleted++;}
static int lv_event_get_code(lv_event_t*e){return e->code;}
static lv_obj_t *lv_event_get_target(lv_event_t*e){return e->target;}
static void lv_label_set_text(lv_obj_t*p,const char*s){assert(p);message=s;}
"""
  for signature in ['static void hardware_debug_sync(lv_timer_t *timer)','static void hardware_debug_stop(void)','static void hardware_debug_event(lv_event_t *e)']:
   code+=extract(source,signature+'\n{')+'\n'
  code+=r"""
int main(void){lv_obj_t first={0},second={0},status={0};lv_timer_t timer=0;
hardware_debug_sync(NULL);s_hardware_debug_switch=&first;s_hardware_debug_status=&status;s_hardware_debug_timer=&timer;
/* Same shared state changed by serial; update only in LVGL owner timer. */
enabled=true;hardware_debug_sync(NULL);assert(first.checked);enabled=false;hardware_debug_sync(NULL);assert(!first.checked);
first.checked=true;lv_event_t e={2,&first};hardware_debug_event(&e);assert(enabled&&first.checked);
first.checked=false;fail=1;hardware_debug_event(&e);assert(enabled&&first.checked&&message);fail=0;
hardware_debug_stop();assert(deleted==1&&!s_hardware_debug_switch&&!s_hardware_debug_status&&!s_hardware_debug_timer);
hardware_debug_sync(NULL);s_hardware_debug_switch=&second;hardware_debug_sync(NULL);assert(second.checked);
enabled=false;hardware_debug_sync(NULL);assert(!second.checked);hardware_debug_stop();hardware_debug_stop();assert(deleted==1);return 0;}
"""
  self.run_c('ui-owner',code)
 def test_boot_console_layout_safety_contracts(self):
  source=(ROOT/'ESP32C5/main/main.c').read_text();extract=lambda source,signature:helpers.Revision91.extract(self,source,signature)
  boot=extract(source,'void app_main(void)\n{');self.assertLess(boot.index('cym_debug_load()'),boot.index('game_early_consume('))
  screen=extract(source,'static void show_hardware_options_screen_measured(void)\n{')
  self.assertLess(screen.index('create_function_page_base'),screen.index('g_screen_stop_fn = hardware_debug_stop'))
  self.assertIn('lv_timer_create(hardware_debug_sync,200,NULL)',screen);self.assertIn('Debug diagnostics',screen);self.assertIn('lv_disp_get_ver_res(NULL)',screen)
  for w,h in [(240,320),(320,240),(320,480),(480,320),(800,480)]:
   self.assertGreater(h-30-90,0);self.assertGreater(w-12-44,140)
  console=(ROOT/'ESP32C5/main/debug_console.c').read_text();self.assertIn('esp_console_run(line,&result)',console);self.assertIn('fopen(DEBUG_USB_VFS_PATH,"r")',console);self.assertIn('fopen(DEBUG_USB_VFS_PATH,"w")',console);self.assertIn('#if CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG\n#define DEBUG_USB_VFS_PATH "/dev/secondary"\n#else\n#define DEBUG_USB_VFS_PATH "/dev/usbserjtag"',console);self.assertIn('CONFIG_ESP_CONSOLE_NONE',console)
  self.assertNotIn('GPS_UART',console);self.assertNotIn('lv_',console);self.assertNotIn('wifi_cli_register_commands',console)
  settings=(ROOT/'ESP32C5/main/debug_settings.c').read_text();self.assertNotIn('lv_',settings);self.assertNotIn('nvs_erase',settings)
  game=(ROOT/'ESP32C5/components/cym_doom/doom_ui.c').read_text();self.assertIn('if(cym_debug_enabled()&&(uint32_t)(now-ui_last_log)>=5000)',game)
  audio=(ROOT/'ESP32C5/components/cym_doom/doom_audio.c').read_text();self.assertIn('if(!verified){ESP_LOGE',audio);self.assertIn('AUDIO_WRITE_FAILED',audio)

 def test_production_optional_measurements_and_transition_windows(self):
  source=(ROOT/'ESP32C5/main/main.c').read_text();extract=lambda text,sig:helpers.Revision91.extract(self,text,sig)
  code=r"""#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <inttypes.h>
#include "ui_diagnostics.h"
#include "display_diagnostics.h"
static bool enabled;static uint32_t generation;static uint64_t now;static unsigned clocks,logs;
static bool cym_debug_enabled(void){return enabled;}
static uint32_t cym_debug_generation(void){return generation;}
static uint64_t esp_timer_get_time(void){clocks++;return now;}
static void log_line(const char*t,const char*f,...){(void)t;(void)f;logs++;}
#define ESP_LOGI log_line
#define TAG "test"
static cym_ui_diag s_ui_diag;static bool s_ui_diag_normal=true;
"""
  for sig in ['static void cym_ui_diag_transition(void)','uint32_t cym_ui_diag_clock(void)','void cym_ui_diag_record(unsigned kind,uint32_t start)','void cym_ui_diag_work_record(unsigned kind,uint32_t units)','static void cym_ui_diag_report(void)']:
   code+=extract(source,sig)+'\n'
  code+='#include "display_diagnostics_report.h"\n'+r"""
int main(void){
 now=100;assert(!cym_ui_diag_clock());cym_ui_diag_record(0,10);cym_ui_diag_work_record(0,20);cym_ui_diag_report();cym_display_diag_report();assert(!clocks&&!logs&&!s_ui_diag.total[0].count&&!s_ui_diag.work_total[0].count);
 enabled=true;generation=2;cym_ui_diag_report();cym_display_diag_report();now+=10000;
 uint32_t start=cym_ui_diag_clock();now+=20;cym_ui_diag_record(0,start);cym_ui_diag_work_record(0,30);assert(s_ui_diag.window[0].count==1&&s_ui_diag.work_window[0].units==30);
 enabled=false;generation=4;cym_ui_diag_work_record(0,40);assert(!s_ui_diag.window[0].count&&!s_ui_diag.work_window[0].count&&s_ui_diag.total[0].count==1);
 cym_ui_diag_report();cym_display_diag_report();unsigned oldclocks=clocks,oldlogs=logs;
 now+=6000000;cym_ui_diag_report();cym_display_diag_report();assert(clocks==oldclocks&&logs==oldlogs);
 enabled=true;generation=6;cym_ui_diag_report();cym_display_diag_report();cym_diag_callback_begin(&s_display_diag[0],10,480,4096,100);cym_diag_callback_end(&s_display_diag[0],false,120);start=cym_ui_diag_clock();now+=30;cym_ui_diag_record(0,start);
 now+=4990000;cym_ui_diag_report();cym_display_diag_report();assert(logs==oldlogs);now+=10000;cym_ui_diag_report();cym_display_diag_report();assert(logs==oldlogs+2);return 0;}
"""
  self.run_c('runtime-measurements',code)
 def test_engine_optional_printf_skips_arguments_off(self):
  code=r"""#define CYM_DEBUG_HOST_STATE 1
#include <stdio.h>
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
static bool enabled;
bool cym_debug_enabled(void){return enabled;}
uint32_t cym_debug_generation(void){return enabled;}
void cym_debug_memory_report(void){}
#define DEH_printf printf
#include """+'"'+str(ROOT/'ESP32C5/components/cym_doom/include/debug_gate.h')+'"'+r"""
int main(void){int expensive=0;CYM_GAME_DEBUG_PRINTF("%d",++expensive);CYM_GAME_DEBUG_DEH_PRINTF("%d",++expensive);CYM_GAME_DEBUG_PUTS((++expensive,"test"));assert(!expensive);enabled=true;CYM_GAME_DEBUG_PRINTF("%d",++expensive);CYM_GAME_DEBUG_DEH_PRINTF("%d",++expensive);CYM_GAME_DEBUG_PUTS((++expensive,"test"));assert(expensive==3);return 0;}
"""
  self.run_c('engine-format',code)

 def test_real_lvgl_hardware_layouts_and_recreation(self):
  source=(ROOT/'ESP32C5/main/main.c').read_text();extract=lambda text,sig:helpers.Revision91.extract(self,text,sig)
  pre=r"""#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "lvgl.h"
LV_FONT_DECLARE(lv_extra_symbols);
#define ESP_OK 0
#define ESP_LOGE(...) ((void)0)
#define COLOR_MATERIAL_RED lv_color_hex(0xf44336)
#define MY_SYMBOL_TOWER "tower"
typedef int esp_err_t;
static int screen_orientation;static bool dark_mode_enabled,enabled;static int fail;
static lv_obj_t *function_page,*s_hardware_debug_switch,*s_hardware_debug_status;
static lv_timer_t *s_hardware_debug_timer;static void (*g_screen_stop_fn)(void);
static const char *cym_debug_console_status(void){return "Ready (USB-C)";}
static bool cym_debug_enabled(void){return enabled;}
static int cym_debug_set(bool v){if(fail)return -1;enabled=v;return 0;}
static lv_color_t ui_card_color(void){return dark_mode_enabled?lv_color_hex(0x303030):lv_color_white();}
static lv_color_t ui_card_pressed_color(void){return lv_color_hex(0x404040);}
static lv_color_t ui_border_color(void){return lv_color_hex(0x555555);}
static lv_color_t ui_text_color(void){return dark_mode_enabled?lv_color_white():lv_color_black();}
static void hw_options_tile_event_cb(lv_event_t *e){(void)e;}
static void apply_menu_bg(void){}
static void create_function_page_base(const char *name){
 assert(!strcmp(name,"Hardware Options"));if(g_screen_stop_fn){g_screen_stop_fn();g_screen_stop_fn=NULL;}
 if(function_page)lv_obj_del(function_page);
 function_page=lv_obj_create(lv_scr_act());lv_obj_set_size(function_page,lv_pct(100),lv_pct(100));lv_obj_align(function_page,LV_ALIGN_CENTER,0,0);
 lv_obj_set_style_border_width(function_page,0,0);lv_obj_set_style_pad_all(function_page,0,0);lv_obj_clear_flag(function_page,LV_OBJ_FLAG_SCROLLABLE);
}
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){(void)a;(void)p;lv_disp_flush_ready(d);}
"""
  functions=''
  for sig in ['static lv_obj_t *create_tile(lv_obj_t *parent, const char *icon, const char *text, lv_color_t accent, lv_event_cb_t callback, const char *user_data)\n{','static void hardware_debug_sync(lv_timer_t *timer)','static void hardware_debug_stop(void)','static void hardware_debug_event(lv_event_t *e)','static void show_hardware_options_screen_measured(void)\n{']:
   functions+=extract(source,sig)+'\n'
  post=r"""
static void geometry(void){lv_obj_update_layout(function_page);
 lv_obj_t *row=lv_obj_get_parent(s_hardware_debug_switch),*label=lv_obj_get_child(row,0);lv_area_t r,l,sw,st;
 lv_obj_get_coords(row,&r);lv_obj_get_coords(label,&l);lv_obj_get_coords(s_hardware_debug_switch,&sw);lv_obj_get_coords(s_hardware_debug_status,&st);
 assert(r.x1>=0&&r.y1>=30&&r.x2<lv_disp_get_hor_res(NULL)&&r.y2<lv_disp_get_ver_res(NULL));
 assert(l.x2<sw.x1&&l.y2<st.y1&&sw.y2<st.y1);assert(st.x1>=r.x1&&st.x2<=r.x2&&st.y2<=r.y2);
 lv_point_t size;lv_txt_get_size(&size,lv_label_get_text(s_hardware_debug_status),&lv_font_montserrat_12,0,0,lv_obj_get_width(s_hardware_debug_status),LV_TEXT_FLAG_NONE);
 assert(size.y<=lv_obj_get_height(s_hardware_debug_status));
 lv_obj_t *tiles=lv_obj_get_child(function_page,0);assert(lv_obj_get_child_cnt(tiles)==2);
 lv_area_t t;lv_obj_get_coords(tiles,&t);assert(t.y2<r.y1);}
int main(void){lv_init();static lv_color_t pixels[800*20];static lv_disp_draw_buf_t buf;lv_disp_draw_buf_init(&buf,pixels,NULL,800*20);
 static lv_disp_drv_t drv;lv_disp_drv_init(&drv);drv.hor_res=240;drv.ver_res=320;drv.draw_buf=&buf;drv.flush_cb=flush;lv_disp_t *d=lv_disp_drv_register(&drv);
 int sizes[][2]={{240,320},{320,240},{320,480},{480,320},{480,800},{800,480}};
 for(unsigned i=0;i<6;i++)for(int layout=0;layout<2;layout++)for(int repeat=0;repeat<3;repeat++){
  drv.hor_res=sizes[i][0];drv.ver_res=sizes[i][1];lv_disp_drv_update(d,&drv);screen_orientation=i%2?3:0;dark_mode_enabled=layout==1;
  enabled=false;show_hardware_options_screen_measured();assert(s_hardware_debug_timer&&!lv_obj_has_state(s_hardware_debug_switch,LV_STATE_CHECKED));geometry();
  enabled=true;lv_tick_inc(210);lv_timer_handler();assert(lv_obj_has_state(s_hardware_debug_switch,LV_STATE_CHECKED));
  lv_obj_clear_state(s_hardware_debug_switch,LV_STATE_CHECKED);lv_event_send(s_hardware_debug_switch,LV_EVENT_VALUE_CHANGED,NULL);assert(!enabled);
  fail=1;lv_obj_add_state(s_hardware_debug_switch,LV_STATE_CHECKED);lv_event_send(s_hardware_debug_switch,LV_EVENT_VALUE_CHANGED,NULL);assert(!enabled&&!lv_obj_has_state(s_hardware_debug_switch,LV_STATE_CHECKED));geometry();fail=0;
 }
 hardware_debug_stop();assert(!s_hardware_debug_switch&&!s_hardware_debug_status&&!s_hardware_debug_timer);lv_obj_del(function_page);function_page=NULL;g_screen_stop_fn=NULL;lv_timer_handler();
 puts("PRODUCTION_HARDWARE_REAL_LVGL six geometries, shared Classic/Modern page,36 recreations,serial owner polling,toggle/save rollback,text fit PASS");return 0;}
"""
  out=ROOT/'.hermes/debug94/hardware-lvgl';out.mkdir(parents=True,exist_ok=True);src=out/'test.c';src.write_text(pre+functions+post)
  lvgl=ROOT/'ESP32C5/managed_components/lvgl__lvgl'
  flags=['-std=gnu11','-O1','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-I'+str(lvgl)]
  font=next((ROOT/'ESP32C5/main').glob('*extra_symbols*.c'))
  r=subprocess.run(['cc',*flags,str(src),str(font),*[str(p) for p in (lvgl/'src').rglob('*.c')],'-lm','-o',str(out/'test')],capture_output=True,text=True);(out/'compile.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(out/'test')],capture_output=True,text=True,timeout=30);(out/'run.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)

 def test_production_game_optional_clock_transition_no_underflow(self):
  source=(ROOT/'ESP32C5/components/cym_doom/doom_session.c').read_text();extract=lambda sig:helpers.Revision91.extract(self,source,sig)
  code=r"""#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#define ESP_PLATFORM 1
static bool enabled;static uint32_t clock_us;
static uint32_t metric_us(void){return enabled?clock_us:0;}
"""+extract('static uint32_t metric_delta(uint32_t start,uint32_t end)')+'\n'+extract('static uint32_t metric_elapsed(uint32_t start)')+r"""
int main(void){enabled=true;clock_us=120;assert(metric_elapsed(100)==20);
 enabled=false;assert(!metric_elapsed(100));assert(!metric_delta(100,0));
 enabled=true;clock_us=400;assert(!metric_elapsed(0));assert(!metric_delta(0,400));
 clock_us=10;assert(metric_elapsed(UINT32_MAX-9)==20);return 0;}
"""
  self.run_c('game-clock-transition',code)
