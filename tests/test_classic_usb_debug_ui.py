"""Run the production Classic modal and Hardware Options with real installed LVGL."""
from test_classic_usb_debug_next import NVS_STUB
from pathlib import Path
import os, re, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'ESP32C5/main'

def function(source,name):
    match=re.search(r'^(?:static )?(?:inline )?(?:void|bool|lv_obj_t \*|lv_color_t)\s*'+name+r'\([^;]*?\)\s*\{',source,re.M)
    if not match: raise AssertionError(name)
    a=source.index('{',match.start());depth=1;b=a+1
    while depth:
        depth+=(source[b]=='{')-(source[b]=='}');b+=1
    return source[match.start():b]

PRELUDE=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "lvgl.h"
#include "classic_usb_debug.h"
#define CONFIG_BOARD_CYD2USB 1
#define GPS_UART_NUM 2
/* Production palette below */
#define MY_SYMBOL_TOWER "tower"
#define ESP_LOGE(...) ((void)0)
LV_FONT_DECLARE(lv_extra_symbols);
#include "nvs.h"
static int saved_usb;
esp_err_t nvs_open(const char *n,int mode,nvs_handle_t *h){assert(!strcmp(n,"cym_usb")&&mode==1);*h=1;return 0;}
esp_err_t nvs_get_u8(nvs_handle_t h,const char *k,uint8_t *v){(void)h;(void)k;*v=saved_usb;return 0;}
esp_err_t nvs_set_u8(nvs_handle_t h,const char *k,uint8_t v){(void)h;(void)k;saved_usb=v;return 0;}
esp_err_t nvs_commit(nvs_handle_t h){(void)h;return 0;}
void nvs_close(nvs_handle_t h){(void)h;}
static int screen_orientation;
static bool dark_mode_enabled;
static lv_obj_t *function_page,*s_hardware_debug_switch,*s_hardware_debug_status;
static lv_timer_t *s_hardware_debug_timer;
static void (*g_screen_stop_fn)(void);
static bool g_gps_uart_ready=true,g_gps_nmea_found=true,g_gps_uart_data_seen=true;
static struct {bool valid;} current_gps={true};
static int gps_deletes,uart_starts,uart_stops,reboots,stop_fail,start_fail;
static bool debug_enabled;
static const char *cym_debug_console_status(void){return "Unavailable (board console disabled)";}
static bool cym_debug_enabled(void){return debug_enabled;}
static esp_err_t cym_debug_set(bool v){debug_enabled=v;return 0;}
static bool uart_is_driver_installed(int n){assert(n==2);return !gps_deletes;}
static int uart_driver_delete(int n){assert(n==2&&cym_classic_usb_gps_blocked()&&!g_gps_uart_ready);gps_deletes++;return 0;}
void cym_classic_usb_uart_stats(cym_classic_usb_uart_stats_t *s){*s=(cym_classic_usb_uart_stats_t){0};}
esp_err_t cym_classic_usb_uart_start(void){assert(gps_deletes==1&&!current_gps.valid&&cym_classic_usb_gps_blocked());uart_starts++;return start_fail?ESP_FAIL:ESP_OK;}
esp_err_t cym_classic_usb_uart_stop(void){uart_stops++;return stop_fail?ESP_FAIL:ESP_OK;}
static void esp_restart(void){assert(!stop_fail&&uart_stops>0);reboots++;}
/* PRODUCTION_THEME_HELPERS */
static bool nav_to_menu_flag,g_home_layout_4cat;
static void (*nav_deferred_show_fn)(void),(*g_screen_back_fn)(void);
static int nav_stack_depth=2;
static const char *nav_stack[]={"Settings","Hardware Options"};
static void clock_cancel_radio_navigation(void){}
static void deferred_parent(void){if(g_screen_stop_fn)g_screen_stop_fn();}
static void (*nav_show_lookup(const char *name))(void){assert(!strcmp(name,"Settings"));return deferred_parent;}
static void hw_options_tile_event_cb(lv_event_t *e){(void)e;}
static void apply_menu_bg(void){}
static void create_function_page_base(const char *name){
 assert(!strcmp(name,"Hardware Options"));if(g_screen_stop_fn){g_screen_stop_fn();g_screen_stop_fn=NULL;}
 if(function_page)lv_obj_del(function_page);
 function_page=lv_obj_create(lv_scr_act());lv_obj_set_size(function_page,lv_pct(100),lv_pct(100));
 lv_obj_set_style_border_width(function_page,0,0);lv_obj_set_style_pad_all(function_page,0,0);
 lv_obj_clear_flag(function_page,LV_OBJ_FLAG_SCROLLABLE);
}
static lv_color_t framebuffer[320*320];
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){
 int w=lv_disp_get_hor_res(NULL);
 for(int y=a->y1;y<=a->y2;y++)for(int x=a->x1;x<=a->x2;x++)framebuffer[y*w+x]=*p++;
 lv_disp_flush_ready(d);
}
static const char *evidence;
static void render(const char *name){
 if(!evidence)return;
 lv_obj_invalidate(lv_scr_act());lv_refr_now(NULL);
 char path[1024];snprintf(path,sizeof(path),"%s/%s.ppm",evidence,name);
 FILE *f=fopen(path,"wb");assert(f);int w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);
 fprintf(f,"P6\n%d %d\n255\n",w,h);
 for(int i=0;i<w*h;i++){lv_color32_t c={.full=lv_color_to32(framebuffer[i])};unsigned char rgb[]={c.ch.red,c.ch.green,c.ch.blue};fwrite(rgb,1,3,f);}
 fclose(f);
}
static int failures;
#define CHECK(c) do{if(!(c)){printf("READABILITY FAIL line %d: %s\n",__LINE__,#c);failures++;}}while(0)
static double linear(unsigned x){double s=x/255.;return s<=.04045?s/12.92:pow((s+.055)/1.055,2.4);}
static double luminance(lv_color_t c){lv_color32_t v={.full=lv_color_to32(c)};return .2126*linear(v.ch.red)+.7152*linear(v.ch.green)+.0722*linear(v.ch.blue);}
static double contrast(lv_color_t a,lv_color_t b){double x=luminance(a),y=luminance(b);return (fmax(x,y)+.05)/(fmin(x,y)+.05);}
static void text_style(lv_obj_t *label,lv_color_t foreground,lv_color_t background,const char *name){
 const lv_font_t *font=lv_obj_get_style_text_font(label,0);
 lv_color_t actual=lv_obj_get_style_text_color(label,0);
 printf("STYLE %s fg=%06x bg=%06x text_opa=%d opa=%d font_height=%d contrast=%.2f\n",name,(unsigned)(lv_color_to32(actual)&0xffffff),(unsigned)(lv_color_to32(background)&0xffffff),lv_obj_get_style_text_opa(label,0),lv_obj_get_style_opa(label,0),font->line_height,contrast(actual,background));
 CHECK((actual.full==foreground.full));CHECK(lv_obj_get_style_text_opa(label,0)==LV_OPA_COVER);CHECK(lv_obj_get_style_opa(label,0)==LV_OPA_COVER);
 CHECK(font==&lv_font_montserrat_14||font==&lv_font_montserrat_16);CHECK(contrast(actual,background)>=4.5);
 CHECK(lv_label_get_long_mode(label)==LV_LABEL_LONG_WRAP);
 lv_point_t needed;lv_txt_get_size(&needed,lv_label_get_text(label),font,lv_obj_get_style_text_letter_space(label,0),lv_obj_get_style_text_line_space(label,0),lv_obj_get_width(label),LV_TEXT_FLAG_NONE);
 CHECK(lv_obj_get_height(label)>=needed.y);
}
static void button_style(lv_obj_t *button,const char *name){
 lv_obj_t *label=lv_obj_get_child(button,0);
 text_style(label,dark_mode_enabled?COLOR_DARK_BG:lv_color_white(),lv_obj_get_style_bg_color(button,0),name);
 CHECK((lv_obj_get_style_bg_color(button,0).full==ui_accent_color().full));
 CHECK(lv_obj_get_style_bg_opa(button,0)==LV_OPA_COVER);CHECK(lv_obj_get_style_opa(button,0)==LV_OPA_COVER);
 lv_area_t a,b;lv_obj_get_coords(button,&a);lv_obj_get_coords(label,&b);
 CHECK(b.x1>=a.x1&&b.x2<=a.x2&&b.y1>=a.y1&&b.y2<=a.y2);
 lv_obj_add_state(button,LV_STATE_PRESSED);lv_tick_inc(200);lv_timer_handler();lv_obj_update_layout(button);
 CHECK(contrast(lv_obj_get_style_text_color(label,0),lv_obj_get_style_bg_color(button,0))>=4.5);
 CHECK(lv_obj_get_style_text_opa(label,0)==LV_OPA_COVER);
 lv_obj_clear_state(button,LV_STATE_PRESSED);lv_tick_inc(200);lv_timer_handler();
}
"""
POST=r"""
static void visible_button(lv_obj_t *obj){
 lv_obj_scroll_to_view(obj,LV_ANIM_OFF);lv_obj_update_layout(lv_scr_act());
 lv_area_t a;lv_obj_get_coords(obj,&a);
 assert(a.x1>=0&&a.y1>=0&&a.x2<lv_disp_get_hor_res(NULL)&&a.y2<lv_disp_get_ver_res(NULL));
}
static void open_popup(void){
 show_hardware_options_screen_measured();
 lv_obj_t *tiles=lv_obj_get_child(function_page,0);assert(lv_obj_get_child_cnt(tiles)==3);
 lv_obj_t *button=lv_obj_get_child(tiles,2);visible_button(button);
 lv_event_send(button,LV_EVENT_CLICKED,NULL);assert(s_classic_usb_popup);
 lv_obj_update_layout(lv_scr_act());
 assert(lv_obj_get_height(s_classic_usb_popup)==lv_disp_get_ver_res(NULL)-12);
 assert(lv_obj_get_scroll_dir(s_classic_usb_popup)==LV_DIR_VER);
 /* Every action is reachable by scrolling, not clipped beyond physical screen. */
 for(int i=2;i<5;i++)visible_button(lv_obj_get_child(s_classic_usb_popup,i));
}
static int lifecycle(void){
 lv_init();static lv_color_t pixels[320*20];static lv_disp_draw_buf_t buf;
 lv_disp_draw_buf_init(&buf,pixels,NULL,320*20);static lv_disp_drv_t drv;
 lv_disp_drv_init(&drv);drv.hor_res=240;drv.ver_res=320;drv.draw_buf=&buf;drv.flush_cb=flush;
 lv_disp_t *d=lv_disp_drv_register(&drv);
 for(int active=0;active<2;active++)for(int theme=0;theme<2;theme++)for(int orient=0;orient<2;orient++)for(int cycle=0;cycle<3;cycle++){
  drv.hor_res=orient?320:240;drv.ver_res=orient?240:320;lv_disp_drv_update(d,&drv);
  dark_mode_enabled=theme;screen_orientation=orient?3:0;
  open_popup();assert(cym_classic_usb_active()==(active==1));
  if(!active){
   assert(!gps_deletes&&!uart_starts&&!cym_classic_usb_gps_blocked());
   lv_event_send(lv_obj_get_child(s_classic_usb_popup,4),LV_EVENT_CLICKED,NULL);
   assert(!s_classic_usb_popup&&!cym_classic_usb_gps_blocked());
   open_popup();
  }
  /* Back/Home invokes the same stop hook: no stale modal/timer pointer. */
  g_screen_stop_fn();assert(!s_classic_usb_popup&&!s_classic_usb_popup_status&&!s_hardware_classic_status&&!s_hardware_debug_timer);
  lv_tick_inc(220);lv_timer_handler();assert(cym_classic_usb_active()==(active==1));
  if(!active&&theme==1&&orient==1&&cycle==2){
   open_popup();lv_event_send(lv_obj_get_child(s_classic_usb_popup,2),LV_EVENT_CLICKED,NULL);
   assert(cym_classic_usb_active()&&gps_deletes==1&&uart_starts==1&&!g_gps_uart_ready&&!current_gps.valid);
   classic_usb_popup_close();
  }
 }
 open_popup();classic_usb_enable_event(NULL);assert(uart_starts==1);
 stop_fail=1;classic_usb_reboot_event(NULL);assert(reboots==0&&cym_classic_usb_gps_blocked());
 stop_fail=0;classic_usb_reboot_event(NULL);assert(reboots==1&&!cym_classic_usb_active());
 hardware_debug_stop();assert(!s_classic_usb_popup&&!s_hardware_debug_timer);
 lv_obj_del(function_page);function_page=NULL;g_screen_stop_fn=NULL;
 lv_tick_inc(250);lv_timer_handler();
 puts("REAL_LVGL Classic USB popup: 24 lifecycle cycles, light/dark, portrait/landscape, cancel/ack/Back/Home/reentry/stop-failure/reboot PASS");return 0;
}
static int readability(int theme,int orient,int navigation,int state){
 lv_init();static lv_color_t pixels[320*20];static lv_disp_draw_buf_t buf;
 lv_disp_draw_buf_init(&buf,pixels,NULL,320*20);static lv_disp_drv_t drv;
 lv_disp_drv_init(&drv);drv.hor_res=orient?320:240;drv.ver_res=orient?240:320;drv.draw_buf=&buf;drv.flush_cb=flush;
 lv_disp_drv_register(&drv);dark_mode_enabled=theme;screen_orientation=orient?3:0;
 evidence=getenv("CYM_CLASSIC_UI_EVIDENCE");char name[128];g_home_layout_4cat=navigation;
 for(int cycle=0;cycle<2;cycle++){
  show_hardware_options_screen_measured();lv_obj_update_layout(lv_scr_act());
  lv_obj_t *entry=lv_obj_get_child(lv_obj_get_child(function_page,0),2);
  visible_button(entry);button_style(entry,"Hardware entry");
  snprintf(name,sizeof(name),"%s-%s-nav%d-state%d-entry",theme?"dark":"light",orient?"landscape":"portrait",navigation,state);if(!cycle)render(name);
  lv_event_send(entry,LV_EVENT_CLICKED,NULL);lv_obj_update_layout(lv_scr_act());
  if(state==1)classic_usb_enable_event(NULL);
  if(state==2){start_fail=1;classic_usb_enable_event(NULL);}
  if(state==3){classic_usb_enable_event(NULL);stop_fail=1;classic_usb_reboot_event(NULL);CHECK(reboots==0);}
  lv_obj_update_layout(lv_scr_act());
  CHECK(strstr(lv_label_get_text(lv_obj_get_child(s_classic_usb_popup,0)),"Saved across reboot"));
  CHECK(strstr(lv_label_get_text(lv_obj_get_child(s_classic_usb_popup,0)),"Debug OFF plus reboot"));
  CHECK(lv_obj_get_style_bg_opa(s_classic_usb_popup,0)==LV_OPA_COVER);
  CHECK((lv_obj_get_style_bg_color(s_classic_usb_popup,0).full==ui_panel_color().full));
  text_style(lv_obj_get_child(s_classic_usb_popup,0),ui_text_color(),ui_panel_color(),"warning");
  text_style(s_classic_usb_popup_status,ui_text_color(),ui_panel_color(),"status");
  const char *status=lv_label_get_text(s_classic_usb_popup_status);
  if(state==0)CHECK(!cym_classic_usb_active()&&!gps_deletes&&!uart_starts);
  if(state==1)CHECK(strstr(status,"ON - 115200")&&cym_classic_usb_active());
  if(state==2)CHECK(strstr(status,"Enable failed")&&!cym_classic_usb_active()&&cym_classic_usb_gps_blocked());
  if(state==3)CHECK(strstr(status,"TX shutdown failed")&&cym_classic_usb_gps_blocked());
  lv_obj_scroll_to_y(s_classic_usb_popup,0,LV_ANIM_OFF);lv_obj_update_layout(lv_scr_act());
  snprintf(name,sizeof(name),"%s-%s-nav%d-state%d-warning",theme?"dark":"light",orient?"landscape":"portrait",navigation,state);if(!cycle)render(name);
  visible_button(s_classic_usb_popup_status);
  for(int i=2;i<5;i++){
   lv_obj_t *button=lv_obj_get_child(s_classic_usb_popup,i);visible_button(button);button_style(button,"popup action");
   snprintf(name,sizeof(name),"%s-%s-nav%d-state%d-action%d",theme?"dark":"light",orient?"landscape":"portrait",navigation,state,i-2);if(!cycle)render(name);
  }
  bool before=cym_classic_usb_active();
  lv_event_send(lv_obj_get_child(s_classic_usb_popup,4),LV_EVENT_CLICKED,NULL);
  CHECK(!s_classic_usb_popup&&cym_classic_usb_active()==before);
  show_classic_usb_popup();CHECK(s_classic_usb_popup);
  nav_to_menu_flag=false;nav_deferred_show_fn=NULL;
  if(cycle==0){
   nav_back_cb(NULL);CHECK(nav_deferred_show_fn==deferred_parent&&!nav_to_menu_flag);
   CHECK(s_classic_usb_popup);nav_deferred_show_fn();nav_deferred_show_fn=NULL;
  }else{
   home_btn_event_cb(NULL);CHECK(nav_to_menu_flag&&s_classic_usb_popup);
   /* Main loop dispatches show_menu; its production layout/stop contract is pinned below. */
   deferred_parent();nav_to_menu_flag=false;
  }
  CHECK(!s_classic_usb_popup&&!s_classic_usb_popup_status&&!s_hardware_classic_status&&!s_hardware_debug_timer);
  CHECK(cym_classic_usb_active()==before);
  lv_obj_del(function_page);function_page=NULL;g_screen_stop_fn=NULL;
  lv_tick_inc(250);lv_timer_handler();
 }
 printf("REAL_LVGL readability theme=%d orientation=%d navigation=%d state=%d failures=%d\n",theme,orient,navigation,state,failures);
 return failures?1:0;
}
int main(int argc,char **argv){
 setbuf(stdout,NULL);
 if(argc==5)return readability(atoi(argv[1]),atoi(argv[2]),atoi(argv[3]),atoi(argv[4]));
 return lifecycle();
}

"""
class ClassicUsbUI(unittest.TestCase):
    def test_both_home_navigation_contracts(self):
        source=(MAIN/'main.c').read_text()
        for name in ['show_cat_tools','show_main_tiles']:
            self.assertRegex(function(source,name),r'"Settings".*main_tile_event_cb, "Settings"')
        self.assertIn('show_settings_screen();',function(source,'settings_nav_timer_cb'))
        self.assertRegex(function(source,'show_settings_screen_measured'),r'settings_tile_event_cb, "Hardware Options"')
        self.assertIn('show_hardware_options_screen();',function(source,'settings_tile_event_cb_measured'))
        menu=function(source,'show_menu')
        self.assertIn('run_screen_stop_fn();',menu)
        self.assertIn('g_screen_stop_fn',function(source,'run_screen_stop_fn'))
        self.assertIn('if (g_home_layout_4cat) show_category_home();',menu)
        self.assertRegex(menu,r'else\s+show_main_tiles\(\);')
        self.assertIn('g_screen_stop_fn = hardware_debug_stop;',function(source,'show_hardware_options_screen_measured'))

    def test_production_popup_real_lvgl(self):
        source=(MAIN/'main.c').read_text()
        ui=source[source.index('static lv_obj_t *s_classic_usb_popup,'):source.index('/* Hardware objects and timer')]
        ui=ui.rsplit('#endif',1)[0]
        palette=source[source.index('#define COLOR_DARK_BG '):source.index('// WPA-SEC upload constants')]
        palette=palette.replace('static bool dark_mode_enabled = true;', '')
        code=PRELUDE.replace('/* PRODUCTION_THEME_HELPERS */',palette)
        if "static void classic_usb_style_action(" in source:
            code+=function(source,"classic_usb_style_action")+"\n"
        code+=ui
        for name in ['nav_back_cb','home_btn_event_cb','create_tile','hardware_debug_sync','hardware_debug_stop','hardware_debug_event','show_hardware_options_screen_measured']:
            code+=function(source,name)+'\n'
        code+=POST
        with tempfile.TemporaryDirectory(prefix='classic-lvgl-',dir=os.environ['TMPDIR']) as tmp:
            d=Path(tmp);(d/'test.c').write_text(code);(d/'nvs.h').write_text(NVS_STUB)
            (d/'esp_err.h').write_text('#pragma once\ntypedef int esp_err_t;\n#define ESP_OK 0\n#define ESP_FAIL -1\n#define ESP_ERR_INVALID_ARG 0x102\n#define ESP_ERR_INVALID_STATE 0x103\n#define ESP_ERR_NOT_SUPPORTED 0x106\n')
            (d/'sdkconfig.h').write_text('#define CONFIG_BOARD_CYD2USB 1\n')
            lvgl=ROOT/'ESP32C5/managed_components/lvgl__lvgl'
            flags=['-std=gnu11','-O1','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-DLV_FONT_MONTSERRAT_14=1','-DLV_FONT_MONTSERRAT_16=1','-DLV_COLOR_DEPTH=16','-I'+str(lvgl),'-I'+str(d),'-I'+str(MAIN)]
            cmd=['cc',*flags,str(d/'test.c'),str(MAIN/'classic_usb_debug.c'),str(MAIN/'lv_extra_symbols.c'),*[str(p) for p in (lvgl/'src').rglob('*.c')],'-lm','-o',str(d/'test')]
            r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([str(d/'test')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr);print(r.stdout)
            results=[]
            for theme in range(2):
                for orient in range(2):
                    for navigation in range(2):
                        for state in range(4):
                            r=subprocess.run([str(d/'test'),str(theme),str(orient),str(navigation),str(state)],capture_output=True,text=True)
                            print(r.stdout+r.stderr)
                            results.append(r.returncode)
            self.assertEqual(results,[0]*32,'Computed production palette/styles/geometry failed; see STYLE output')

if __name__=='__main__':unittest.main()
