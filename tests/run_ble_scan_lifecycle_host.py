#!/usr/bin/env python3
"""Compile real BLE worker/start/stop/rescan helpers; deterministic RTOS boundary faults."""
from pathlib import Path
import os,re,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];M=R/'ESP32C5/main/main.c';s=M.read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'ble-lifecycle';D.mkdir(parents=True,exist_ok=True)
def fn(n):
 m=re.search(r'static (?:void|bool|BaseType_t) '+n+r'\([^;]*?\)\s*\{',s)
 if not m:return ''
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
pre=r"""
#define bt_stage(stage,rc) ((void)0)

#include <stdint.h>
#include <stdbool.h>
static const char *bt_sas_entry_error;static bool ensure_ble_mode(void){return true;}
static void *wardrive_task_handle;static bool wardrive_active,wardrive_task_done,wdp_ble_cleanup_pending;
static uint32_t s_bt_cham_token;

#include <assert.h>
#include <stdbool.h>
static bool nimble_cleanup_busy;
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef int BaseType_t;typedef void *TaskHandle_t;typedef int lv_event_t;
#define pdPASS 1
#define pdFAIL 0
#define pdMS_TO_TICKS(x) (x)
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define TAG "host"
#define LV_OBJ_FLAG_HIDDEN 1
static volatile bool bt_scan_active,bt_scan_worker_busy,bt_scan_create_pending;
static TaskHandle_t bt_scan_task_handle,s_bt_scan_owner;
static TaskHandle_t s_bt_transition_owner;
static bool s_bt_scan_api_busy;
static bool ble_scan_finished,ble_scan_needs_ui_update,bt_locator_needs_ui_update,bt_sas_needs_update,ble_obs_store_pending;
static char ble_scan_status_text[80];static int g_bt_scan_duration_s=1;
static int bt_device_count,bt_airtag_count,bt_smarttag_count,bt_devices[16];
static bool bt_sas_ui_active=true;static int bt_sas_selected_idx,bt_sas_page,bt_sas_rendered_count;
static void *bt_sas_next_btn,*bt_sas_status_label,*bt_sas_save_overlay,*bt_sas_save_ta,*bt_sas_list;
static void *bt_sas_nav_bar,*bt_sas_nav_prev,*bt_sas_nav_lbl,*bt_sas_nav_next;
static int creates,cancels,deletes,foreign_deletes,resets,start_rc,create_rc=pdPASS,stop_failures,join_after=-1,waits;
static TaskHandle_t self=(void*)2;
static void bt_scan_task(void*);
static void bt_scan_stop(void);
static TaskHandle_t xTaskGetCurrentTaskHandle(void){return self;}
static int xTaskCreate(void(*fn)(void*),const char*n,int stack,void*a,int prio,TaskHandle_t*out){
 assert(fn==bt_scan_task&&stack==4096&&prio==5);creates++;
 if(create_rc!=pdPASS)return create_rc;*out=(void*)2;return pdPASS;}
static void vTaskDelay(int ms){(void)ms;waits++;
 if(join_after>=0&&waits>=join_after){bt_scan_task_handle=NULL;bt_scan_worker_busy=false;join_after=-1;}}
static void vTaskDelete(void*p){deletes++;if(p)foreign_deletes++;}
static void bt_reset_counters(void){resets++;bt_device_count=0;memset(bt_devices,0,sizeof(bt_devices));}
static int bt_start_scan(void){return start_rc;}
static bool bt_stop_scan(void){cancels++;if(stop_failures){stop_failures--;return false;}return true;}
static bool lv_obj_is_valid(void*p){return p!=NULL;}
static void lv_obj_add_flag(void*p,int f){(void)p;(void)f;}
static void lv_obj_clear_flag(void*p,int f){(void)p;(void)f;}
static void lv_obj_del(void*p){(void)p;}
static void lv_label_set_text(void*p,const char*t){(void)p;(void)t;}
static void bt_sas_refresh_list(void){}
"""
helpers=fn('bt_scan_worker_start')
if not helpers:helpers='static BaseType_t bt_scan_worker_start(void){bt_scan_active=true;return xTaskCreate(bt_scan_task,"bt_scan_task",4096,NULL,5,&bt_scan_task_handle);}'
pre += re.search(r'typedef enum \{ BT_SCAN_RUNNING.*?bt_scan_outcome = BT_SCAN_SUCCESS;', s, re.S).group(0) + '\n'
post=r"""
static void reset(void){bt_scan_active=false;bt_scan_task_handle=NULL;bt_scan_worker_busy=false;bt_scan_create_pending=false;creates=cancels=deletes=foreign_deletes=resets=waits=0;start_rc=0;create_rc=pdPASS;join_after=-1;stop_failures=0;bt_sas_ui_active=true;}
int main(int argc,char**argv){assert(argc==2);reset();
 if(!strcmp(argv[1],"delayed")){
  bt_scan_active=true;bt_scan_worker_busy=true;bt_scan_task_handle=(void*)2;bt_device_count=7;bt_devices[0]=42;
  bt_sas_rescan_cb(NULL);
  assert(creates==0&&"must not create successor before delayed worker quiesces");
  assert(bt_device_count==7&&bt_devices[0]==42&&"must preserve old results while stop pending");
  assert(foreign_deletes==0);
 }else if(!strcmp(argv[1],"join")){
  bt_scan_active=true;bt_scan_worker_busy=true;bt_scan_task_handle=(void*)2;join_after=12;
  bt_sas_rescan_cb(NULL);assert(creates==1&&waits>=12);assert(!foreign_deletes);
  bt_sas_rescan_cb(NULL);assert(creates==1&&"repeated presses cannot overlap delayed new worker");
 }else if(!strcmp(argv[1],"create-failure")){
  create_rc=pdFAIL;assert(bt_scan_worker_start()!=pdPASS);assert(!bt_scan_active&&!bt_scan_worker_busy&&!bt_scan_task_handle);
  create_rc=pdPASS;assert(bt_scan_worker_start()==pdPASS);assert(creates==2);
 }else if(!strcmp(argv[1],"worker")){
  bt_scan_active=true;bt_scan_worker_busy=true;bt_scan_task_handle=self;stop_failures=3;bt_scan_task(NULL);
  assert(cancels==4&&"cancel failures must retain owner and retry before releasing task");
  assert(!bt_scan_task_handle&&!bt_scan_worker_busy&&!bt_scan_active&&ble_scan_finished);assert(!foreign_deletes);
 }else if(!strcmp(argv[1],"start-failure")){
  bt_scan_active=true;bt_scan_worker_busy=true;bt_scan_task_handle=self;start_rc=7;bt_scan_task(NULL);
  assert(!bt_scan_task_handle&&!bt_scan_worker_busy&&!bt_scan_active&&ble_scan_finished&&bt_sas_needs_update);
 }else if(!strcmp(argv[1],"navigation")){
  for(int layout=0;layout<2;layout++)for(int route=0;route<2;route++){
   bt_scan_active=true;bt_scan_worker_busy=true;bt_scan_task_handle=self;join_after=3;waits=0;
   bt_sas_list=bt_sas_status_label=bt_sas_next_btn=bt_sas_nav_bar=bt_sas_nav_prev=bt_sas_nav_lbl=bt_sas_nav_next=(void*)1;
   bt_sas_stop();assert(!bt_sas_ui_active&&!bt_sas_list&&!bt_sas_status_label&&!bt_sas_next_btn&&!bt_scan_task_handle&&!foreign_deletes);
   assert(bt_scan_worker_start()==pdPASS);bt_sas_ui_active=true;
  }
 }else abort();printf("PASS production BLE lifecycle %s\n",argv[1]);return 0;}
"""
code=pre+helpers+fn('bt_scan_stop')+fn('bt_sas_stop')+fn('bt_sas_rescan_cb')+fn('bt_scan_task')+post
(D/'host.c').write_text(code);(D/'provenance.json').write_text(json.dumps({'source_sha256':hashlib.sha256(M.read_bytes()).hexdigest(),'production_helpers':['bt_scan_worker_start','bt_scan_stop','bt_sas_stop','bt_sas_rescan_cb','bt_scan_task']},indent=2))
subprocess.run(['cc','-std=gnu11','-g','-O1','-fsanitize=undefined',str(D/'host.c'),'-o',str(D/'host')],check=True)
results=[]
for case in ['delayed','join','create-failure','worker','start-failure','navigation']:
 p=subprocess.run([str(D/'host'),case],capture_output=True,text=True);print(p.stdout+p.stderr,end='');results.append(dict(case=case,exit_code=p.returncode))
(D/'results.json').write_text(json.dumps(results,indent=2));assert all(x['exit_code']==0 for x in results),results
