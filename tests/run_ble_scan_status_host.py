#!/usr/bin/env python3
"""Actual SAS main-loop branch + production worker; SDK/LVGL boundaries only."""
from pathlib import Path
import os,runpy,subprocess,json
R=Path(__file__).resolve().parents[1]
x=runpy.run_path(str(R/'tests/run_ble_scan_scheduling_host.py'))
M=x['M'];a=M.index('if (bt_sas_needs_update && bt_sas_ui_active) {');i=M.index('{',a)+1;depth=1
while depth:depth+=(M[i]=='{')-(M[i]=='}');i+=1
D=Path(os.environ['CYM_TEST_OUT'])/'ble-status';D.mkdir(parents=True,exist_ok=True)
ui=r"""
#define LV_OBJ_FLAG_HIDDEN 1
static bool bt_sas_ui_active=true,hidden;static int bt_sas_selected_idx=-1;
static void *bt_sas_status_label=(void*)1;static char rendered[100];static int refreshes;
static bool lv_obj_is_valid(void*p){return p!=NULL;}
static void lv_label_set_text(void*p,const char*s){snprintf(rendered,sizeof(rendered),"%s",s);}
static void lv_obj_add_flag(void*p,int f){hidden=true;}
static void lv_obj_clear_flag(void*p,int f){hidden=false;}
static bool bt_sas_list_changed(void){return false;} // separately executed production invalidation runner
static void bt_sas_refresh_list(void){refreshes++;}
"""
navpre=r"""
#define cym_fsd_input_epoch() ((void)0) /* unrelated FSD hook mocked */
typedef int lv_event_t;
static bool init_ok,ui_locked;
static bool ensure_ble_mode(void){return init_ok;}
static void *bt_sas_save_overlay,*bt_sas_save_ta,*bt_sas_list,*bt_sas_next_btn,*bt_sas_nav_bar,*bt_sas_nav_prev,*bt_sas_nav_lbl,*bt_sas_nav_next;
static int bt_sas_rendered_count,bt_sas_page,home_calls,parent_calls;static bool nav_to_menu_flag;
static int nav_stack_depth,nav_stack[4];
static void (*nav_deferred_show_fn)(void),(*g_screen_stop_fn)(void),(*g_screen_back_fn)(void);
static void lv_obj_del(void*p){(void)p;}
static void clock_cancel_radio_navigation(void){}
static void run_screen_stop_fn(void);
static void parent(void){parent_calls++;}
static void (*nav_show_lookup(int n))(void){(void)n;return parent;}
static void show_menu(void){home_calls++;run_screen_stop_fn();}
"""
def block(marker):
 a=M.index(marker);j=M.index('{',a)+1;d=1
 while d:d+=(M[j]=='{')-(M[j]=='}');j+=1
 return M[a:j]
nav=navpre+'\n'.join(x['fn'](M,n) for n in ['bt_scan_stop','bt_sas_stop','bt_sas_rescan_cb','run_screen_stop_fn','home_btn_event_cb','nav_back_cb'])
entry=x['fn'](M,'show_bt_scan_select_screen');entry=entry[entry.index('    // Switch to BLE and start scan'):]
nav+='static void enter_scan_tail(void){'+entry+'\n'
nav+='static void dispatch_navigation(void){'+block('if (nav_to_menu_flag) {')+block('if (nav_deferred_show_fn) {')+'}'
post=r"""
static void run_worker(void){deferred=true;assert(bt_scan_worker_start()==pdPASS);for(int i=0;alive&&i<100;i++)swapcontext(&creator,&worker);assert(!alive);apply_ui();}
int main(void){
 for(int stale=0;stale<2;stale++){
  bt_device_count=stale?3:0;start_rc=7;bt_sas_selected_idx=stale?0:-1;run_worker();
  assert(!hidden&&strstr(rendered,"failed (7)")&&"actual refresh must retain error even with stale rows/selection");
 }
 bt_sas_selected_idx=-1;start_rc=0;bt_device_count=0;run_worker();assert(!hidden&&!strcmp(rendered,"No devices found"));
 bt_device_count=3;run_worker();assert(hidden);
 bt_device_count=0;deferred=true;assert(bt_scan_worker_start()==pdPASS);bt_scan_active=false;
 while(alive)swapcontext(&creator,&worker);apply_ui();assert(!hidden&&strstr(rendered,"cancel"));
 start_rc=0;run_worker();assert(!hidden&&!strcmp(rendered,"No devices found"));
 for(int rows=0;rows<2;rows++){
  bt_sas_ui_active=true;bt_sas_status_label=(void*)1;bt_sas_selected_idx=-1;bt_device_count=rows?4:0;
  init_ok=false;enter_scan_tail();bt_sas_needs_update=true;apply_ui();assert(strstr(rendered,"failed")&&!hidden);
 }
 init_ok=true;create_rc=pdFAIL;enter_scan_tail();bt_sas_needs_update=true;apply_ui();assert(strstr(rendered,"failed")&&!hidden);
 create_rc=pdPASS;deferred=true;start_rc=0;bt_sas_rescan_cb(NULL);assert(!bt_sas_entry_error);while(alive)swapcontext(&creator,&worker);apply_ui();assert(!strstr(rendered,"failed"));
 for(int layout=0;layout<2;layout++)for(int home=0;home<2;home++){
  bt_sas_entry_error=NULL;

  bt_sas_ui_active=true;bt_sas_status_label=(void*)1;bt_sas_list=(void*)2;
  g_screen_stop_fn=bt_sas_stop;g_screen_back_fn=layout?parent:NULL;nav_stack_depth=2;
  start_rc=0;deferred=true;assert(bt_scan_worker_start()==pdPASS);swapcontext(&creator,&worker);assert(alive);
  if(home)home_btn_event_cb(NULL);else nav_back_cb(NULL);
  assert(bt_sas_ui_active&&alive);dispatch_navigation();
  assert(!bt_sas_ui_active&&!alive&&!bt_scan_worker_busy&&!bt_sas_list&&!bt_sas_status_label&&!g_screen_stop_fn);
  apply_ui();dispatch_navigation();
 }
 assert(home_calls==2&&parent_calls==2);
 assert(refreshes==0);puts("PASS actual SAS refresh: failure zero/stale/selected, retry success, empty completion, cancel");
}
"""
code=x['pre']+'\n'+x['macro']+'\n'+x['delay']+'\n'+x['helper']+'\n'+x['worker']+'static const char *bt_sas_entry_error;'+ui+'\nstatic void apply_ui(void){'+M[a:i]+'}\n'+nav+post
(D/'host.c').write_text(code)
results=[]
for debug in [0,1]:
 subprocess.run(['cc','-std=gnu11','-O1','-DHZ=100',f'-DDBG={debug}','-I'+str(R/'ESP32C5/main'),str(D/'host.c'),'-o',str(D/'host')],check=True)
 p=subprocess.run([str(D/'host')],capture_output=True,text=True);print(p.stdout+p.stderr);results.append({'debug':debug,'exit':p.returncode,'output':p.stdout+p.stderr})
(D/'results.json').write_text(json.dumps(results,indent=2));assert all(r['exit']==0 for r in results)
