#!/usr/bin/env python3
"""Exercise production main-owner/lazy helpers; RTOS boundary fault injection."""
from pathlib import Path
import re,subprocess,os
r=Path(__file__).resolve().parents[1];d=Path(os.environ.get('CYM_TEST_OUT','/home/dev/projects/cym-targeted-refactor-20261017'))/'owners';d.mkdir(parents=True,exist_ok=True)
s=(r/'ESP32C5/main/main.c').read_text()
def fn(name):
 m=re.search(r'(?m)^static [^;\n]+\b'+name+r'\([^;]*?\)\s*\{',s);assert m,name
 i=s.index('{',m.start())+1;level=1
 while level:level+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]+'\n'
def run(name,code,flags=[]):
 p=d/(name+'.c');p.write_text(code);exe=d/name
 subprocess.run(['cc','-std=c11','-g','-fsanitize=address,undefined','-no-pie',*flags,str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
base=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
"""
shot=base+r"""
typedef uint8_t StackType_t;typedef int screenshot_msg_t;
static void *screenshot_task_handle,*screenshot_queue,*screenshot_task_stack;
static int screenshot_task_buffer,fail,allocations,queues,calls;
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_INTERNAL 2
#define MALLOC_CAP_8BIT 4
#define tskIDLE_PRIORITY 0
static void screenshot_save_task(void*p){}
static void *xQueueCreate(int n,int z){calls++;assert(n==1);if(fail==1)return NULL;queues++;return malloc(8);}
static void vQueueDelete(void*p){assert(p);queues--;free(p);}
static void *heap_caps_malloc(int n,int c){calls++;assert(n==4096);if(fail==2)return NULL;allocations++;return malloc(n);}
static void heap_caps_free(void*p){if(p){allocations--;free(p);}}
static void *xTaskCreateStatic(void(*f)(void*),const char*n,int z,void*a,int pri,void*st,void*t){assert(z==4096&&pri==2&&st&&t);return fail==3?NULL:(void*)1;}
"""+fn('screenshot_worker_ensure')+r"""
int main(void){
#if CONFIG_BOARD_HAS_PSRAM
 for(fail=1;fail<=3;fail++){
  assert(!screenshot_worker_ensure());assert(!allocations&&!queues&&!screenshot_task_handle&&!screenshot_queue&&!screenshot_task_stack);
 }
 fail=0;assert(screenshot_worker_ensure());int before=calls;assert(screenshot_worker_ensure()&&calls==before);
 assert(allocations==1&&queues==1);heap_caps_free(screenshot_task_stack);vQueueDelete(screenshot_queue);
#else
 assert(!screenshot_worker_ensure());assert(!calls);
#endif
 puts("PASS production lazy screenshot admission/failure unwind/reentry/no-PSRAM");
}
"""
run('screenshot-psram',shot,['-DCONFIG_BOARD_HAS_PSRAM=1']);run('screenshot-internal',shot,['-DCONFIG_BOARD_HAS_PSRAM=0'])
ot=base+r"""
#include <setjmp.h>
#define ESP_OK 0
#define ESP_LOGW(...) ((void)0)
#define eSuspended 3
#define configNUMBER_OF_CORES 2
#define pdTRUE 1
#define portMAX_DELAY 999
#define pdMS_TO_TICKS(x) (x)
typedef struct {bool valid;double latitude,longitude,altitude,accuracy,altitude_m,accuracy_m;}gps_data_t;
static gps_data_t gps,s_ots_end_geo;
static void *s_ots_stop_handle,*g_active_survey,*s_ots_allowlist,*s_ots_tmr,*core_task,*sd_spi_mutex;
static bool s_ots_stopping,s_ots_show_results,s_ots_stop_done,s_ots_worker_parked;
static int s_ots_generation,s_ots_worker_generation,s_ots_finalize_result,s_ots_allowlist_count,s_ots_session;
static int notifications,deletes,state,stops,takes,gives,finalizes;static jmp_buf park;
static const gps_data_t *gps_best(void){return &gps;}
static void xTaskNotifyGive(void*p){assert(p);notifications++;}
static int eTaskGetState(void*p){return state;}
static void *xTaskGetCurrentTaskHandleForCore(unsigned c){return c==1?core_task:NULL;}
static void vTaskDelete(void*p){assert(state==eSuspended&&!core_task&&p);deletes++;}
static void ulTaskNotifyTake(int a,int b){assert(notifications);}
static int ot_radio_scheduler_stop(void){return ++stops<3?-1:0;}
static void vTaskDelay(int n){}
static int xSemaphoreTake(void*p,int n){return ++takes<3?0:1;}
static void xSemaphoreGive(void*p){gives++;}
static int ot_survey_stop(int*p,gps_data_t*g){assert(!g_active_survey&&takes==3&&g->valid);finalizes++;return 0;}
static void vTaskSuspend(void*p){longjmp(park,1);}
"""+fn('s_ots_request_stop')+fn('s_ots_owner_poll')+fn('s_ots_stop_task')+r"""
int main(void){
 s_ots_request_stop(true);assert(!notifications);
 s_ots_stop_handle=(void*)1;g_active_survey=(void*)2;gps.valid=true;gps.latitude=3;gps.accuracy=4;
 s_ots_request_stop(true);assert(notifications==1&&!g_active_survey&&s_ots_end_geo.latitude==3&&s_ots_end_geo.accuracy_m==4);
 s_ots_request_stop(false);assert(notifications==1&&s_ots_show_results);
 sd_spi_mutex=(void*)3;if(!setjmp(park))s_ots_stop_task(NULL);
 assert(stops==3&&takes==3&&gives==1&&finalizes==1&&s_ots_worker_parked);
 s_ots_owner_poll();assert(!deletes);
 state=eSuspended;core_task=s_ots_stop_handle;s_ots_owner_poll();assert(!deletes);
 core_task=NULL;s_ots_allowlist=malloc(64);s_ots_allowlist_count=4;s_ots_tmr=(void*)4;s_ots_worker_generation=1;s_ots_generation=2;
 s_ots_owner_poll();assert(deletes==1&&!s_ots_allowlist&&!s_ots_allowlist_count&&!s_ots_stop_done&&!s_ots_stopping);
 s_ots_stop_handle=(void*)1;s_ots_worker_parked=true;s_ots_stopping=true;s_ots_worker_generation=2;
 s_ots_owner_poll();assert(deletes==2&&s_ots_stop_done&&s_ots_stopping);
 puts("PASS production OT main-owner request/generation/SD retries/park/off-core/result retention");
}
"""
run('ot-main-owner',ot)
log=re.sub(r'^#include .*$', '',(r/'ESP32C5/main/legacy_log_lifetime.h').read_text(),flags=re.M)
race=base+r"""
#include <pthread.h>
typedef void *QueueHandle_t;
#define portMUX_TYPE pthread_mutex_t
#define portMUX_INITIALIZER_UNLOCKED PTHREAD_MUTEX_INITIALIZER
#define portENTER_CRITICAL(p) pthread_mutex_lock(p)
#define portEXIT_CRITICAL(p) pthread_mutex_unlock(p)
static int deleted;static void vQueueDelete(void*p){deleted++;free(p);}
"""+log+r"""
static pthread_barrier_t entered,leave_now;static QueueHandle_t q;
static void *producer(void*x){cym_log_enter();pthread_barrier_wait(&entered);pthread_barrier_wait(&leave_now);assert(q);memset(q,7,160);cym_log_leave();return NULL;}
int main(void){
 pthread_barrier_init(&entered,NULL,2);pthread_barrier_init(&leave_now,NULL,2);
 for(int i=0;i<7;i++){
  q=malloc(i==3?3200:5120);pthread_t t;assert(!pthread_create(&t,NULL,producer,NULL));pthread_barrier_wait(&entered);
  assert(!cym_log_retire(&q,false)&&q);pthread_barrier_wait(&leave_now);pthread_join(t,NULL);
  assert(cym_log_retire(&q,false)&&!q);cym_log_enter();assert(!q);cym_log_leave();assert(cym_log_retire(&q,false));
 }
 assert(deleted==7);puts("PASS production log gate: real pthread producer parked across retirement, seven capacities, late producer");
}
"""
run('log-concurrent',race,['-D_XOPEN_SOURCE=700','-pthread'])
