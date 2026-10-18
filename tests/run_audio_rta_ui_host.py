#!/usr/bin/env python3
"""Production Audio RTA UI/glyph/tile against real pinned LVGL; synthetic SDK/session."""
from pathlib import Path
import os,subprocess,re
R=Path(__file__).resolve().parents[1];M=R/'ESP32C5/main';LV=R/'ESP32C5/managed_components/lvgl__lvgl';D=Path(os.environ['CYM_TEST_OUT'])/'rta-ui';D.mkdir(parents=True,exist_ok=True)
(D/'esp_err.h').write_text('typedef int esp_err_t;\n#define ESP_OK 0\n#define ESP_FAIL -1\n#define ESP_ERR_NO_MEM 257\n#define ESP_ERR_INVALID_STATE 3\n')
main=(M/'main.c').read_text()
def function(name):
 m=re.search(r'(?:static )?(?:lv_obj_t \*|void )'+name+r'\([^;]*?\)\s*\{',main);assert m,name
 i=m.end();depth=1
 while depth:depth+=(main[i]=='{')-(main[i]=='}');i+=1
 return main[m.start():i]
pre=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "lvgl.h"
#include "audio_rta.h"
#define BOARD_HAS_AUDIO_RTA 1
#define RTA_MIC_SYMBOL "\xEE\x84\x80"
LV_FONT_DECLARE(audio_rta_mic_font);
static bool dark_mode_enabled=true,g_home_layout_4cat;
static int screen_orientation;
static lv_obj_t *function_page;
static void(*g_screen_stop_fn)(void),(*g_screen_back_fn)(void);
static int stops,starts,controls,parent_seen,home_seen,forced_error;
static uint32_t gen;
static audio_rta_snapshot_t fake;
#define UI_ACCENT_BLUE lv_color_hex(0x1565c0)
#define UI_ACCENT_CYAN lv_color_hex(0x00bcd4)
#define UI_ACCENT_GREEN lv_color_hex(0x008800)
#define LV_SYMBOL_SETTINGS "S"
#define MY_SYMBOL_MICROCHIP "M"
#define MY_SYMBOL_WAVE "W"
#define MY_SYMBOL_CLOCK "C"
#define MY_SYMBOL_CAMERA "Q"
LV_FONT_DECLARE(lv_extra_symbols);
static lv_color_t ui_card_color(void){return lv_color_hex(0x111827);}
static lv_color_t ui_card_pressed_color(void){return lv_color_hex(0x334155);}
static lv_color_t ui_border_color(void){return lv_color_hex(0x475569);}
static lv_color_t ui_text_color(void){return lv_color_white();}
static void show_audio_rta(void);
static void show_cat_tools(void){parent_seen++;}
static void show_main_tiles(void){home_seen++;}
static void apply_menu_bg(void){}
static void create_function_page_base(const char*n){assert(!strcmp(n,"Audio RTA"));if(g_screen_stop_fn){g_screen_stop_fn();g_screen_stop_fn=NULL;}lv_obj_clean(lv_scr_act());function_page=lv_obj_create(lv_scr_act());lv_obj_remove_style_all(function_page);lv_obj_set_size(function_page,lv_disp_get_hor_res(NULL),lv_disp_get_ver_res(NULL));lv_obj_t*t=lv_obj_create(function_page);lv_obj_set_size(t,lv_pct(100),30);lv_obj_set_pos(t,0,0);}
static void*ws_c5_35_i2c_bus(void){return (void*)1;}
static const char*esp_err_to_name(int e){(void)e;return "ESP_ERR_SYNTHETIC_LONG_CODEC_OR_ALLOCATION_FAILURE";}
esp_err_t audio_rta_start(void*b,uint32_t*g){assert(b);starts++;*g=++gen;memset(&fake,0,sizeof(fake));fake.generation=gen;fake.state=RTA_RUNNING;fake.spectrum.valid=0xffffff;for(int i=0;i<24;i++){fake.spectrum.band[i]=-60+i*2;fake.spectrum.peak[i]=-50+i*2;}return 0;}
bool audio_rta_snapshot(uint32_t g,audio_rta_snapshot_t*s){assert(g==gen);*s=fake;return true;}
void audio_rta_controls(uint32_t g,bool f,bool slow,int gain,bool reset){assert(g==gen);(void)slow;(void)reset;controls++;fake.state=f?RTA_FROZEN:RTA_RUNNING;fake.gain_db=gain;}
void audio_rta_stop(uint32_t g){if(g)stops++;}
bool audio_rta_closed(void){return true;}
static void main_tile_event_cb(lv_event_t*e){assert(!strcmp(lv_event_get_user_data(e),"Audio RTA"));show_audio_rta();}
"""
post=r"""
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){(void)a;(void)p;lv_disp_flush_ready(d);}
static void within(lv_obj_t*o){lv_area_t a;lv_obj_get_coords(o,&a);assert(a.x1>=0&&a.y1>=30&&a.x2<lv_disp_get_hor_res(NULL)&&a.y2<lv_disp_get_ver_res(NULL));}
static void render(void){lv_obj_update_layout(lv_scr_act());lv_refr_now(NULL);}
int main(void){lv_init();static lv_color_t pixels[480*32];lv_disp_draw_buf_t buf;lv_disp_draw_buf_init(&buf,pixels,NULL,480*32);lv_disp_drv_t drv;lv_disp_drv_init(&drv);drv.hor_res=320;drv.ver_res=480;drv.draw_buf=&buf;drv.flush_cb=flush;lv_disp_t*disp=lv_disp_drv_register(&drv);
 lv_font_glyph_dsc_t glyph;assert(audio_rta_mic_font.get_glyph_dsc(&audio_rta_mic_font,&glyph,0xe100,0));assert(glyph.box_w==14&&glyph.box_h==21&&glyph.bpp==1);assert(!audio_rta_mic_font.get_glyph_dsc(&audio_rta_mic_font,&glyph,'X',0));const uint8_t*bm=audio_rta_mic_font.get_glyph_bitmap(&audio_rta_mic_font,0xe100);int ink=0;for(int i=0;i<37;i++)ink+=bm[i]!=0;assert(ink>20);
 for(int layout=0;layout<2;layout++)for(int rot=0;rot<4;rot++){
  g_home_layout_4cat=layout;screen_orientation=rot;lv_disp_set_rotation(disp,(lv_disp_rot_t)rot);lv_obj_clean(lv_scr_act());lv_obj_t*tile=lv_obj_create(lv_scr_act());lv_obj_set_size(tile,200,100);create_tile(tile,RTA_MIC_SYMBOL,"Audio RTA",UI_ACCENT_CYAN,main_tile_event_cb,"Audio RTA");lv_obj_t*btn=lv_obj_get_child(tile,0);lv_obj_t*icon=lv_obj_get_child(btn,0);assert(lv_obj_get_style_text_font(icon,0)==&audio_rta_mic_font);lv_event_send(btn,LV_EVENT_CLICKED,NULL);render();assert(g_screen_stop_fn==audio_rta_ui_stop);assert(g_screen_back_fn==(layout?show_cat_tools:show_main_tiles));
  rta_selected=0;fake.spectrum.age[0]=4800;rta_refresh(NULL);assert(!strcmp(lv_label_get_text(rta_detail),"20.00-26.67 Hz  -60.0 dBFS\nAge 100 ms / 683 ms bass window"));fake.spectrum.valid &= ~1u;rta_refresh(NULL);assert(!strcmp(lv_label_get_text(rta_detail),"20.00-26.67 Hz / warming up\nBass needs 683 ms of fresh input"));fake.spectrum.valid |= 1u;rta_refresh(NULL); fake.sequence=1; fake.spectrum.rms=-23.5f; fake.spectrum.sample_peak=-6.25f; rta_refresh(NULL); assert(strstr(lv_label_get_text(rta_status),"RMS -23.5 Pk -6.2") && strstr(lv_label_get_text(rta_status),"Clips 0")); within(rta_status);within(rta_chart);within(rta_detail);for(unsigned i=3;i<lv_obj_get_child_cnt(rta_body);i++){lv_obj_t*b=lv_obj_get_child(rta_body,i);within(b);assert(lv_obj_get_height(b)>=44);}
  lv_obj_t*gain=lv_obj_get_parent(rta_gain_label);lv_event_send(gain,LV_EVENT_CLICKED,NULL);render();assert(rta_overlay);within(rta_overlay);assert(lv_obj_get_scroll_dir(rta_overlay)==LV_DIR_VER);lv_obj_t*choice=lv_obj_get_child(rta_overlay,2);lv_event_send(choice,LV_EVENT_CLICKED,NULL);render();assert(!rta_overlay&&fake.gain_db==6);
  char prior_detail[160],prior_gain[32];snprintf(prior_detail,sizeof(prior_detail),"%s",lv_label_get_text(rta_detail));snprintf(prior_gain,sizeof(prior_gain),"%s",lv_label_get_text(rta_gain_label));fake.state=RTA_ERROR;fake.error=ESP_ERR_NO_MEM;fake.gain_db=42;fake.spectrum.band[0]=0;rta_refresh(NULL);assert(strstr(lv_label_get_text(rta_status),"(257). Back/Home exits safely.") && strstr(lv_label_get_text(rta_status),"Insufficient memory is not retried automatically."));assert(!strcmp(prior_detail,lv_label_get_text(rta_detail)) && !strcmp(prior_gain,lv_label_get_text(rta_gain_label)));assert(lv_obj_has_flag(rta_chart,LV_OBJ_FLAG_HIDDEN));fake.error=-1;rta_refresh(NULL);render();assert(lv_obj_get_scroll_dir(rta_body)==LV_DIR_VER);within(rta_status);
  int old=stops;g_screen_stop_fn();assert(stops==old+1&&!rta_timer&&!rta_status&&!rta_chart&&!rta_detail&&!rta_overlay&&!rta_generation);g_screen_stop_fn();assert(stops==old+1);g_screen_stop_fn=NULL;g_screen_back_fn();lv_obj_clean(lv_scr_act());
 }
 assert(starts==8&&stops==8&&controls==8&&parent_seen==4&&home_seen==4);printf("PASS production UI: 2 menu tile layouts x4 rotations; real LVGL/glyph/draw, 44px controls, bounded gain, long error scrolling, copied model and idempotent detach\n");return 0;}
"""
(D/'host.c').write_text(pre+'\n'+function('create_tile')+'\n'+(M/'audio_rta_ui.inc').read_text()+'\n'+post)
flags=['-std=gnu11','-O1','-g','-fsanitize=address,undefined','-DLV_CONF_SKIP=1','-DLV_SPRINTF_USE_FLOAT=0','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-I'+str(LV),'-I'+str(D),'-I'+str(M)]
with (D/'compile.log').open('w') as f:subprocess.run(['cc',*flags,str(D/'host.c'),str(M/'audio_rta_dsp.c'),str(M/'audio_rta_mic.c'),str(M/'lv_extra_symbols.c'),*[str(p) for p in (LV/'src').rglob('*.c')],'-lm','-o',str(D/'host')],stdout=f,stderr=subprocess.STDOUT,check=True)
env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=0'
subprocess.run([str(D/'host')],env=env,check=True)
