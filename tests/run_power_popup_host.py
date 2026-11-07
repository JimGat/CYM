#!/usr/bin/env python3
# Real installed LVGL, production popup/callback extraction; no SDK or RF.
import os,re,subprocess,json,hashlib,ast
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=Path(os.environ.get("CYM_POWER_SOURCE",R));s=(S/"ESP32C5/main/main.c").read_text()
O=Path(os.environ["CYM_TEST_OUT"])/"power-popup";O.mkdir(parents=True,exist_ok=False)
LV=R/"ESP32C5/managed_components/lvgl__lvgl"
def fn(sig):
 m=re.search(re.escape(sig)+r"[^;{}]*\)\s*\{",s);assert m,sig
 a=m.start();b=m.end()-1;i=b+1;d=1
 while d:d+=(s[i]=="{")-(s[i]=="}");i+=1
 return s[a:i]
pre=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include "lvgl.h"
#define COLOR_MATERIAL_RED lv_color_hex(0xb00020)
#define ESP_OK 0
#define PWR_SRC_ERROR 3
#define PWR_LVL_MAX 2
#define PWR_LVL_NORMAL 1
static bool g_max_power_mode,dark;
static uint8_t g_pwr_lvl=1;
#define PWR_RADIO_OFF 0
#define PWR_RADIO_FAILED 2
static uint8_t ble_power_applied_level(void){return 0;}
static uint8_t ble_power_status(void){return 0;}
static uint8_t wifi_power_status(void){return 0;}
static int s_pwr_load_source;
typedef struct{uint8_t level;uint32_t req_seq,done_seq;bool busy;bool saved_rc,submit_rc;}pwr_job_t;
static pwr_job_t job;
static pwr_job_t pwr_snapshot(void){return job;}
static uint8_t wifi_power_applied_level(void){return 0;}
static void pwr_request(uint8_t l){job.req_seq++;g_pwr_lvl=l;g_max_power_mode=l==2;}
static lv_color_t ui_bg_color(void){return dark?lv_color_hex(0x111111):lv_color_white();}
static lv_color_t ui_panel_color(void){return dark?lv_color_hex(0x222222):lv_color_hex(0xf0f0f0);}
static lv_color_t ui_text_color(void){return dark?lv_color_white():lv_color_black();}
static lv_color_t ui_muted_color(void){return dark?lv_color_hex(0xbbbbbb):lv_color_hex(0x444444);}
static lv_obj_t *powermode_popup,*powermode_normal_btn,*powermode_max_btn,*powermode_status_lbl;
static lv_timer_t *powermode_timer;
static void powermode_timer_cb(lv_timer_t*);
"""
functions=["powermode_start_poll","powermode_refresh_buttons","powermode_timer_cb","powermode_delete_cb","powermode_close_cb","powermode_normal_cb","powermode_max_cb","show_power_mode_popup"]
body="\n".join(fn("static void "+n+"(") for n in functions)
post=r"""
static int checks,failures;
#define CHECK(v,n) do{checks++;if(!(v)){failures++;printf("FAIL %s\n",n);}}while(0)
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){(void)a;(void)p;lv_disp_flush_ready(d);}
static void render(void){lv_obj_update_layout(lv_scr_act());lv_refr_now(NULL);}
static bool contains(lv_obj_t*p,lv_obj_t*c){lv_area_t a,b;lv_obj_get_coords(p,&a);lv_obj_get_coords(c,&b);return b.x1>=a.x1&&b.x2<=a.x2&&b.y1>=a.y1&&b.y2<=a.y2;}
int main(void){
 lv_init();static lv_color_t buf[512*32];static lv_disp_draw_buf_t db;lv_disp_draw_buf_init(&db,buf,NULL,512*32);static lv_disp_drv_t dr;lv_disp_drv_init(&dr);dr.draw_buf=&db;dr.flush_cb=flush;dr.hor_res=240;dr.ver_res=320;lv_disp_t*d=lv_disp_drv_register(&dr);
 int sizes[][2]={{240,320},{320,240},{320,480},{480,320},{512,300}};
 for(int menu=0;menu<2;menu++)for(int theme=0;theme<2;theme++)for(int dim=0;dim<5;dim++)for(int rot=0;rot<4;rot++){
  dark=theme;dr.hor_res=sizes[dim][0];dr.ver_res=sizes[dim][1];lv_disp_drv_update(d,&dr);lv_disp_set_rotation(d,rot);show_power_mode_popup();render();
  lv_obj_t*dialog=lv_obj_get_child(powermode_popup,0);CHECK(contains(lv_scr_act(),dialog),"dialog screen bounds");
  lv_obj_t*first=lv_obj_get_child(dialog,0);CHECK(contains(dialog,first),"first label visible at scroll zero");
  for(int status=0;status<6;status++){
   job.req_seq=job.done_seq=1;job.submit_rc=job.saved_rc=0;job.busy=false;s_pwr_load_source=0;
   if(status==0)job.req_seq=0;if(status==1)job.busy=true;if(status==2)job.saved_rc=-1;if(status==3)job.submit_rc=-1;if(status==4){job.req_seq=0;s_pwr_load_source=3;}
   powermode_timer_cb(powermode_timer);render();
   for(unsigned i=0;i<lv_obj_get_child_cnt(dialog);i++){
    lv_obj_t*c=lv_obj_get_child(dialog,i);lv_obj_scroll_to_view_recursive(c,LV_ANIM_OFF);render();CHECK(contains(dialog,c),"each label/warning/status/button reachable");
   }
   lv_obj_scroll_to_y(dialog,0,LV_ANIM_OFF);render();CHECK(contains(dialog,first),"first remains reachable after status update");
  }
  lv_timer_t*old=powermode_timer;lv_obj_t*popup=powermode_popup;
  lv_event_send(powermode_max_btn,LV_EVENT_CLICKED,NULL);CHECK(g_pwr_lvl==2,"Max callback route");
  lv_event_send(powermode_normal_btn,LV_EVENT_CLICKED,NULL);CHECK(g_pwr_lvl==1,"Normal callback route");
  lv_obj_del(popup);CHECK(!powermode_popup&&!powermode_timer&&!powermode_status_lbl,"delete clears owned UI and timer");
  show_power_mode_popup();render();job.done_seq=job.req_seq;job.saved_rc=0;powermode_timer_cb(powermode_timer);CHECK(powermode_popup!=NULL,"completion after reopen");
  (void)old;powermode_close_cb(NULL);CHECK(!powermode_popup&&!powermode_timer,"Close cleans timer");
 }
 printf("RESULT checks=%d failures=%d cases=160\n",checks,failures);return failures?1:0;
}
"""
(O/"host.c").write_text(pre+body+post)
flags=["-std=gnu11","-O2","-DLV_CONF_SKIP=1","-DLV_FONT_MONTSERRAT_12=1","-DLV_FONT_MONTSERRAT_16=1","-I"+str(LV)]
cmd=["cc",*flags,str(O/"host.c"),*[str(p)for p in(LV/"src").rglob("*.c")],"-lm","-o",str(O/"host")]
with(O/"compile.log").open("w")as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
if rc:print((O/"compile.log").read_text()[-5000:]);raise SystemExit(rc)
r=subprocess.run([str(O/"host")],capture_output=True,text=True);(O/"run.log").write_text(r.stdout+r.stderr)
(O/"results.json").write_text(json.dumps(dict(command=cmd,exit=r.returncode,source_sha256=hashlib.sha256(s.encode()).hexdigest(),limitations=["menu endpoint setup modeled; popup production callbacks real", "host LVGL reachability, not physical readability or touch", "worker results mocked here, tested separately"]),indent=2));print(r.stdout+r.stderr);raise SystemExit(r.returncode)
