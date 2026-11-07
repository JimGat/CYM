#!/usr/bin/env python3
# Deterministic interleavings of the real worker, request and snapshot functions.
import os,re,subprocess,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];s=(Path(os.environ.get("CYM_POWER_SOURCE",R))/"ESP32C5/main/main.c").read_text()
O=Path(os.environ["CYM_TEST_OUT"])/"power-worker";O.mkdir(parents=True,exist_ok=False)
a=s.index("typedef struct {\n    uint8_t level",s.index("// Power Mode Popup"));b=s.index("static void powermode_start_poll(void)",a);body=s[a:b]
def fn(sig):
 m=re.search(re.escape(sig)+r"[^;{}]*\)\s*\{",s);assert m,sig
 a=m.start();i=m.end();d=1
 while d:d+=(s[i]=="{")-(s[i]=="}");i+=1
 return s[a:i]
pre=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <setjmp.h>
typedef int esp_err_t;typedef int BaseType_t;typedef void*TaskHandle_t;typedef int portMUX_TYPE;typedef int lv_timer_t;
#define portMUX_INITIALIZER_UNLOCKED 0
#define ESP_OK 0
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_NO_MEM 0x101
#define ESP_ERR_TIMEOUT 0x107
#define PWR_RADIO_OFF 0
#define PWR_RADIO_BUSY 1
#define PWR_RADIO_FAILED 2
#define PWR_RADIO_APPLIED 3
#define pdMS_TO_TICKS(x) (x)
#define PWR_LVL_NORMAL 1
#define PWR_LVL_MAX 2
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY 0xffffffff
static int critical;
#define portENTER_CRITICAL(p) do{(void)(p);assert(!critical);critical++;}while(0)
#define portEXIT_CRITICAL(p) do{(void)(p);assert(critical==1);critical--;}while(0)
uint8_t g_pwr_lvl=1;bool g_max_power_mode;
static jmp_buf waitpoint;static int notifications,create_fail=1,creates,saves,rapid,save_rc;static uint8_t levels[16];
static int wifi_rc,ble_rc;static int wifi_calls,ble_calls;static uint8_t wifi_levels[64],ble_levels[64];
int wifi_power_apply_requested(uint8_t l){assert(!critical);wifi_levels[wifi_calls++]=l;return wifi_rc;}
static int ble_power_apply_requested(uint8_t l){assert(!critical);ble_levels[ble_calls++]=l;return ble_rc;}
void power_policy_notify(void);
static void pwr_request(uint8_t);
unsigned ulTaskNotifyTake(int c,unsigned timeout){(void)c;(void)timeout;assert(!critical);if(!notifications)longjmp(waitpoint,1);notifications=0;return 1;}
TaskHandle_t xTaskGetCurrentTaskHandle(void){return (void*)2;}
void xTaskNotifyGive(TaskHandle_t t){assert(t);assert(!critical);notifications++;}
int nvs_settings_save_power_level(uint8_t l){assert(!critical);levels[saves++]=l;if(rapid){rapid=0;pwr_request(1);}return save_rc;}
BaseType_t xTaskCreate(void(*fn)(void*),const char*n,unsigned stack,void*a,int pri,TaskHandle_t*out){(void)n;(void)pri;assert(stack==4096);assert(!critical);creates++;if(create_fail)return 0;*out=(void*)1;if(!setjmp(waitpoint))fn(a);return pdPASS;}
"""
post=r"""
int main(void){
 pwr_request(2);assert(creates==1 && g_pwr_lvl==1 && !g_max_power_mode);assert(!s_pwr_job.req_seq && s_pwr_job.submit_rc!=0 && "allocation failure must not select or leave Applying");
 create_fail=0;pwr_request(2);assert(creates==2 && !saves && "immediate preemption blocks before unpublished request");
 assert(s_pwr_job.req_seq==1 && notifications);rapid=1;
 if(!setjmp(waitpoint))pwr_worker(NULL);
 pwr_job_t j=pwr_snapshot();assert(saves==2 && levels[0]==2 && levels[1]==1 && "immutable request saved before coalesced latest");
 assert(wifi_calls>=2 && ble_calls>=2 && wifi_levels[0]==2 && wifi_levels[1]==1 && ble_levels[0]==2 && ble_levels[1]==1 && "active Max to Normal must invoke immutable per-radio setters");
  assert(j.req_seq==j.done_seq && j.req_seq==2 && !j.busy && g_pwr_lvl==1);
 assert(sizeof(pwr_job_t)<=16 && "bounded internal control state");
 assert(j.saved_rc==0 && !critical && creates==2);
 save_rc=-1;pwr_request(2);if(!setjmp(waitpoint))pwr_worker(NULL);j=pwr_snapshot();assert(j.saved_rc!=0 && j.done_seq==j.req_seq && !j.busy);
 pwr_request(0);assert(s_pwr_job.req_seq==3 && "unsupported Low rejected");
 puts("PASS real worker: allocation failure/retry, immediate preemption, immutable snapshot, rapid coalescing, coherent terminal result, independent live radios, save failure");
}
"""
(O/"host.c").write_text(pre+body+fn("void power_policy_notify(")+fn("static void pwr_request(")+post)
c=["cc","-std=gnu11","-g","-fsanitize=address,undefined","-fno-pie","-no-pie",str(O/"host.c"),"-o",str(O/"host")]
b=subprocess.run(c,capture_output=True,text=True);(O/"compile.log").write_text(b.stdout+b.stderr);assert b.returncode==0,b.stderr
r=subprocess.run([str(O/"host")],capture_output=True,text=True);(O/"run.log").write_text(r.stdout+r.stderr);(O/"results.json").write_text(json.dumps(dict(command=c,exit=r.returncode,limitations=["deterministic injected task-create/save interleavings, not SMP stress or target timing", "owner adapter tested separately; worker passes immutable sequence level"]),indent=2));print(r.stdout+r.stderr);raise SystemExit(r.returncode)
