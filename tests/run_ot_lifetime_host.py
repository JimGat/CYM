#!/usr/bin/env python3
"""Compile actual OT scheduler lifecycle with fault-injected RTOS primitives."""
import os,re,subprocess
from pathlib import Path
r=Path(__file__).resolve().parents[1]
out=Path(os.environ.get('CYM_TEST_OUT','/home/dev/projects/cym-targeted-refactor-20261017'))/'ot';out.mkdir(parents=True,exist_ok=True)
src=(r/'ESP32C5/components/ot_survey/ot_radio.c').read_text()
src=re.sub(r'^#include.*$','',src,flags=re.M)
stub=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef int esp_err_t;typedef unsigned char StackType_t;typedef int StaticTask_t;
typedef void *TaskHandle_t;typedef void *SemaphoreHandle_t;typedef int ot_survey_profile_t;
typedef int ot_radio_slot_t;typedef int ot_sched_state_t;
typedef struct {bool(*switch_to_wifi)(void);bool(*switch_to_ble)(void);bool(*switch_to_154)(void);void(*switch_to_idle)(void);bool(*wifi_scan_busy)(void);}ot_radio_hooks_t;
#define OT_PROFILE_COUNT 8
#define OT_PROFILE_BALANCED 0
#define OT_SLOT_WIFI 0
#define OT_SLOT_BLE 1
#define OT_SLOT_154 2
#define OT_SLOT_ESPNOW 3
#define OT_SLOT_COUNT 4
#define OT_SCHED_IDLE 0
#define OT_SCHED_RUNNING 1
#define OT_SCHED_STOP_REQUESTED 2
#define OT_SCHED_PARKED 3
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_INVALID_ARG 3
#define ESP_ERR_TIMEOUT 4
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_INTERNAL 2
#define MALLOC_CAP_8BIT 4
#define pdTRUE 1
#define pdPASS 1
#define pdMS_TO_TICKS(x) (x)
#define configNUMBER_OF_CORES 2
#define eSuspended 3
#define eRunning 0
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
static int allocated,deleted,alloc_calls,fail_at,static_fail,dynamic_fail,task_state;
static void *heap_caps_malloc(size_t n,int caps){(void)caps;if(++alloc_calls==fail_at)return NULL;void *p=malloc(n);if(p)allocated++;return p;}
static void heap_caps_free(void *p){if(p){allocated--;free(p);}}
static TaskHandle_t xTaskCreateStaticPinnedToCore(void(*fn)(void*),const char*n,int sz,void*a,int pr,StackType_t*s,StaticTask_t*t,int c){return static_fail?NULL:(void*)1;}
static int xTaskCreate(void(*fn)(void*),const char*n,int sz,void*a,int pr,TaskHandle_t*h){*h=dynamic_fail?NULL:(void*)1;return dynamic_fail?0:1;}
static void vTaskDelete(TaskHandle_t t){assert(t && task_state==eSuspended);deleted++;}
static void vTaskDelay(int n){(void)n;}
static void vTaskSuspend(void *t){abort();}
static int eTaskGetState(TaskHandle_t t){return task_state;}
static TaskHandle_t core_task;
static TaskHandle_t xTaskGetCurrentTaskHandleForCore(unsigned c){return c==1?core_task:NULL;}
static TaskHandle_t xTaskGetCurrentTaskHandle(void){return (void*)2;}
static void *xSemaphoreCreateBinary(void){return (void*)3;}
static int xSemaphoreTake(void *s,int t){return 0;}
static void xSemaphoreGive(void*s){}
static const char *ot_survey_profile_name(int p){return "test";}
'''
tests=r'''
int main(void){
 assert(ot_radio_scheduler_start(0)==ESP_OK);
 /* An unparked timeout must retain task, storage, and conflicting admission. */
 assert(ot_radio_scheduler_stop()==ESP_ERR_TIMEOUT);
 assert(deleted==0 && g_ot_survey_active);
 assert(ot_radio_scheduler_start(0)==ESP_ERR_INVALID_STATE);
 s_state=OT_SCHED_PARKED;task_state=eRunning;
 assert(ot_radio_scheduler_stop()==ESP_ERR_TIMEOUT && deleted==0);
 task_state=eSuspended;core_task=s_task;
 assert(ot_radio_scheduler_stop()==ESP_ERR_TIMEOUT && deleted==0);
 core_task=NULL;assert(ot_radio_scheduler_stop()==ESP_OK);
 assert(allocated==0 && deleted==1 && !g_ot_survey_active);
 for(int mode=0;mode<4;mode++){
   alloc_calls=0;fail_at=mode==0?1:mode==1?2:0;static_fail=mode==2;dynamic_fail=1;
   if(mode==3)static_fail=1;
   int rc=ot_radio_scheduler_start(0);
#ifdef CONFIG_SPIRAM
   assert(rc!=ESP_OK);
#else
   assert(rc!=ESP_OK);
#endif
   assert(!g_ot_survey_active && allocated==0);
 }
 /* A PSRAM allocation/create failure must not silently consume internal RAM.
  * Leave dynamic creation healthy: the old fallback incorrectly succeeds. */
#ifdef CONFIG_SPIRAM
 dynamic_fail=0;
 for(int mode=0;mode<3;mode++){
   alloc_calls=0;fail_at=mode==0?1:mode==1?2:0;static_fail=mode==2;
   assert(ot_radio_scheduler_start(0)!=ESP_OK);
   assert(!g_ot_survey_active && allocated==0);
 }
#endif
 fail_at=static_fail=dynamic_fail=0;
 for(int i=0;i<20;i++){
   assert(ot_radio_scheduler_start(0)==ESP_OK);
   s_state=OT_SCHED_PARKED;task_state=eSuspended;
   assert(ot_radio_scheduler_stop()==ESP_OK && allocated==0);
 }
 puts("PASS OT: timeout retention, off-core gate, allocation/create failures, repeated retirement");
}
'''
for psram in [False,True]:
 c=out/f'ot-{int(psram)}.c';exe=c.with_suffix('');c.write_text(stub+src+tests)
 subprocess.run(['cc','-std=c11','-g','-fsanitize=address,undefined','-no-pie',*(['-DCONFIG_SPIRAM=1'] if psram else []),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
