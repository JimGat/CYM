#!/usr/bin/env python3
"""Execute extracted production stop/finalize dispatch; synthetic UI lock/RF boundary."""
from pathlib import Path
import os,re,subprocess,hashlib,json
R=Path(__file__).resolve().parents[1];M=R/'ESP32C5/main/main.c'
D=Path(os.environ['CYM_TEST_OUT'])/'wifi-sas';D.mkdir(parents=True,exist_ok=True)
s=M.read_text()
def function(name):
 m=re.search(r'static void '+name+r'\([^;]*?\)\s*\{',s);assert m,name
 i=m.end();depth=1
 while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
a=s.index('                bool wifi_sas_owns_completion =')
b=s.index('                show_touch_dot = true;',a)
dispatch=s[a:b]+' rebuilds++; }\n'
pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "wifi_sas_policy.h"
#define MAX_SCAN_RESULTS 16
typedef int wifi_ap_record_t;
static bool wifi_sas_auto_scanning,wifi_sas_ui_active;
static bool scan_done_ui_flag;
static void *function_page;
static int wifi_sas_page,wifi_sas_scan_pass,wifi_sas_stable_passes;
static uint32_t wifi_sas_scan_start_ms,wifi_sas_expected_scan,scan_done_ui_generation;
static unsigned wifi_sas_accum_count,g_shared_scan_count;
static int wifi_sas_accum[16],g_shared_scan_results[16];
static void *wifi_sas_nav_bar,*wifi_sas_nav_prev,*wifi_sas_nav_lbl,*wifi_sas_nav_next,*scan_status_label;
static int rebuilds,starts,start_rc;static bool locked;
static int64_t esp_timer_get_time(void){return 0;}
static bool wifi_sas_merge_pass(void){return false;}
static bool lv_obj_is_valid(void*p){return p!=NULL;}
static void lv_label_set_text(void*p,const char*s){(void)p;(void)s;}
static int wifi_scanner_start_scan(void){starts++;return start_rc;}
static unsigned wifi_scanner_scan_generation(void){return 7;}
#define ESP_OK 0
static void (*g_screen_stop_fn)(void);
static void run_screen_stop_fn(void);
static void reset_function_page_children(void){run_screen_stop_fn();scan_status_label=NULL;}
static void lv_obj_del(void*p){(void)p;}
static void show_function_page(const char*n){(void)n;reset_function_page_children();function_page=(void*)1;}
#define TAG "TEST"
#define ESP_LOGW(...) ((void)0)
typedef int esp_err_t;

"""
post=r"""
int main(void){locked=true;
 for(int menu=0;menu<2;menu++){
  wifi_sas_ui_active=true;wifi_sas_expected_scan=scan_done_ui_generation=7;
  wifi_sas_auto_scanning=false;dispatch();assert(rebuilds==menu+1);assert(g_screen_stop_fn==wifi_sas_screen_stop&&wifi_sas_ui_active&&wifi_sas_expected_scan==0);
  wifi_sas_nav_bar=wifi_sas_nav_prev=wifi_sas_nav_lbl=wifi_sas_nav_next=(void*)1;
  wifi_sas_auto_scanning=true;wifi_sas_page=2;g_screen_stop_fn=wifi_sas_screen_stop;run_screen_stop_fn();
  assert(!g_screen_stop_fn&&!wifi_sas_auto_scanning);
  int before=rebuilds;dispatch();assert(rebuilds==before && "late scan completion must not rebuild Home/Back/target screen");
  assert(!wifi_sas_nav_bar&&!wifi_sas_nav_prev&&!wifi_sas_nav_lbl&&!wifi_sas_nav_next&&!wifi_sas_page);
  wifi_sas_ui_active=true;wifi_sas_expected_scan=8;scan_done_ui_generation=7;
  dispatch();assert(rebuilds==before && "stale generation must not finalize reentered screen");
  wifi_sas_ui_active=false;
 }
 /* Exercise the exact entry suffix, including failed initial/reentry start. */
 int before=rebuilds;start_rc=9;wifi_sas_ui_active=true;wifi_sas_auto_scanning=true;entry_start();
 assert(!wifi_sas_ui_active&&!wifi_sas_auto_scanning&&!wifi_sas_expected_scan&&!scan_done_ui_flag);
 dispatch();assert(rebuilds==before);
 start_rc=0;wifi_sas_ui_active=true;entry_start();assert(wifi_sas_expected_scan==7);
 wifi_sas_auto_scanning=true;wifi_sas_stable_passes=0;wifi_sas_scan_pass=0;scan_done_ui_generation=7;
 dispatch();assert(rebuilds==before&&wifi_sas_auto_scanning&&wifi_sas_expected_scan==7&&wifi_sas_scan_pass==1);
 start_rc=9;wifi_sas_stable_passes=0;dispatch();assert(rebuilds==before+1&&wifi_sas_ui_active&&g_screen_stop_fn==wifi_sas_screen_stop);
 run_screen_stop_fn();assert(!wifi_sas_ui_active);
 puts("PASS extracted Wi-Fi stop/finalize: normal, Back/Home/target detach, late event, immediate-reentry generation");return 0;
}
"""
entry_text=function('show_wifi_scan_attack_screen');entry_text=entry_text[entry_text.index('    // Consume no previous completion,'):];entry='\nstatic void entry_start(void){'+entry_text+'\n'
(D/'host.c').write_text(pre+function('wifi_sas_screen_stop')+function('run_screen_stop_fn')+'\nstatic void dispatch(void){assert(locked);\n'+dispatch+'}\n'+entry+post)
(D/'provenance.json').write_text(json.dumps({'source_sha256':hashlib.sha256(M.read_bytes()).hexdigest(),'extracted':['wifi_sas_screen_stop','run_screen_stop_fn','adaptive/finalize dispatch prefix']},indent=2))
(D/'sdkconfig.h').write_text('')
subprocess.run(['cc','-I'+str(D),'-I'+str(R/'ESP32C5/main'),'-std=gnu11','-g','-O1','-fsanitize=address,undefined',str(D/'host.c'),'-o',str(D/'host')],check=True)
subprocess.run([str(D/'host')],check=True)
