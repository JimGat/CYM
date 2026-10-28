#!/usr/bin/env python3
"""Production FSD mailbox/UI + installed LVGL. Only clock/SDK/physical sensor mocked."""
from pathlib import Path
import ast,os,subprocess,json
R=Path(__file__).resolve().parents[1];M=R/'ESP32C5/main';LV=R/'ESP32C5/managed_components/lvgl__lvgl'
D=Path(os.environ['CYM_TEST_OUT'])/'fsd-gesture';D.mkdir(parents=True,exist_ok=True)
legacy=ast.parse((R/'tests/run_fsd_host.py').read_text())
pre=next(ast.literal_eval(n.value) for n in legacy.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='pre' for t in n.targets))
for name in ['sdkconfig.h','esp_heap_caps.h']:(D/name).write_text('/* mock SDK */\n')
ui=Path(os.environ.get('FSD_UI_SOURCE',str(M/'fsd_ui.inc'))).read_text()
new_api='bool blocked, bool physical' in ui
(D/'fsd.h').write_text(Path(os.environ.get('FSD_UI_SOURCE',str(M/'fsd_ui.inc'))).with_name('fsd.h').read_text())
pre += '\nstatic bool g_home_layout_4cat,go_dark_active,screen_dimmed,ignore_touch_until_release,ui_locked,touch_pressed_flag;static int64_t g_radio_settle_until_ms;\n'
if not new_api:pre += '\nstatic unsigned fsd_page_epoch;\n'
# Do not substitute the cancellation/reset implementation: exercise production UI unchanged.
post=r"""
static bool blocked,physical;static int gesture_clicks,presses,reads;static lv_indev_t *pointer;
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){(void)a;(void)p;lv_disp_flush_ready(d);}
static void event(lv_event_t*e){if(lv_event_get_code(e)==LV_EVENT_CLICKED){gesture_clicks++;if(delete_event==1)fsd_page_epoch++;}if(lv_event_get_code(e)==LV_EVENT_PRESSED)presses++;}
static void read_touch(lv_indev_drv_t*d,lv_indev_data_t*v){(void)d;reads++;if(INJECT_CALL)return;v->point.x=40;v->point.y=40;v->state=physical?LV_INDEV_STATE_PRESSED:LV_INDEV_STATE_RELEASED;}
static void read_one(void){lv_indev_read_timer_cb(pointer->driver->read_timer);}
static cym_fsd_request_t *arm(void){cym_fsd_request_t*r=cym_fsd_submit(FSD_TAP,0,40,40,"");assert(r);cym_fsd_poll();assert(!r->done);return r;}
static void finish(cym_fsd_request_t*r){cym_fsd_poll();assert(r->done);cym_fsd_release(r);assert(!live&&!s_fsd_busy&&!s_fsd_inj_req);}
int main(int argc,char**argv){assert(argc==2);output=tmpfile();lv_init();static lv_color_t pixels[240*10];static lv_disp_draw_buf_t db;lv_disp_draw_buf_init(&db,pixels,NULL,2400);static lv_disp_drv_t dr;lv_disp_drv_init(&dr);dr.hor_res=240;dr.ver_res=320;dr.draw_buf=&db;dr.flush_cb=flush;lv_disp_t*display=lv_disp_drv_register(&dr);assert(display);
 static lv_indev_drv_t in;lv_indev_drv_init(&in);in.type=LV_INDEV_TYPE_POINTER;in.read_cb=read_touch;pointer=lv_indev_drv_register(&in);assert(pointer);
 lv_obj_t*b=lv_btn_create(lv_scr_act());lv_obj_set_pos(b,20,20);lv_obj_set_size(b,100,80);lv_obj_add_event_cb(b,event,LV_EVENT_ALL,NULL);lv_obj_update_layout(lv_scr_act());
 const char*s=argv[1];cym_fsd_request_t*r;
 if(!strcmp(s,"idle")){for(int i=0;i<1000;i++){physical=!(i%2);read_one();}assert(gesture_clicks==500);assert(!live);}
 else if(!strcmp(s,"cancel")){r=arm();read_one();assert(presses==1);r->cancelled=1;read_one();assert(gesture_clicks==0);assert(!lv_obj_has_state(b,LV_STATE_PRESSED));finish(r);assert(!pointer->proc.types.pointer.act_obj);}
 else if(!strcmp(s,"cancel-retry")){r=arm();read_one();__atomic_store_n(&r->cancelled,1,__ATOMIC_RELEASE);cym_fsd_poll();assert(r->done&&!r->status);cym_fsd_release(r);r=arm();for(int i=0;i<4;i++)read_one();finish(r);assert(gesture_clicks==1);}
 else if(!strcmp(s,"timeout")){r=arm();read_one();now=s_fsd_inj_deadline+1;cym_fsd_poll();read_one();assert(!gesture_clicks&&!pointer->proc.types.pointer.act_obj);assert(r->done&&!r->status);cym_fsd_release(r);}
 else if(!strcmp(s,"boundary")||!strcmp(s,"late-release")){r=arm();read_one();read_one();read_one();now=s_fsd_inj_deadline+(!strcmp(s,"late-release"));read_one();cym_fsd_poll();assert(r->done&&!r->status&&!gesture_clicks);cym_fsd_release(r);}
 else if(!strcmp(s,"rotation")){r=arm();read_one();lv_disp_set_rotation(display,LV_DISP_ROT_90);read_one();cym_fsd_poll();assert(!gesture_clicks&&r->done&&!r->status);cym_fsd_release(r);}
 else if(!strcmp(s,"page")){r=arm();read_one();fsd_page_epoch++;read_one();cym_fsd_poll();assert(!gesture_clicks&&r->done&&!r->status);cym_fsd_release(r);}
 else if(!strcmp(s,"physical")){r=arm();read_one();physical=true;read_one();cym_fsd_poll();assert(r->done&&!r->status&&!gesture_clicks);cym_fsd_release(r);read_one();physical=false;read_one();assert(!gesture_clicks);physical=true;read_one();physical=false;read_one();assert(gesture_clicks==1);}
 else if(!strcmp(s,"blocked")){r=arm();read_one();blocked=true;read_one();cym_fsd_poll();assert(r->done&&!r->status&&!gesture_clicks);cym_fsd_release(r);}
 else if(!strcmp(s,"completed-navigation")){delete_event=1;r=arm();for(int i=0;i<4;i++)read_one();assert(gesture_clicks==1&&fsd_page_epoch==1);finish(r);}
 else if(!strcmp(s,"caller-release")){r=arm();read_one();r->cancelled=1;cym_fsd_release(r);assert(live==1);cym_fsd_poll();assert(!live&&!s_fsd_busy);read_one();assert(!gesture_clicks);r=arm();for(int i=0;i<4;i++)read_one();finish(r);assert(gesture_clicks==1);}
 else if(!strcmp(s,"dropdown")){lv_obj_del(b);lv_obj_t*dd=lv_dropdown_create(lv_scr_act());lv_obj_set_pos(dd,10,10);lv_obj_set_width(dd,150);lv_dropdown_set_options(dd,"One\nTwo\nThree");lv_dropdown_open(dd);lv_obj_update_layout(lv_scr_act());lv_obj_t*list=lv_dropdown_get_list(dd);lv_area_t a;lv_obj_get_coords(list,&a);r=cym_fsd_submit(FSD_TAP,0,a.x1+25,a.y1+35,"");assert(r);cym_fsd_poll();for(int i=0;i<4;i++)read_one();finish(r);assert(!lv_dropdown_is_open(dd));}
 else if(!strcmp(s,"swipe")){lv_obj_del(b);lv_obj_t*list=lv_obj_create(lv_scr_act());lv_obj_set_pos(list,0,0);lv_obj_set_size(list,220,200);for(int i=0;i<20;i++){lv_obj_t*l=lv_label_create(list);lv_label_set_text(l,"Row");lv_obj_set_pos(l,0,i*30);}lv_obj_update_layout(lv_scr_act());r=cym_fsd_submit(FSD_SWIPE,-120,80,150,"");assert(r);cym_fsd_poll();for(int i=0;i<12;i++)read_one();finish(r);assert(lv_obj_get_scroll_y(list)>0);}
 else if(!strcmp(s,"keyboard")){lv_obj_del(b);lv_obj_t*ta=lv_textarea_create(lv_scr_act());lv_obj_set_size(ta,240,80);lv_obj_t*kb=lv_keyboard_create(lv_scr_act());lv_keyboard_set_textarea(kb,ta);lv_obj_update_layout(lv_scr_act());for(int i=0;i<50;i++){lv_btnmatrix_set_selected_btn(kb,1);lv_event_send(kb,LV_EVENT_VALUE_CHANGED,NULL);}assert(strlen(lv_textarea_get_text(ta))>0);assert(!s_fsd_inj_req&&!live);}
 else return 2;
 assert(!live&&!s_fsd_busy);fclose(output);printf("PASS %s real-LVGL production gesture/mailbox\n",s);return 0;}
"""
post=post.replace('INJECT_CALL','cym_fsd_touch_inject(v, blocked, physical)' if new_api else 'cym_fsd_touch_inject(v)')
(D/'host.c').write_text(pre+'\n'+ui+'\n'+post)
flags=['-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_USE_SNAPSHOT=1','-I'+str(LV),'-I'+str(D),'-I'+str(M)]
with (D/'compile.log').open('w') as f:subprocess.run(['cc',*flags,str(D/'host.c'),*[str(p) for p in (LV/'src').rglob('*.c')],'-lm','-o',str(D/'host')],stdout=f,stderr=subprocess.STDOUT,check=True)
env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0');results=[]
for case in ['idle','cancel','cancel-retry','timeout','boundary','late-release','rotation','page','physical','blocked','completed-navigation','caller-release','dropdown','swipe','keyboard']:
 p=subprocess.run([str(D/'host'),case],env=env,capture_output=True,text=True);results.append(dict(case=case,exit_code=p.returncode,output=p.stdout+p.stderr));print(case,p.returncode,p.stdout+p.stderr,flush=True)
(D/'results.json').write_text(json.dumps(results,indent=2));raise SystemExit(any(r['exit_code'] for r in results))
