#!/usr/bin/env python3
"""Installed LVGL 8.4 + full Messenger UI include, no device/network operations.
Requires managed LVGL, cc; core uses a synthetic no-auth harness endpoint only.
"""
from pathlib import Path
import os,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'messenger-lvgl';D.mkdir(parents=True,exist_ok=True)
LV=R/'ESP32C5/managed_components/lvgl__lvgl';assert (LV/'src/core/lv_obj.c').is_file()
pre=r"""
#include "lvgl.h"
#include "cym_messenger.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CONFIG_BOARD_HAS_RF_HAT 1
#define UI_ACCENT_CYAN lv_color_hex(0x00bcd4)
#define UI_ACCENT_BLUE lv_color_hex(0x2196f3)
static lv_obj_t *function_page;static void(*g_screen_stop_fn)(void),(*g_screen_back_fn)(void);
static bool g_home_layout_4cat,g_rf_hat_enabled,light;static int sends,stops,starts;
static cym_messenger_status snapshot;
static lv_color_t ui_bg_color(void){return lv_color_hex(light?0xeeeeee:0x111111);}
static lv_color_t ui_text_color(void){return lv_color_hex(light?0x111111:0xeeeeee);}
static lv_color_t ui_card_color(void){return ui_bg_color();}
static lv_color_t ui_border_color(void){return lv_color_hex(0x888888);}
static lv_color_t ui_accent_color(void){return UI_ACCENT_CYAN;}
static void show_cat_tools(void){} static void show_main_tiles(void){}static void apply_menu_bg(void){}
static void create_function_page_base(const char *title){(void)title;if(g_screen_stop_fn)g_screen_stop_fn();g_screen_stop_fn=NULL;if(function_page)lv_obj_del(function_page);function_page=lv_obj_create(lv_scr_act());lv_obj_set_size(function_page,lv_pct(100),lv_pct(100));lv_obj_set_style_pad_all(function_page,0,0);lv_obj_set_style_border_width(function_page,0,0);lv_obj_clear_flag(function_page,LV_OBJ_FLAG_SCROLLABLE);}
bool cym_messenger_start(const cym_messenger_config*c){(void)c;starts++;return true;}
void cym_messenger_stop(void){stops++;}bool cym_messenger_busy(void){return false;}
bool cym_messenger_send(const char*t,size_t n){(void)t;(void)n;sends++;return snapshot.can_send;}
void cym_messenger_snapshot(cym_messenger_status *out){*out=snapshot;}
bool cym_messenger_take(cm_message*m){(void)m;return false;}
bool cym_messenger_key_request(void){return true;}bool cym_messenger_info_request(void){return true;}
bool cym_messenger_key_take(char k[33]){(void)k;return false;}
bool cym_messenger_parse_key(const char*t,uint8_t*k){(void)t;(void)k;return false;}
bool cym_messenger_parse_mac(const char*t,uint8_t*k){(void)t;(void)k;return false;}
"""
post=r"""
static int checks,failures;
#define CHECK(x,n) do{checks++;if(!(x)){failures++;printf("FAIL %s\n",n);}}while(0)
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*c){(void)a;(void)c;lv_disp_flush_ready(d);}
static int timer_count(void){int n=0;lv_timer_t*t=NULL;while((t=lv_timer_get_next(t)))n++;return n;}
int main(void){setbuf(stdout,NULL);lv_init();static lv_color_t pixels[800*20];static lv_disp_draw_buf_t buf;lv_disp_draw_buf_init(&buf,pixels,NULL,800*20);
 lv_disp_drv_t dr;lv_disp_drv_init(&dr);dr.hor_res=240;dr.ver_res=320;dr.draw_buf=&buf;dr.flush_cb=flush;lv_disp_t*d=lv_disp_drv_register(&dr);
 const int dims[][2]={{240,320},{320,240},{320,480},{480,320},{480,800},{800,480}};
 for(int layout=0;layout<2;layout++)for(int theme=0;theme<2;theme++)for(int dim=0;dim<6;dim++){
  g_home_layout_4cat=layout;light=theme;dr.hor_res=dims[dim][0];dr.ver_res=dims[dim][1];lv_disp_drv_update(d,&dr);int timers=timer_count();
  show_messenger_screen();CHECK(msg_ui!=NULL,"lazy UI created");CHECK(g_screen_back_fn==(layout?show_cat_tools:show_main_tiles),"Classic/Modern Back route");CHECK(lv_textarea_get_password_mode(msg_ui->key),"key initially masked");
  messenger_key_reveal(NULL);CHECK(!lv_textarea_get_password_mode(msg_ui->key),"reveal explicit");messenger_key_reveal(NULL);
  lv_textarea_set_text(msg_ui->composer,"\xc3\xa9");messenger_count();CHECK(strstr(lv_label_get_text(msg_ui->counter),"2 / 160")!=NULL,"byte counter not Unicode count");
  for(int protocol=1;protocol<5;protocol++){
   lv_dropdown_set_selected(msg_ui->selector,protocol);messenger_protocol(NULL);CHECK(!strcmp(lv_textarea_get_text(msg_ui->composer),"\xc3\xa9"),"protocol draft untouched");int before=sends;messenger_send_click(NULL);CHECK(sends==before,"planned protocol never sends");
   if(protocol==4)CHECK(strstr(lv_label_get_text(msg_ui->hint),"unavailable")!=NULL,"HAT-disabled IR unavailable");
  }
  g_rf_hat_enabled=true;messenger_protocol(NULL);CHECK(strstr(lv_label_get_text(msg_ui->hint),"not physically detected")!=NULL,"configured not detected");g_rf_hat_enabled=false;
  lv_dropdown_set_selected(msg_ui->selector,0);messenger_protocol(NULL);snapshot.state=MSG_READY;snapshot.can_send=true;messenger_poll(NULL);
  lv_event_send(msg_ui->composer,LV_EVENT_CLICKED,NULL);lv_obj_update_layout(function_page);CHECK(!lv_obj_has_flag(msg_ui->keyboard,LV_OBJ_FLAG_HIDDEN),"keyboard reachable");
  lv_area_t kb,send;lv_obj_get_coords(msg_ui->keyboard,&kb);lv_obj_get_coords(msg_ui->send,&send);CHECK(send.y2<kb.y1,"Send stays above keyboard");CHECK(send.x1>=0&&send.x2<dims[dim][0],"Send fits screen width");
  int before=sends;messenger_send_click(NULL);CHECK(sends==before+1,"real Send callback routes");CHECK(!*lv_textarea_get_text(msg_ui->composer),"successful enqueue clears composer");
  char longtext[322];for(int i=0;i<160;i++){longtext[2*i]=(char)0xc3;longtext[2*i+1]=(char)0xa9;}longtext[320]=0;
  lv_textarea_set_text(msg_ui->composer,longtext);messenger_count();CHECK(strstr(lv_label_get_text(msg_ui->counter),"320 / 160")!=NULL,"overbyte draft retained not truncated by byte count");before=sends;messenger_send_click(NULL);CHECK(sends==before,"overbyte Send refused");
  for(int i=0;i<12;i++)messenger_row("Peer:","synthetic");CHECK(lv_obj_get_child_cnt(msg_ui->history)==4,"bounded conversation");
  snapshot.delivery=CM_UNCONFIRMED;messenger_poll(NULL);CHECK(strstr(lv_label_get_text(msg_ui->state),"may have arrived")!=NULL,"timeout truthful");
  before=stops;g_screen_stop_fn();g_screen_stop_fn=NULL;CHECK(stops==before+1&&!msg_ui,"screen stop cancels worker and UI state");lv_obj_del(function_page);function_page=NULL;CHECK(timer_count()==timers,"timer reclaimed");
 }
 printf("RESULT checks=%d failures=%d\n",checks,failures);return failures?1:0;
}
"""
src=pre+'\n'+(R/'ESP32C5/main/cym_messenger_ui.inc').read_text()+'\n'+post;(D/'host.c').write_text(src)
cmd=['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_USE_USER_DATA=1','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-I'+str(LV),'-I'+str(R/'ESP32C5/main'),str(D/'host.c'),str(R/'ESP32C5/main/cym_messenger_core.c'),*[str(p) for p in sorted((LV/'src').rglob('*.c'))],'-lm','-o',str(D/'host')]
x=subprocess.run(cmd,capture_output=True,text=True);(D/'compile.log').write_text(x.stdout+x.stderr);assert x.returncode==0,x.stderr[-4000:]
x=subprocess.run([str(D/'host')],env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'),capture_output=True,text=True);(D/'run.log').write_text(x.stdout+x.stderr)
(D/'provenance.json').write_text(json.dumps({'command':cmd,'source_sha256':hashlib.sha256(src.encode()).hexdigest(),'exit_code':x.returncode},indent=2));print(x.stdout+x.stderr);raise SystemExit(x.returncode)
