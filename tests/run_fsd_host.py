#!/usr/bin/env python3
"""Production FSD UI/lifecycle/parser against pinned real LVGL; synthetic SDK only."""
from pathlib import Path
import os, subprocess, re
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'fsd-host';D.mkdir(parents=True,exist_ok=True)
LV=R/'ESP32C5/managed_components/lvgl__lvgl';M=R/'ESP32C5/main'
headers=['sdkconfig.h','esp_console.h','esp_heap_caps.h','esp_log.h','esp_timer.h','freertos/FreeRTOS.h','freertos/task.h','mbedtls/base64.h']
for name in headers:
 p=D/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('/* host SDK boundary */\n')
pre=r"""
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include "lvgl.h"
#define CONFIG_ESP_CONSOLE_NONE 0
#define CONFIG_BOARD_HAS_PSRAM 1
#if HOST_ROTATE
#define CONFIG_BOARD_NM_CYD_C5 1
#endif
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_8BIT 2
#define MALLOC_CAP_INTERNAL 4
#define MALLOC_CAP_DMA 8
#define ESP_OK 0
#define pdMS_TO_TICKS(n) (n)
#define ESP_LOGE(...) ((void)0)
typedef int esp_err_t;
typedef struct {const char *command,*help,*hint;int (*func)(int,char**);} esp_console_cmd_t;
static int allocation,fail_alloc,live,registered,reg_calls,fail_reg,del_calls,stops,home,clicks,events,delete_event;
static size_t requested;
static void (*alloc_hook)(size_t);
static void *heap_caps_calloc(size_t n,size_t s,int caps){assert(caps==3);if(alloc_hook)alloc_hook(n*s);requested=n*s;allocation++;if(fail_alloc==allocation)return NULL;void*p=calloc(n,s);assert(p);live++;return p;}
static void *heap_caps_malloc(size_t n,int caps){return heap_caps_calloc(1,n,caps);}
static void heap_caps_free(void*p){if(p){live--;free(p);}}
static size_t heap_caps_get_free_size(int c){return 10000+c;}
static size_t heap_caps_get_largest_free_block(int c){return 5000+c;}
static size_t heap_caps_get_minimum_free_size(int c){return 1000+c;}
static int esp_console_cmd_register(const esp_console_cmd_t*c){assert(c->func);reg_calls++;if(reg_calls==fail_reg)return 1;registered++;return 0;}
static int esp_console_cmd_deregister(const char*n){assert(n);registered--;del_calls++;return 0;}
static const char *esp_err_to_name(int n){(void)n;return "host failure";}
static FILE *output;
static FILE *cym_console_output(void){return output;}
static int64_t now;
static int64_t esp_timer_get_time(void){return now;}
static int mbedtls_base64_encode(unsigned char*d,size_t n,size_t*o,const unsigned char*s,size_t z){(void)d;(void)n;(void)o;(void)s;(void)z;return 1;}
static lv_obj_t *brightness_overlay;
static bool g_home_layout_4cat,go_dark_active,screen_dimmed,ignore_touch_until_release,ui_locked,touch_pressed_flag;
static int64_t g_radio_settle_until_ms;
static bool doom_ui_exclusive(void){return false;}
static int nav_stack_depth;static const char *nav_stack[12];static void(*g_screen_back_fn)(void);
static unsigned char screen_orientation;
static void parent(void){nav_stack_depth=1;nav_stack[0]="Settings";}
static void (*nav_show_lookup(const char*n))(void){return !strcmp(n,"Settings")?parent:NULL;}
static void nav_back_cb(lv_event_t*e){(void)e;home++;nav_stack_depth=0;}
static void run_screen_stop_fn(void){stops++;}
static void clock_cancel_radio_navigation(void){}
static void go_home(void){home++;}
static void apply_screen_orientation(unsigned char o){lv_disp_set_rotation(NULL,(lv_disp_rot_t)o);}
#include "fsd.h"
"""
ui=(M/'fsd_ui.inc').read_text()
console=(M/'fsd_console.c').read_text();console=re.sub(r'^#include "debug_console_stdio.h".*$','',console,flags=re.M)
post=r"""
static cym_fsd_request_t *timeout_during_event;
static cym_fsd_request_t *cancel_inflight;
static int cancelled_during_snapshot;
static void cancel_snapshot(size_t n){(void)n;alloc_hook=NULL;cancelled_during_snapshot++;__atomic_store_n(&cancel_inflight->cancelled,1,__ATOMIC_RELEASE);cym_fsd_release(cancel_inflight);cancel_inflight=NULL;}
static int disable_on_pressed;
static int exclusive_active;
static bool doom_ui_active(void){return exclusive_active;}
static int auto_poll=1;
static void vTaskDelay(unsigned n){now+=(int64_t)n*1000;if(auto_poll)cym_fsd_poll();}
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){(void)a;(void)p;lv_disp_flush_ready(d);}
static void event_cb(lv_event_t*e){int c=lv_event_get_code(e);if(timeout_during_event&&c==LV_EVENT_PRESSED){__atomic_store_n(&timeout_during_event->cancelled,1,__ATOMIC_RELEASE);cym_fsd_release(timeout_during_event);timeout_during_event=NULL;}if(c==LV_EVENT_PRESSED||c==LV_EVENT_RELEASED||c==LV_EVENT_SHORT_CLICKED||c==LV_EVENT_CLICKED){events++;if(disable_on_pressed&&c==LV_EVENT_PRESSED)lv_obj_add_state(lv_event_get_target(e),LV_STATE_DISABLED);if(c==LV_EVENT_CLICKED)clicks++;if(c==delete_event)lv_obj_del(lv_event_get_target(e));}}
static lv_indev_t *host_pointer;
static void read_touch(lv_indev_drv_t*d,lv_indev_data_t*v){(void)d;if(!cym_fsd_touch_inject(v,false,false))v->state=LV_INDEV_STATE_RELEASED;}
static cym_fsd_request_t *send(int op,int id,int a,int b,const char*t){cym_fsd_request_t*r=cym_fsd_submit(op,id,a,b,t);assert(r);cym_fsd_poll();for(int i=0;!r->done&&i<40;i++){lv_indev_read_timer_cb(host_pointer->driver->read_timer);cym_fsd_poll();}assert(r->done);return r;}
static void release(cym_fsd_request_t*r){cym_fsd_release(r);assert(live==0);}
static void command(int argc,char**argv,int expect){assert(fsd_command(argc,argv)==expect);assert(live<=1);}
int main(void){
 output=tmpfile();assert(output);lv_init();static lv_color_t pixels[800*10];static lv_disp_draw_buf_t db;lv_disp_draw_buf_init(&db,pixels,NULL,800*10);static lv_disp_drv_t drv;lv_disp_drv_init(&drv);drv.hor_res=240;drv.ver_res=320;drv.draw_buf=&db;drv.flush_cb=flush;lv_disp_t*d=lv_disp_drv_register(&drv);assert(d);static lv_indev_drv_t input;lv_indev_drv_init(&input);input.type=LV_INDEV_TYPE_POINTER;input.read_cb=read_touch;host_pointer=lv_indev_drv_register(&input);assert(host_pointer);
 for(int f=1;f<=14;f++){reg_calls=registered=del_calls=0;fail_reg=f;cym_fsd_register();assert(!registered&&del_calls==f-1&&!fsd_registered);}
 fail_reg=0;reg_calls=0;cym_fsd_register();assert(registered==14);cym_fsd_register();assert(registered==14);cym_fsd_unregister();assert(!registered);
 fail_alloc=allocation+1;assert(!cym_fsd_submit(FSD_WHERE,0,0,0,""));assert(!s_fsd_busy&&!live);fail_alloc=0;
 cym_fsd_request_t*r=cym_fsd_submit(FSD_TEXT,0,0,0,"old");assert(r);assert(!cym_fsd_submit(FSD_TEXT,0,0,0,"new"));__atomic_store_n(&r->cancelled,1,__ATOMIC_RELEASE);cym_fsd_release(r);assert(live==1);cym_fsd_poll();assert(live==0&&!s_fsd_busy);
 /* Defensive publication failure injection, without replacing existing request. */
 cym_fsd_request_t sentinel={0};s_fsd_pending=&sentinel;assert(!cym_fsd_submit(FSD_WHERE,0,0,0,""));assert(s_fsd_pending==&sentinel&&!live);s_fsd_pending=NULL;
 for(int k=0;k<1000;k++){r=send(FSD_WHERE,0,0,0,"");assert(r->status&&strstr(r->desc,"depth=0"));release(r);}
 int sizes[][2]={{240,320},{320,240},{320,480},{480,320},{512,300},{480,800},{800,480}};
 for(int size=0;size<7;size++)for(int layout=0;layout<2;layout++){
  drv.hor_res=sizes[size][0];drv.ver_res=sizes[size][1];lv_disp_drv_update(d,&drv);lv_obj_clean(lv_scr_act());lv_obj_clean(lv_layer_top());
  lv_obj_t *container=layout?lv_obj_create(lv_scr_act()):lv_scr_act();if(layout){lv_obj_set_pos(container,0,0);lv_obj_set_size(container,lv_pct(100),lv_pct(100));lv_obj_set_style_pad_all(container,0,0);lv_obj_set_style_border_width(container,0,0);lv_obj_clear_flag(container,LV_OBJ_FLAG_CLICKABLE);}
  lv_obj_t *btn=lv_btn_create(container);lv_obj_set_pos(btn,20,30);lv_obj_set_size(btn,100,50);lv_obj_t *lbl=lv_label_create(btn);lv_label_set_text(lbl,"Settings");lv_obj_add_event_cb(btn,event_cb,LV_EVENT_ALL,NULL);lv_obj_update_layout(lv_scr_act());
  r=send(FSD_TAPT,0,0,0,"Settings");assert(r->status);int id=r->id;release(r);
  lv_obj_add_state(btn,LV_STATE_DISABLED);r=send(FSD_TAPT,0,0,0,"Settings");assert(!r->status);release(r);r=send(FSD_TAPID,id,0,0,"");assert(!r->status);release(r);lv_obj_clear_state(btn,LV_STATE_DISABLED);
  lv_obj_add_flag(btn,LV_OBJ_FLAG_HIDDEN);r=send(FSD_TAP,0,25,35,"");assert(r->status); /* consumed, not proof of a hit */release(r);lv_obj_clear_flag(btn,LV_OBJ_FLAG_HIDDEN);
  lv_obj_t *modal=lv_obj_create(lv_layer_top());lv_obj_set_size(modal,150,150);r=send(FSD_TAPID,id,0,0,"");assert(!r->status);release(r);r=send(FSD_TAPT,0,0,0,"Settings");assert(!r->status);release(r);
  lv_obj_set_pos(modal,0,0);lv_obj_set_size(modal,200,240);lv_obj_set_style_radius(modal,0,0);lv_obj_set_style_border_width(modal,0,0);lv_obj_set_style_bg_color(modal,lv_color_hex(0xff0000),0);lv_obj_set_style_bg_opa(modal,LV_OPA_COVER,0);brightness_overlay=lv_obj_create(lv_layer_top());
  r=send(FSD_SHOT,0,0,0,"");assert(r->status&&(unsigned char)r->data[0]==255&&r->data[1]==0&&r->data[2]==0&&!lv_obj_has_flag(brightness_overlay,LV_OBJ_FLAG_HIDDEN));release(r);lv_obj_del(brightness_overlay);brightness_overlay=NULL;lv_obj_del(modal);
  r=send(FSD_TAP,0,799,799,"");assert(!r->status);release(r);
  r=send(FSD_TREE,0,0,0,"");assert(r->status&&strstr(r->data,"Settings")&&r->length);release(r);
  fail_alloc=allocation+2;r=send(FSD_TREE,0,0,0,"");assert(!r->status);release(r);fail_alloc=0;
  r=send(FSD_MOVE,id,25,35,"");assert(r->status);release(r);r=send(FSD_SIZE,id,80,40,"");assert(r->status);release(r);r=send(FSD_TEXT,id,0,0,"Preview");assert(r->status&&!strcmp(lv_label_get_text(lbl),"Preview"));release(r);
  r=send(FSD_SHOT,0,0,0,"");assert(r->status&&r->length==(size_t)sizes[size][0]*sizes[size][1]*3);release(r);
  fail_alloc=allocation+2;r=send(FSD_SHOT,0,0,0,"");assert(!r->status);release(r);fail_alloc=0;
 }
 r=cym_fsd_submit(FSD_SHOT,0,0,0,"");assert(r);cancel_inflight=r;alloc_hook=cancel_snapshot;cym_fsd_poll();assert(cancelled_during_snapshot==1&&live==0&&!s_fsd_busy);
 lv_obj_clean(lv_scr_act());lv_obj_clean(lv_layer_top());
 int codes[]={LV_EVENT_PRESSED,LV_EVENT_RELEASED,LV_EVENT_SHORT_CLICKED,LV_EVENT_CLICKED};
 for(int i=0;i<4;i++){lv_obj_t*b=lv_btn_create(lv_scr_act());lv_obj_add_event_cb(b,event_cb,LV_EVENT_ALL,NULL);delete_event=codes[i];int before=events;assert(fsd_click(b));assert(events-before==i+1);}delete_event=0;
 lv_obj_t *disabled=lv_btn_create(lv_scr_act());lv_obj_t *disabled_label=lv_label_create(disabled);lv_label_set_text(disabled_label,"Disable during press");lv_obj_add_event_cb(disabled,event_cb,LV_EVENT_ALL,NULL);disable_on_pressed=1;int before_disabled=events;
 r=send(FSD_TAPT,0,0,0,"Disable during press");assert(!r->status&&events==before_disabled+1);release(r);disable_on_pressed=0;lv_obj_del(disabled);
 lv_obj_t *late=lv_btn_create(lv_scr_act());lv_obj_t *late_label=lv_label_create(late);lv_label_set_text(late_label,"Late");lv_obj_add_event_cb(late,event_cb,LV_EVENT_ALL,NULL);
 timeout_during_event=cym_fsd_submit(FSD_TAPT,0,0,0,"Late");assert(timeout_during_event);cym_fsd_poll();assert(!timeout_during_event&&!live&&!s_fsd_busy);
 r=send(FSD_NAV,0,0,0,"Settings");assert(r->status&&stops);release(r);r=send(FSD_WHERE,0,0,0,"");assert(strstr(r->desc,"Settings"));release(r);

#if HOST_ROTATE
 exclusive_active=1;r=send(FSD_NAV,0,0,0,"Settings");assert(!r->status);release(r);r=send(FSD_ROTATE,0,1,0,"");assert(!r->status);release(r);exclusive_active=0;
#endif
 r=send(FSD_ROTATE,0,1,0,"");assert(r->status==HOST_ROTATE);release(r);
 lv_obj_clean(lv_scr_act());lv_obj_t *deep=lv_scr_act();for(int i=0;i<66;i++)deep=lv_obj_create(deep);r=send(FSD_TREE,0,0,0,"");assert(!r->status);release(r);lv_obj_clean(lv_scr_act());
 char*bad[][4]={{"tap","abc","0"},{"tap","1junk","0"},{"tap","99999999999999999","0"},{"size","1","0","4"},{"rotate","abc"},{"tapid","-1"},{"move","1","0","32768"}};
 int counts[]={3,3,3,4,2,2,4};for(int i=0;i<7;i++)command(counts[i],bad[i],1);
 char huge[128];memset(huge,'x',127);huge[127]=0;char*longtext[]={"tapt",huge};command(2,longtext,1);
 char*miss[]={"tapt","not present"};command(2,miss,1);char*where[]={"where"};command(1,where,0);
 auto_poll=0;command(1,where,1);assert(live==1);cym_fsd_poll();assert(live==0);auto_poll=1;command(1,where,0);
 fclose(output);printf("PASS FSD real LVGL: geometries=7 synthetic_container_layouts=2 timeout/retry/queue/OOM/deletion/overlay/parser/registration; request_size=%zu mailbox_static=%zu\n",sizeof(cym_fsd_request_t),sizeof(s_fsd_pending)+sizeof(s_fsd_busy));return 0;
}
"""
# vTaskDelay is SDK boundary but production calls it before its body.
source=pre+'\nstatic void vTaskDelay(unsigned n);\nstatic bool doom_ui_active(void);\n'+ui+'\n'+console+'\n'+post
(D/'host.c').write_text(source)
flags=['-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_USE_SNAPSHOT=1','-I'+str(LV),'-I'+str(D),'-I'+str(M)]
for rotate in [0,1]:
 exe=D/f'host-{rotate}'
 with (D/f'compile-{rotate}.log').open('w') as out:
  subprocess.run(['cc',*flags,f'-DHOST_ROTATE={rotate}',*(['-DCONFIG_BOARD_WS_C5_28=1'] if rotate else []),str(D/'host.c'),*[str(p) for p in (LV/'src').rglob('*.c')],'-lm','-o',str(exe)],stdout=out,stderr=subprocess.STDOUT,check=True)
 env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=0' # LVGL process-global display/theme intentionally survives main
 subprocess.run([str(exe)],env=env,check=True)
