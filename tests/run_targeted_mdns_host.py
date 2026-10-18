#!/usr/bin/env python3
from pathlib import Path
import subprocess,re,os
r=Path(__file__).resolve().parents[1];d=Path(os.environ.get('CYM_TEST_OUT','/home/dev/projects/cym-targeted-refactor-20261017'))/'mdns';d.mkdir(parents=True,exist_ok=True)
s=Path(os.environ.get('CYM_MDNS_SOURCE',str(r/'ESP32C5/managed_components/espressif__mdns/mdns_service.c'))).read_text()
def fn(name):
 m=re.search(r'^(?:static )?(?:esp_err_t|bool|void) '+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 i=m.end();depth=1
 while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
code=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef int esp_err_t;typedef void* TaskHandle_t;typedef int TickType_t;
typedef struct {int type;} mdns_action_t;
#define ACTION_TASK_STOP 1
#define pdPASS 1
#define pdTRUE 1
#define CYM_MDNS_BOUNDARY(...) ((void)0)
#define ESP_OK 0
#define ESP_ERR_TIMEOUT 9
#define ESP_ERR_INVALID_STATE 10
#define portTICK_PERIOD_MS 1
#define pdMS_TO_TICKS(n) (n)
#define configNUMBER_OF_CORES 2
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
#define ESP_LOGW(...) ((void)0)
enum {eRunning,eSuspended};
static TaskHandle_t s_service_task_handle=(void*)1;
static void *s_action_queue=(void*)2,*s_service_semaphore=(void*)3;
static bool s_stopping;static unsigned s_timer_inflight;static int s_admission_mux;
static int deleted,waited,sends,state=eRunning,oncore=1,delay_park=0;
static int stop_timer(void){return 0;}
static int xQueueSend(void*q,void*a,int t){(void)q;(void)a;(void)t;sends++;return 0;}
static void vTaskDelay(int n){assert(n);waited++;if(delay_park&&waited==2){state=eSuspended;oncore=0;}}
static int eTaskGetState(void*h){assert(h);return state;}
static void *xTaskGetCurrentTaskHandleForCore(unsigned c){return c==1&&oncore?(void*)1:NULL;}
static void vTaskDelete(void*h){assert(h==(void*)1);deleted++;}
static void vSemaphoreDelete(void*h){(void)h;}
"""+fn('service_task_stop')+r"""
int main(void){
 int rc=service_task_stop();assert(rc==ESP_ERR_TIMEOUT);assert(!deleted&&s_service_task_handle&&s_service_semaphore);assert(!sends);
 state=eSuspended;assert(service_task_stop()==ESP_ERR_TIMEOUT&&!deleted);
 oncore=0;assert(service_task_stop()==ESP_OK&&deleted==1&&!s_service_task_handle);
 assert(service_task_stop()==ESP_OK&&deleted==1);
 s_service_task_handle=(void*)1;state=eRunning;oncore=1;waited=0;delay_park=1;assert(service_task_stop()==0&&deleted==2);
 puts("PASS production mDNS full queue / timeout / off-core / delayed park / double stop");}
"""
p=d/'stop.c';p.write_text(code);exe=d/'stop'
subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-variable','-fsanitize=address,undefined','-no-pie',str(p),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)

# Actual init/free/admission helpers under partial-start and late-callback faults.
extra=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
typedef int esp_err_t;typedef void* QueueHandle_t;
typedef struct {int type;}mdns_action_t;
#define CYM_MDNS_BOUNDARY(...) ((void)0)
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NO_MEM 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_TIMEOUT 3
#define pdTRUE 1
#define pdPASS 1
#define MDNS_ACTION_QUEUE_LEN 16
#define MDNS_TASK_USE_SIMPLE_CREATE 0
#define CONFIG_MDNS_ENABLE_QUERY_CACHE 1
#define portENTER_CRITICAL(p) ((void)0)
#define portEXIT_CRITICAL(p) ((void)0)
#define HOOK_MALLOC_FAILED ((void)0)
#define MDNS_SERVICE_LOCK() ((void)0)
#define MDNS_SERVICE_UNLOCK() ((void)0)
static bool s_stopping,server,unregistered,pcbs;
static void *s_action_queue,*s_stack_buffer,*s_service_semaphore;
static int fail,stop_timeout,queued,freed,stack_freed,queue_deleted;
static bool mdns_priv_is_server_init(void){return server;}
static int mdns_priv_responder_init(void){if(fail==1)return 1;server=true;return 0;}
static void mdns_priv_responder_free(void){server=false;}
static void *xQueueCreate(int n,int z){(void)n;(void)z;return fail==2?NULL:(void*)1;}
static int mdns_priv_netif_init(void){unregistered=false;pcbs=true;return fail==3?-1:0;}
static int service_task_start(void){s_service_semaphore=(void*)2;s_stack_buffer=malloc(4096);return fail==4?-1:0;}
static void mdns_priv_netif_unregister_predefined_handlers(void){unregistered=true;}
static int service_task_stop(void){return stop_timeout?ESP_ERR_TIMEOUT:0;}
static void mdns_priv_pcb_deinit(void){assert(unregistered);pcbs=false;}
static int xQueueReceive(void*q,mdns_action_t**a,int t){assert(!pcbs);if(!queued)return 0;queued--;*a=malloc(sizeof(**a));return 1;}
static void free_action(mdns_action_t*a){freed++;free(a);}
static void vQueueDelete(void*q){assert(q&&!s_action_queue);queue_deleted++;}
static void mdns_priv_clear_tx_queue(void){}
static void mdns_priv_query_free(void){}
static void mdns_priv_browse_free(void){}
static void mdns_priv_cache_clear(void){}
static void mdns_mem_task_free(void*p){if(p){stack_freed++;free(p);}}
static void vSemaphoreDelete(void*p){assert(p);}
static int xQueueSend(void*q,void*a,int t){assert(q);return queued<16?++queued,1:0;}
esp_err_t mdns_free_wait(void);
"""+fn('mdns_init')+fn('mdns_free_wait')+fn('mdns_priv_queue_action')+r"""
int main(void){
 for(fail=1;fail<=4;fail++){
  assert(mdns_init()!=0);assert(!server&&!s_action_queue&&!s_stack_buffer&&!s_service_semaphore);
 }
 fail=0;assert(mdns_init()==0);mdns_action_t a={0};
 for(int i=0;i<16;i++)assert(mdns_priv_queue_action(&a));
 assert(!mdns_priv_queue_action(&a));
 stop_timeout=1;assert(mdns_free_wait()==ESP_ERR_TIMEOUT);
 assert(server&&s_action_queue&&s_stack_buffer&&s_service_semaphore);
 assert(mdns_init()==ESP_ERR_INVALID_STATE);assert(!mdns_priv_queue_action(&a));
 stop_timeout=0;assert(mdns_free_wait()==0);assert(freed==16);
 assert(!server&&!s_action_queue&&!s_stack_buffer&&!s_service_semaphore);
 assert(!mdns_priv_queue_action(&a));assert(mdns_free_wait()==0);
 assert(mdns_init()==0);assert(mdns_free_wait()==0);
 puts("PASS mDNS production partial init, full queue, late admission, timeout retention, reentry, drain");
}
"""
p=d/'lifetime.c';p.write_text(extra);exe=d/'lifetime'
subprocess.run(['cc','-std=c11','-g','-fsanitize=address,undefined','-no-pie',str(p),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
