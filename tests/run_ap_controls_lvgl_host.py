#!/usr/bin/env python3
"""Actual Package B controls with installed LVGL 8.4. SDK/radio APIs are mocked.
Exercises widget geometry in running-view-like flex parents, not full screens or
physical panel/IR. All rotations and portrait/landscape parent compositions.
"""
from pathlib import Path
import os,re,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];S=(R/'ESP32C5/main/main.c').read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'ap-controls';D.mkdir(parents=True,exist_ok=True)
LV=R/'ESP32C5/managed_components/lvgl__lvgl';assert (LV/'src/core/lv_obj.c').exists()
a=S.index('static lv_obj_t *s_ap_ctrl_btn_lbl');b=S.index('// Screen-exit teardown for Captive Portal',a)
prod=S[a:b]
assert 'ap_suspend_control_cleanup();' in S[S.index('static void reset_function_page_children(void) {'):][:300]
for n in ['portal_stop','rogue_ap_stop']:
 m=re.search(r'static void '+n+r'\(void\)\s*\{',S);assert m
 assert 'radio_reset_to_idle' not in S[m.end():S.index('\n}',m.end())]
pre=r"""
#include "lvgl.h"
#include "esp_err.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void ap_suspend_control_cleanup(void);
static int state,queue_error,suspends,resumes;
static int wifi_attacks_ap_owner_state(void){return state;}
static int wifi_attacks_ap_suspend(void){suspends++;return queue_error;}
static int wifi_attacks_ap_resume(void){resumes++;return queue_error;}
static lv_font_t *font_btn_landscape,*font_btn_portrait;
#define UI_ACCENT_CYAN lv_color_hex(0x00bcd4)
#define UI_BG_SURFACE lv_color_hex(0x222222)
"""
post=r"""
static int checks,failures;
#define CHECK(x,n) do{checks++;if(!(x)){failures++;printf("FAIL %s\n",n);}}while(0)
static int timer_count(void){int n=0;lv_timer_t*t=NULL;while((t=lv_timer_get_next(t)))n++;return n;}
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*c){(void)a;(void)c;lv_disp_flush_ready(d);}
static void tick(void){lv_tick_inc(480);lv_timer_handler();}
int main(void){setbuf(stdout,NULL);lv_init();font_btn_landscape=font_btn_portrait=(lv_font_t*)LV_FONT_DEFAULT;
 static lv_color_t pixels[800*20];static lv_disp_draw_buf_t buf;lv_disp_draw_buf_init(&buf,pixels,NULL,800*20);
 lv_disp_drv_t dr;lv_disp_drv_init(&dr);dr.hor_res=800;dr.ver_res=480;dr.draw_buf=&buf;dr.flush_cb=flush;lv_disp_t*d=lv_disp_drv_register(&dr);
 const int sizes[][2]={{240,320},{320,480},{480,320},{800,480},{512,300}};
 for(int dim=0;dim<5;dim++)for(int rot=0;rot<4;rot++)for(int landscape=0;landscape<2;landscape++){
  dr.hor_res=sizes[dim][0];dr.ver_res=sizes[dim][1];lv_disp_drv_update(d,&dr);lv_disp_set_rotation(d,rot);
  int before=timer_count();lv_obj_t*p=lv_obj_create(lv_scr_act());lv_obj_set_size(p,lv_pct(100),lv_pct(85));
  lv_obj_set_flex_flow(p,LV_FLEX_FLOW_COLUMN);lv_obj_set_style_pad_all(p,5,0);
  lv_obj_t*log=lv_obj_create(p);lv_obj_set_size(log,lv_pct(100),landscape?lv_pct(80):120);
  state=4;lv_obj_t*btn=ap_add_suspend_control(p);lv_obj_update_layout(p);lv_obj_scroll_to_view(btn,LV_ANIM_OFF);lv_obj_update_layout(p);
  lv_area_t ba,pa;lv_obj_get_coords(btn,&ba);lv_obj_get_coords(p,&pa);
  CHECK(ba.x1>=pa.x1 && ba.x2<=pa.x2,"control fits width");
  CHECK(ba.y1>=pa.y1 && ba.y2<=pa.y2,"control scroll reachable");
  CHECK(strstr(lv_label_get_text(s_ap_ctrl_btn_lbl),"Starting")!=NULL,"pending truthful");
  suspends=resumes=0;lv_event_send(btn,LV_EVENT_CLICKED,NULL);CHECK(!suspends&&!resumes,"pending no duplicate");
  state=1;tick();CHECK(!strcmp(lv_label_get_text(s_ap_ctrl_btn_lbl),"Suspend AP"),"active caption");
  queue_error=ESP_ERR_TIMEOUT;lv_event_send(btn,LV_EVENT_CLICKED,NULL);tick();CHECK(strstr(lv_label_get_text(s_ap_ctrl_btn_lbl),"Busy")!=NULL,"queue refusal visible");
  queue_error=0;state=3;tick();lv_event_send(btn,LV_EVENT_CLICKED,NULL);CHECK(resumes==1,"held resume once");
  state=5;tick();CHECK(strstr(lv_label_get_text(s_ap_ctrl_btn_lbl),"uncertain")!=NULL,"uncertain never held");
  state=0;tick();CHECK(!strcmp(lv_label_get_text(s_ap_ctrl_btn_lbl),"AP idle"),"idle truthful");
  lv_obj_del(p);CHECK(!s_ap_ctrl_timer&&!s_ap_ctrl_btn_lbl,"DELETE clears timer identities");
  CHECK(timer_count()==before,"DELETE reclaims timer");tick();
 }
 printf("RESULT checks=%d failures=%d\n",checks,failures);return failures?86:0;
}
"""

(D/'sdkconfig.h').write_text('/* Host LVGL config is explicitly set by compile flags. */\n')
flags=['-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-I'+str(LV),'-I'+str(D),'-I'+str(Path(os.environ.get('IDF_PATH','/home/dev/esp/esp-idf'))/'components/esp_common/include')]
# Compile installed LVGL once and link identical objects to each semantic mutant.
objects=[]
for i,p in enumerate(sorted((LV/'src').rglob('*.c'))):
 obj=D/(str(i)+'.o');cmd=[os.environ.get('CC','cc'),*flags,'-c',str(p),'-o',str(obj)]
 b=subprocess.run(cmd,capture_output=True,text=True)
 if b.returncode:raise RuntimeError(b.stdout+b.stderr)
 objects.append(str(obj))
variants=[('production',prod,False),('timer-leak',prod.replace('lv_timer_del(s_ap_ctrl_timer);','/* mutant: leaked timer */'),True),('ignore-queue-refusal',prod.replace('s_ap_ctrl_rejected = rc != ESP_OK;','s_ap_ctrl_rejected = false;'),True)]
records=[]
for name,body,mutant in variants:
 assert not mutant or body!=prod
 d=D/name;d.mkdir(exist_ok=True);(d/'host.c').write_text(pre+body+post)
 cmd=[os.environ.get('CC','cc'),*flags,str(d/'host.c'),*objects,'-lm','-o',str(d/'host')]
 b=subprocess.run(cmd,capture_output=True,text=True);(d/'compile.log').write_text(b.stdout+b.stderr);assert not b.returncode,b.stderr
 b=subprocess.run([str(d/'host')],capture_output=True,text=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'));log=b.stdout+b.stderr;(d/'run.log').write_text(log)
 m=re.search(r'RESULT checks=(\d+) failures=(\d+)',log)
 ok=bool(m) and ((b.returncode==86 and int(m[2])>0 and 'Sanitizer' not in log) if mutant else b.returncode==0 and int(m[2])==0)
 records.append(dict(name=name,mutant=mutant,exit=b.returncode,ok=ok,checks=int(m[1])if m else None,failures=int(m[2])if m else None));print(records[-1],log[-500:])
(D/'results.json').write_text(json.dumps(dict(results=records,source_sha256=hashlib.sha256(S.encode()).hexdigest(),limits=__doc__),indent=2))
assert all(x['ok']for x in records)
