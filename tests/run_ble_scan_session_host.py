#!/usr/bin/env python3
"""Production GAP admission/cancel wrappers, with faulted controller boundaries."""
from pathlib import Path
import os,re,subprocess
R=Path(__file__).resolve().parents[1];s=(R/'ESP32C5/main/main.c').read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'ble-session';D.mkdir(parents=True,exist_ok=True)
def fn(n):
 m=re.search(r'static (?:int|bool|void) '+n+r'\([^;]*?\)\s*\{',s)
 if not m:return ''
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
pre=r"""
#define bt_stage(stage,rc) ((void)0)

#include <stdint.h>
#include <stdbool.h>
static void *wardrive_task_handle;static bool wardrive_active,wardrive_task_done,wdp_ble_cleanup_pending;
static uint32_t s_bt_cham_token;

#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
static bool nimble_cleanup_busy;
#include <stdio.h>
#include <stddef.h>
typedef void *TaskHandle_t;
#define MYNEWT_VAL(x) EXT
#define BLE_HS_EBUSY 15
#define BLE_HS_EALREADY 2
#define BLE_HS_EDISABLED 30
#define BLE_HS_FOREVER 0
#define BLE_OWN_ADDR_PUBLIC 0
#define BLE_HCI_SCAN_FILT_NO_WL 0
#define TAG "host"
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
#define pdMS_TO_TICKS(x) (x)
struct ble_gap_event{int type;};
struct ble_gap_ext_disc_params{int itvl,window,passive;};
struct ble_gap_disc_params{int itvl,window,filter_policy,limited,passive,filter_duplicates;};
static void *s_bt_transition_owner;
static bool s_bt_scan_api_busy,bt_scan_worker_busy,s_bt_reports_accept;
static TaskHandle_t s_bt_scan_owner,bt_scan_task_handle,self=(void*)1;
static unsigned s_bt_reports_inflight;static int s_bt_report_mux;
static bool nimble_initialized=true,nimble_stop_requested,bt_tracking_mode;
static unsigned starts,cancels,resets,diag_starts,diag_ends;static int start_rc,cancel_rc;static bool debug;
static TaskHandle_t xTaskGetCurrentTaskHandle(void){return self;}
static void vTaskDelay(int t){(void)t;}
static void bt_reset_counters(void){resets++;}
static uint32_t bt_diag_begin(void){if(debug)diag_starts++;return debug?1:0;}
static void bt_diag_end(const char*b,uint32_t id){(void)b;(void)id;if(debug)diag_ends++;}
static void log_heap_stats(const char*s){(void)s;}
static int bt_gap_event_callback(struct ble_gap_event*e,void*a){return 0;}
static int ble_gap_ext_disc(int a,int b,int c,int d,int e,int f,struct ble_gap_ext_disc_params*g,struct ble_gap_ext_disc_params*h,int(*cb)(struct ble_gap_event*,void*),void*j){starts++;return start_rc;}
static int ble_gap_disc(int a,int b,struct ble_gap_disc_params*c,int(*cb)(struct ble_gap_event*,void*),void*d){starts++;return start_rc;}
static int ble_gap_disc_cancel(void){cancels++;return cancel_rc;}
"""
stop=fn('bt_stop_scan')
if stop.startswith('static void'):stop=stop.replace('static void bt_stop_scan','static void old_stop_scan')+'\nstatic bool bt_stop_scan(void){old_stop_scan();return true;}'
code=pre+fn('bt_scan_session_begin')+fn('bt_scan_session_start_result')+fn('bt_start_scan')+fn('bt_start_scan_passive')+stop+r"""
int main(void){for(int dbg=0;dbg<2;dbg++){
 debug=dbg;diag_starts=diag_ends=starts=cancels=resets=0;self=(void*)1;
 assert(bt_start_scan()==0);unsigned before=starts;
 self=(void*)2;assert(bt_start_scan()!=0&&"foreign scanner cannot reset/start over active owner");assert(starts==before&&resets==1);
 assert(!bt_stop_scan()&&"stale foreign worker cannot cancel successor");assert(cancels==0);
 self=(void*)1;cancel_rc=7;assert(!bt_stop_scan());assert(s_bt_scan_owner==self);
 self=(void*)2;assert(bt_start_scan_passive()!=0);self=(void*)1;cancel_rc=0;
 s_bt_reports_inflight=1;assert(!bt_stop_scan()&&"in-flight callback must retain owner");s_bt_reports_inflight=0;
 assert(bt_stop_scan());assert(!s_bt_scan_owner&&!s_bt_reports_accept);
 start_rc=7;assert(bt_start_scan()!=0);assert(!s_bt_scan_owner);start_rc=0;
 bt_scan_worker_busy=true;bt_scan_task_handle=(void*)2;assert(bt_start_scan()!=0);bt_scan_worker_busy=false;
 assert(bt_start_scan_passive()==0);assert(bt_stop_scan());
 unsigned old_resets=resets;bt_tracking_mode=true;assert(bt_start_scan()==0);assert(resets==old_resets);assert(bt_stop_scan());bt_tracking_mode=false;
 assert(dbg || (!diag_starts&&!diag_ends));
 }puts("PASS production shared BLE session: foreign start/stop, cancel failure, callback quiescence, failure unwind, worker reservation, active/passive, debug on/off");}
"""
(D/'host.c').write_text(code)
for ext in [0,1]:
 for psram in [0,1]:
  subprocess.run(['cc','-std=gnu11','-O1','-fsanitize=undefined',f'-DEXT={ext}',f'-DCONFIG_BOARD_HAS_PSRAM={psram}',str(D/'host.c'),'-o',str(D/'host')],check=True)
  subprocess.run([str(D/'host')],check=True)
