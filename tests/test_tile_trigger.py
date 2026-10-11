from pathlib import Path
import unittest, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
class TileTrigger(unittest.TestCase):
 def test_production_click_and_navigation(self):
  ui=(ROOT/'ESP32C5/components/cym_doom/doom_ui.c').read_text()
  tail=ui[ui.index('static void navigation_due('):len(ui)]
  cancel=ui[ui.index('static void cancel_navigation('):ui.index('static void cancel_navigation(')+ui[ui.index('static void cancel_navigation('):].index('\n')]
  stub=r"""#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stddef.h>
#include "doom_contracts.h"
typedef struct {int unused;} lv_timer_t;
static lv_timer_t timer_obj,*navigation_timer;
static doom_trigger unlock;
static void *overlay;
static bool (*idle_gate)(void),(*sd_ready_gate)(void);
static void (*return_home)(void),(*normal_navigation)(void);
static int dialogs,navigations,deletes;
static bool fail_timer;
static int64_t time_us;
static int64_t esp_timer_get_time(void){return time_us;}
static void lv_timer_del(lv_timer_t*t){assert(t==&timer_obj);deletes++;}
static lv_timer_t*lv_timer_create(void (*cb)(lv_timer_t*),int ms,void*p){(void)cb;(void)p;assert(ms==800);return fail_timer?NULL:&timer_obj;}
static void selector_dialog(void){dialogs++;}
static void navigate(void){navigations++;}
static bool no(void){return false;}
"""
  main=r"""
int main(void){
 doom_ui_configure(no,NULL,no,navigate);
 for(int i=0;i<4;i++){time_us=i*500000;doom_ui_tile_click();assert(dialogs==0);}
 time_us=2000000;doom_ui_tile_click();assert(dialogs==1);assert(!navigation_timer);assert(navigations==0);
 doom_ui_configure(no,NULL,no,navigate);time_us=3000000;doom_ui_tile_click();assert(navigation_timer);navigation_due(navigation_timer);assert(navigations==1);assert(unlock.count==0);
 doom_ui_tile_click();cancel_navigation();assert(!navigation_timer&&unlock.count==0);
 overlay=&timer_obj;doom_ui_tile_click();assert(unlock.count==0);overlay=NULL;
 fail_timer=true;doom_ui_tile_click();assert(navigations==2);assert(!navigation_timer&&unlock.count==0);fail_timer=false;
 doom_ui_configure(no,NULL,no,navigate);time_us=0;doom_ui_tile_click();time_us=7000000;doom_ui_tile_click();assert(dialogs==1&&unlock.count==1);cancel_navigation();
 return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   c=Path(d)/'tile.c';exe=Path(d)/'tile';c.write_text(stub+cancel+'\n'+tail+main)
   subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(ROOT/'ESP32C5/components/cym_doom/include'),str(c),str(ROOT/'ESP32C5/components/cym_doom/doom_contracts.c'),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
