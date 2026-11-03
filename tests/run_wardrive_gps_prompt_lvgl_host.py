#!/usr/bin/env python3
"""Production GPS prompt callbacks/navigation with installed LVGL 8.4 (SDK-native).
Post-admission radio/UI construction is an instrumented endpoint, not hardware.
"""
from pathlib import Path
import os,re,subprocess,json,hashlib,sys
R=Path(__file__).resolve().parents[1]
D=Path(os.environ['CYM_TEST_OUT'])/'wardrive-gps-lvgl';D.mkdir(parents=True,exist_ok=True)
LV=R/'ESP32C5/managed_components/lvgl__lvgl'
assert (LV/'src/core/lv_obj.c').is_file(),'installed LVGL prerequisite missing'
if '--verify-mutations' in sys.argv:
 records=[]
 for name,mutant in [('accepted',False),('home-no-cleanup',True)]:
  out=D/name;env=dict(os.environ,CYM_TEST_OUT=str(out))
  cmd=[sys.executable,'-B',__file__]+(['--mutate-home'] if mutant else [])
  x=subprocess.run(cmd,env=env,capture_output=True,text=True)
  log=x.stdout+x.stderr;(D/(name+'.log')).write_text(log)
  match=re.search(r'RESULT checks=(\d+) failures=(\d+)',log)
  ok=bool(match) and ((x.returncode==1 and int(match[2])>0 and 'FAIL navigation dismisses cached prompt' in log and 'Sanitizer' not in log) if mutant else (x.returncode==0 and int(match[2])==0))
  records.append(dict(name=name,command=cmd,exit_code=x.returncode,semantic=ok,checks=int(match[1]) if match else None,failures=int(match[2]) if match else None))
  (D/'verification.json').write_text(json.dumps(records,indent=2))
  print(name,records[-1],flush=True)
  if not ok:sys.exit(1)
 sys.exit(0)
S=(R/'ESP32C5/main/main.c').read_text()
def fn(n):
 m=re.search(r'static void '+n+r'\s*\([^;]*?\)\s*\{',S);assert m,n
 i=m.end();d=1
 while d:d+=(S[i]=='{')-(S[i]=='}');i+=1
 return S[m.start():i]
a=S.index('static lv_timer_t *wd_gps_wait_timer = NULL;')
b=S.index('static void wardrive_start_btn_cb(lv_event_t *e);',a)
block=S[a:b]
start=fn('wardrive_start_btn_cb');cut=start.index('    // GPS is fresh or user has made choice;')
admission=start[:cut]+'    starts++;\n}\n'
pre=r"""
#include "lvgl.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#define ESP_LOGI(...) ((void)0)
#define UI_ACCENT_CYAN lv_color_hex(0x00bcd4)
#define COLOR_MATERIAL_ORANGE lv_color_hex(0xffa000)
typedef struct {int valid,satellites;float latitude,longitude,accuracy;}gps_data_t;
static gps_data_t current_gps,cached;static int starts,menus,checks,failures;
static volatile int wd_gps_prompt_state;
static bool nav_to_menu_flag,defer_clock;
static void(*s_clock_deferred_radio_fn)(void),(*nav_deferred_show_fn)(void),(*g_screen_back_fn)(void);
static int nav_stack_depth;static const char*nav_stack[4];
static const gps_data_t*gps_best(void){return cached.latitude?&cached:NULL;}
static void show_wardrive_menu_screen(void){menus++;}
static void show_menu(void);
static void(*nav_show_lookup(const char*n))(void){(void)n;return show_wardrive_menu_screen;}
static bool clock_defer_radio_navigation(void(*fn)(void)){if(!defer_clock)return false;s_clock_deferred_radio_fn=fn;return true;}
static void clock_cancel_radio_navigation(void);
static void wardrive_start_btn_cb(lv_event_t*);
static void clock_deferred_wardrive(void);
"""
post=r"""
#define CHECK(v,n) do{checks++;if(!(v)){failures++;printf("FAIL %s\n",n);}}while(0)
static void tick(void){lv_tick_inc(120);lv_timer_handler();}
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*c){(void)a;(void)c;lv_disp_flush_ready(d);}
static void choose(int i){lv_event_send(lv_obj_get_child(s_wd_gps_prompt_modal,i),LV_EVENT_CLICKED,NULL);}
static void reset(void){wd_gps_cleanup_prompts();clock_cancel_radio_navigation();defer_clock=false;nav_to_menu_flag=false;nav_deferred_show_fn=NULL;starts=0;current_gps=(gps_data_t){0};cached=(gps_data_t){.latitude=1,.longitude=2};tick();}
int main(void){setbuf(stdout,NULL);lv_init();static lv_color_t pixels[320*20];static lv_disp_draw_buf_t buf;lv_disp_draw_buf_init(&buf,pixels,NULL,320*20);lv_disp_drv_t dr;lv_disp_drv_init(&dr);dr.hor_res=240;dr.ver_res=320;dr.draw_buf=&buf;dr.flush_cb=flush;lv_disp_t*d=lv_disp_drv_register(&dr);
reset();cached.latitude=0;wardrive_start_btn_cb(NULL);CHECK(s_wd_gps_nodata_mbox!=NULL,"no-data created");wd_gps_cleanup_prompts();CHECK(lv_obj_get_child_cnt(lv_layer_top())==0,"no-data backdrop reclaimed");
reset();cached.latitude=0;wardrive_start_btn_cb(NULL);lv_event_send(lv_msgbox_get_close_btn(s_wd_gps_nodata_mbox),LV_EVENT_CLICKED,NULL);CHECK(s_wd_gps_nodata_mbox==NULL,"X DELETE clears identity");
/* Stop RED before a known stale-pointer cleanup; assertions, not crashes, are evidence. */
if(failures){printf("RESULT checks=%d failures=%d\n",checks,failures);return 1;}
lv_obj_t*unrelated=lv_obj_create(lv_scr_act());wd_gps_cleanup_prompts();CHECK(lv_obj_is_valid(unrelated),"unrelated allocation survives");lv_obj_del(unrelated);
/* Repeated pending OK -> X, allocation, cleanup: cancel only the queued owner. */
for(int rep=0;rep<32;rep++){
 reset();cached.latitude=0;wardrive_start_btn_cb(NULL);lv_obj_t*m=s_wd_gps_nodata_mbox;
 lv_event_send(lv_msgbox_get_btns(m),LV_EVENT_VALUE_CHANGED,NULL);
 lv_event_send(lv_msgbox_get_btns(m),LV_EVENT_VALUE_CHANGED,NULL);
 lv_event_send(lv_msgbox_get_close_btn(m),LV_EVENT_CLICKED,NULL);
 CHECK(!s_wd_gps_nodata_mbox,"pending OK then X clears owner");
 lv_obj_t*other=lv_obj_create(lv_layer_top());wd_gps_cleanup_prompts();tick();
 CHECK(lv_obj_is_valid(other)&&lv_obj_get_child_cnt(lv_layer_top())==1,"queued close never deletes unrelated overlay");lv_obj_del(other);
 reset();wardrive_start_btn_cb(NULL);choose(4);go_home();current_gps.satellites=8;tick();CHECK(starts==0&&!wd_gps_wait_modal&&!wd_gps_wait_timer,"direct Home cancels wait");
}
for(int layout=0;layout<2;layout++)for(int rot=0;rot<4;rot++){
lv_disp_set_rotation(d,rot);
for(int back=0;back<2;back++){
 reset();nav_stack_depth=back?2:0;nav_stack[0]="Wardrive";wardrive_start_btn_cb(NULL);CHECK(wd_gps_prompt_state==1,"cached prompt");if(back)nav_back_cb(NULL);else home_btn_event_cb(NULL);CHECK(!s_wd_gps_prompt_modal&&wd_gps_prompt_state==0,"navigation dismisses cached prompt");tick();CHECK(starts==0,"departure no start");
 reset();wardrive_start_btn_cb(NULL);choose(4);CHECK(wd_gps_wait_timer&&wd_gps_wait_modal,"Wait creates timer");tick();CHECK(starts==0,"no lock waits");if(back)nav_back_cb(NULL);else home_btn_event_cb(NULL);current_gps.satellites=5;tick();CHECK(starts==0&&!wd_gps_wait_timer&&!wd_gps_wait_modal,"departed timer cannot start");
 for(int before=0;before<2;before++){
 reset();cached.latitude=0;wardrive_start_btn_cb(NULL);lv_obj_t*m=s_wd_gps_nodata_mbox;lv_event_send(lv_msgbox_get_btns(m),LV_EVENT_VALUE_CHANGED,NULL);if(before)tick();if(back)nav_back_cb(NULL);else home_btn_event_cb(NULL);tick();CHECK(!s_wd_gps_nodata_mbox&&lv_obj_get_child_cnt(lv_layer_top())==0,"OK async/navigation releases backdrop");wd_gps_cleanup_prompts();tick();CHECK(starts==0,"repeat no start");
 }
 reset();wardrive_start_btn_cb(NULL);choose(3);CHECK(starts==1&&wd_gps_prompt_state==2,"Use Now admitted once");tick();CHECK(starts==1,"Use Now no repeat");
 reset();current_gps.valid=1;wardrive_start_btn_cb(NULL);CHECK(starts==1&&!s_wd_gps_prompt_modal,"fresh admission");
 reset();wardrive_start_btn_cb(NULL);choose(4);current_gps.satellites=4;tick();CHECK(starts==1&&!wd_gps_wait_timer&&!wd_gps_wait_modal,"wait lock resolves once");tick();CHECK(starts==1,"resolved no repeat");
 reset();wardrive_start_btn_cb(NULL);choose(4);lv_event_send(lv_obj_get_child(wd_gps_wait_modal,2),LV_EVENT_CLICKED,NULL);current_gps.satellites=7;tick();CHECK(starts==0&&wd_gps_prompt_state==0&&!wd_gps_wait_timer,"Cancel no re-prompt/start");
 reset();wardrive_start_btn_cb(NULL);defer_clock=true;choose(3);CHECK(s_clock_deferred_radio_fn!=NULL&&starts==0,"clock deferred decision");if(back)nav_back_cb(NULL);else home_btn_event_cb(NULL);CHECK(!s_clock_deferred_radio_fn,"navigation cancels deferred start");defer_clock=false;tick();CHECK(starts==0,"no deferred restart");
}
}
reset();printf("RESULT checks=%d failures=%d\n",checks,failures);return failures?1:0;}
"""
# Preserve the actual direct-Home entry prefix; radio/menu rendering beyond it is
# an explicit endpoint. FSD rejects overlays; direct/IR Home goes through go_home.
sm=S.index('void show_menu(void)\n{');smstart=S.index('{',sm)+1
smend=S.index('    // Run the current screen',smstart)
home_prefix=S[smstart:smend]
assert 'wd_gps_cleanup_prompts();' in home_prefix
fsd=(R/'ESP32C5/main/fsd_ui.inc').read_text()
assert 'overlay blocks navigation' in fsd and 'nav_back_cb(NULL)' in fsd
assert 'wd_gps_cleanup_prompts();' not in fn('wardrive_start_btn_cb')
direct_home='static void show_menu(void) {'+home_prefix+'menus++;}\n'+fn('go_home')
functions=['clock_cancel_radio_navigation' ,'nav_back_cb','home_btn_event_cb','clock_deferred_wardrive']
source=pre+block+'\n'.join(fn(n) for n in functions)+direct_home+admission+post
needle='    wd_gps_cleanup_prompts();  // dismiss a pending Wardrive GPS popup so it can\'t orphan over Home'
if '--mutate-home' in sys.argv:
 assert needle in source,'mutation drift'
 source=source.replace(needle,'    /* mutation: Home omits cleanup */',1)
(D/'host.c').write_text(source)
flags=['-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-I'+str(LV)]
cmd=[os.environ.get('CC','cc'),*flags,str(D/'host.c'),*[str(p)for p in sorted((LV/'src').rglob('*.c'))],'-lm','-o',str(D/'host')]
with (D/'compile.log').open('w')as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
assert rc==0,(D/'compile.log').read_text()[-6000:]
x=subprocess.run([str(D/'host')],capture_output=True,text=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'));log=x.stdout+x.stderr;(D/'run.log').write_text(log)
(D/'provenance.json').write_text(json.dumps(dict(command=cmd,source_sha256=hashlib.sha256(S.encode()).hexdigest(),functions=functions,direct_home_prefix_sha256=hashlib.sha256(home_prefix.encode()).hexdigest(),block_sha256=hashlib.sha256(block.encode()).hexdigest(),admission_prefix_sha256=hashlib.sha256(start[:cut].encode()).hexdigest(),lvgl_sha256={str(p.relative_to(LV)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted((LV/'src').rglob('*'))if p.is_file()},exit_code=x.returncode,limitations=['post-admission UI/radio mocked','layout loop repeats shared callbacks; full geometry separately covered by display_layout','no physical heap/timing evidence']),indent=2))
print(log);sys.exit(x.returncode)
