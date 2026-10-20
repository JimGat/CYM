from pathlib import Path
import re, subprocess, json, hashlib, os
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'ble-scheduling';D.mkdir(parents=True,exist_ok=True)
I=Path('/home/dev/esp/esp-idf');M=(R/'ESP32C5/main/main.c').read_text();K=(I/'components/freertos/FreeRTOS-Kernel/tasks.c').read_text()
def fn(s,n):
 m=re.search(r'(?:static\s+)?(?:void|bool|BaseType_t)\s+'+n+r'\([^;]*?\)\s*\{',s);assert m,n
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
macro=next(l for l in (I/'components/freertos/FreeRTOS-Kernel/include/freertos/projdefs.h').read_text().splitlines() if '#define pdMS_TO_TICKS' in l)
pre=r"""
#define RTC_NOINIT_ATTR
#define BT_STAGE_ENABLED() DBG
#define BT_STAGE_GENERATION() (1u)
#define BT_STAGE_LOCK() ((void)0)
#define BT_STAGE_UNLOCK() ((void)0)
#define BT_STAGE_CURRENT(g,q,s,r) ((void)0)
#define BT_STAGE_PREVIOUS(g,q,s,r) ((void)0)
#define BT_STAGE_BOOT_STATUS(s,r) ((void)0)
#include "ble_stage_diag.h"

#define _XOPEN_SOURCE 700
#include <ucontext.h>
#include <setjmp.h>
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
static bool s_bt_resource_capture;static uint32_t s_bt_resource_failures;
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int BaseType_t;typedef unsigned TickType_t;typedef void *TaskHandle_t;
#define configTICK_RATE_HZ HZ
#define pdPASS 1
#define pdFAIL 0
#define pdTRUE 1
#define pdFALSE 0
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define TAG "probe"
#define configASSERT(x) assert(x)
#define taskIS_SCHEDULER_SUSPENDED() 0
#define prvENTER_CRITICAL_OR_SUSPEND_ALL(x) ((void)0)
#define prvEXIT_CRITICAL_OR_RESUME_ALL(x) 0
#define traceTASK_DELAY() ((void)0)
#define mtCOVERAGE_TEST_MARKER() ((void)0)
static volatile bool bt_scan_active,bt_scan_worker_busy,bt_scan_create_pending;
static bool s_bt_scan_api_busy,nimble_cleanup_busy;
static TaskHandle_t s_bt_transition_owner;
static void *wardrive_task_handle;static bool wardrive_active,wardrive_task_done,wdp_ble_cleanup_pending;
static uint32_t s_bt_cham_token;static TaskHandle_t s_bt_scan_owner,bt_scan_task_handle;
static bool ble_scan_finished,ble_scan_needs_ui_update,bt_locator_needs_ui_update,bt_sas_needs_update,ble_obs_store_pending;
static char ble_scan_status_text[80];static int g_bt_scan_duration_s=1,bt_device_count,bt_airtag_count,bt_smarttag_count;
static ucontext_t creator,worker;static char worker_stack[65536];static jmp_buf boundary;
static bool alive,blocked,deferred,creator_returned;static unsigned zero_yields,blocks,starts,cancels,feeds;
static int create_rc=pdPASS,start_rc,stop_failures;static bool early_cancel;
static void bt_scan_task(void*);
static bool in_worker;
static void scheduler_yield(void){
 if(!in_worker){blocked=false;if(alive)swapcontext(&creator,&worker);return;}
 if(blocked){blocked=false;in_worker=false;swapcontext(&worker,&creator);in_worker=true;return;}
 // Worker priority 5 remains ready; creator 1 and idle 0 are not eligible.
 if(++zero_yields==10000)longjmp(boundary,1);
}
#define portYIELD_WITHIN_API() scheduler_yield()
static void prvAddCurrentTaskToDelayedList(TickType_t ticks,int indefinite){assert(ticks>0);blocks++;blocked=true;}
static void task_entry(void){in_worker=true;bt_scan_task(NULL);assert(!"task returned");}
static int xTaskCreate(void(*f)(void*),const char*n,int stack,void*a,int priority,TaskHandle_t*out){
 assert(f==bt_scan_task&&stack==4096&&priority==5);
 if(create_rc!=pdPASS)return create_rc;
 *out=(void*)2;alive=true;getcontext(&worker);worker.uc_stack.ss_sp=worker_stack;worker.uc_stack.ss_size=sizeof(worker_stack);worker.uc_link=&creator;makecontext(&worker,task_entry,0);
 if(!deferred)swapcontext(&creator,&worker); // FreeRTOS ready-list immediate higher-priority preemption boundary.
 return pdPASS;
}
static void vTaskDelete(void*p){assert(p==NULL);alive=false;in_worker=false;setcontext(&creator);abort();}
static int bt_start_scan(void){starts++;return start_rc;}
static bool bt_stop_scan(void){cancels++;if(stop_failures){stop_failures--;return false;}return true;}
"""
pre += re.search(r'typedef enum \{ BT_SCAN_RUNNING.*?bt_scan_outcome = BT_SCAN_SUCCESS;', M, re.S).group(0) + '\n'
post=r"""
int main(int argc,char**argv){assert(argc==2);bt_stage_boot(1,false);const char *mode=argv[1];
 deferred=!strcmp(mode,"deferred")||!strcmp(mode,"early-cancel");early_cancel=!strcmp(mode,"early-cancel");
 if(!strcmp(mode,"create-fail"))create_rc=pdFAIL;
 if(!strcmp(mode,"start-fail"))start_rc=7;
 if(!strcmp(mode,"cancel-retry"))stop_failures=3;
 if(setjmp(boundary)){
  assert(bt_scan_create_pending&&bt_scan_worker_busy&&!creator_returned&&starts==0&&blocks==0);
  printf("OBSERVED_STARVATION HZ=%u delay1ms=%u pending=%d creator_returned=%d gap_starts=%u zero_yields=%u positive_blocks=%u\n",HZ,pdMS_TO_TICKS(1),bt_scan_create_pending,creator_returned,starts,zero_yields,blocks);return 42;
 }
 int ret=bt_scan_worker_start();creator_returned=true;feeds++;
 if(create_rc!=pdPASS){assert(ret==pdFAIL&&!alive&&!bt_scan_active&&!bt_scan_worker_busy&&!bt_scan_create_pending&&!bt_scan_task_handle);puts("PASS create-failure unwinds");return 0;}
 assert(ret==pdPASS&&!bt_scan_create_pending);
 if(early_cancel)bt_scan_active=false;
 for(int i=0;alive&&i<100;i++){swapcontext(&creator,&worker);feeds++;}
 assert(!alive&&!bt_scan_worker_busy&&!bt_scan_task_handle&&!bt_scan_active&&ble_scan_finished);
 assert(early_cancel?starts==0:starts==1);
 if(start_rc)assert(cancels==0);else if(!early_cancel)assert(cancels==(!strcmp(mode,"cancel-retry")?4:1));
 printf("PASS HZ=%u case=%s delay1ms=%u zero_yields=%u blocks=%u main_progress=%u starts=%u cancels=%u\n",HZ,mode,pdMS_TO_TICKS(1),zero_yields,blocks,feeds,starts,cancels);return 0;
}
"""
worker=fn(M,'bt_scan_task');helper=fn(M,'bt_scan_worker_start');delay=fn(K,'vTaskDelay')
results=[]
for variant in ['production']:
 body=worker if variant=='production' else worker.replace('vTaskDelay(pdMS_TO_TICKS(1));','vTaskDelay(1);')
 assert body!=worker or variant=='production'
 src=D/(variant+'.c');src.write_text(pre+'\n'+macro+'\n'+delay+'\n'+helper+'\n'+body+'\n'+post)
 for hz,dbg in [(h,d) for h in [100,1000] for d in [0,1]]:
  exe=D/(variant+'-'+str(hz)+'-'+str(dbg))
  cmd=['cc','-std=gnu11','-O1','-Wall','-Wextra','-Wno-unused-parameter',f'-DHZ={hz}',f'-DDBG={dbg}','-I'+str(R/'ESP32C5/main'),str(src),'-o',str(exe)]
  c=subprocess.run(cmd,capture_output=True,text=True);assert c.returncode==0,c.stderr
  for case in ['immediate','deferred','create-fail','early-cancel','start-fail','cancel-retry']:
   p=subprocess.run([str(exe),case],capture_output=True,text=True,timeout=5)
   expected=0
   results.append(dict(variant=variant,hz=hz,debug=dbg,case=case,exit=p.returncode,expected=expected,output=p.stdout+p.stderr))
   print(variant,hz,case,p.returncode,p.stdout.strip())
(D/'results.json').write_text(json.dumps(results,indent=2))
(D/'provenance.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(M.encode()).hexdigest(),sdk_tasks_sha256=hashlib.sha256(K.encode()).hexdigest(),functions=['bt_scan_worker_start','bt_scan_task','IDF vTaskDelay','IDF pdMS_TO_TICKS'],limits='Actual extracted C and SDK delay function. RTOS context-switch/ready-list boundaries modeled, no ESP hardware, RF or watchdog emulation. All tests exercise current production; immediate preemption is a worst-case same-core schedule on both uniprocessor and SMP targets.'),indent=2))

assert all(x["exit"]==x["expected"] for x in results), "Production scheduler regression"
