"""Run the production Classic modal and Hardware Options with real installed LVGL."""
from pathlib import Path
import os, re, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'ESP32C5/main'

def function(source,name):
    match=re.search(r'^(?:static )?[^;\n]+\b'+name+r'\([^;]*?\)\s*\{',source,re.M)
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
#include "lvgl.h"
#include "classic_usb_debug.h"
#define CONFIG_BOARD_CYD2USB 1
#define GPS_UART_NUM 2
#define COLOR_MATERIAL_RED lv_color_hex(0xf44336)
#define MY_SYMBOL_TOWER "tower"
#define ESP_LOGE(...) ((void)0)
LV_FONT_DECLARE(lv_extra_symbols);
static int screen_orientation;
static bool dark_mode_enabled;
static lv_obj_t *function_page,*s_hardware_debug_switch,*s_hardware_debug_status;
static lv_timer_t *s_hardware_debug_timer;
static void (*g_screen_stop_fn)(void);
static bool g_gps_uart_ready=true,g_gps_nmea_found=true,g_gps_uart_data_seen=true;
static struct {bool valid;} current_gps={true};
static int gps_deletes,uart_starts,uart_stops,reboots,stop_fail;
static bool debug_enabled;
static const char *cym_debug_console_status(void){return "Unavailable (board console disabled)";}
static bool cym_debug_enabled(void){return debug_enabled;}
static esp_err_t cym_debug_set(bool v){debug_enabled=v;return 0;}
static bool uart_is_driver_installed(int n){assert(n==2);return !gps_deletes;}
static int uart_driver_delete(int n){assert(n==2&&cym_classic_usb_gps_blocked()&&!g_gps_uart_ready);gps_deletes++;return 0;}
esp_err_t cym_classic_usb_uart_start(void){assert(gps_deletes==1&&!current_gps.valid&&cym_classic_usb_gps_blocked());uart_starts++;return 0;}
esp_err_t cym_classic_usb_uart_stop(void){uart_stops++;return stop_fail?ESP_FAIL:ESP_OK;}
static void esp_restart(void){assert(!stop_fail&&uart_stops>0);reboots++;}
static lv_color_t ui_card_color(void){return dark_mode_enabled?lv_color_hex(0x303030):lv_color_white();}
static lv_color_t ui_panel_color(void){return ui_card_color();}
static lv_color_t ui_card_pressed_color(void){return lv_color_hex(0x404040);}
static lv_color_t ui_border_color(void){return lv_color_hex(0x555555);}
static lv_color_t ui_text_color(void){return dark_mode_enabled?lv_color_white():lv_color_black();}
static void hw_options_tile_event_cb(lv_event_t *e){(void)e;}
static void apply_menu_bg(void){}
static void create_function_page_base(const char *name){
 assert(!strcmp(name,"Hardware Options"));if(g_screen_stop_fn){g_screen_stop_fn();g_screen_stop_fn=NULL;}
 if(function_page)lv_obj_del(function_page);
 function_page=lv_obj_create(lv_scr_act());lv_obj_set_size(function_page,lv_pct(100),lv_pct(100));
 lv_obj_set_style_border_width(function_page,0,0);lv_obj_set_style_pad_all(function_page,0,0);
 lv_obj_clear_flag(function_page,LV_OBJ_FLAG_SCROLLABLE);
}
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){(void)a;(void)p;lv_disp_flush_ready(d);}
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
int main(void){
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
 puts("REAL_LVGL Classic USB popup: 24 lifecycle cycles, light/dark, portrait/landscape, cancel/ack/Back/Home/reentry/stop-failure/reboot PASS");
}
"""
class ClassicUsbUI(unittest.TestCase):
    def test_production_popup_real_lvgl(self):
        source=(MAIN/'main.c').read_text()
        ui=source[source.index('static lv_obj_t *s_classic_usb_popup,'):source.index('/* Hardware objects and timer')]
        ui=ui.rsplit('#endif',1)[0]
        code=PRELUDE+ui
        for name in ['create_tile','hardware_debug_sync','hardware_debug_stop','hardware_debug_event','show_hardware_options_screen_measured']:
            code+=function(source,name)+'\n'
        code+=POST
        with tempfile.TemporaryDirectory(prefix='classic-lvgl-',dir=os.environ['TMPDIR']) as tmp:
            d=Path(tmp);(d/'test.c').write_text(code)
            (d/'esp_err.h').write_text('#pragma once\ntypedef int esp_err_t;\n#define ESP_OK 0\n#define ESP_FAIL -1\n#define ESP_ERR_INVALID_ARG 0x102\n#define ESP_ERR_INVALID_STATE 0x103\n#define ESP_ERR_NOT_SUPPORTED 0x106\n')
            (d/'sdkconfig.h').write_text('#define CONFIG_BOARD_CYD2USB 1\n')
            lvgl=ROOT/'ESP32C5/managed_components/lvgl__lvgl'
            flags=['-std=gnu11','-O1','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-I'+str(lvgl),'-I'+str(d),'-I'+str(MAIN)]
            cmd=['cc',*flags,str(d/'test.c'),str(MAIN/'classic_usb_debug.c'),str(MAIN/'lv_extra_symbols.c'),*[str(p) for p in (lvgl/'src').rglob('*.c')],'-lm','-o',str(d/'test')]
            r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([str(d/'test')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr);print(r.stdout)

if __name__=='__main__':unittest.main()
