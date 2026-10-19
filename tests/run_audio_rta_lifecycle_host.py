#!/usr/bin/env python3
"""Actual production session/DSP; synthetic RTOS/hardware fault boundary, ASan/UBSan."""
from pathlib import Path
import subprocess,os
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'rta-lifecycle';D.mkdir(parents=True,exist_ok=True)
from audio_rta_nvs_stubs import write_nvs_stub
write_nvs_stub(D)
(D/'esp_err.h').write_text('typedef int esp_err_t;\n#define ESP_OK 0\n#define ESP_FAIL -1\n#define ESP_ERR_NO_MEM 1\n#define ESP_ERR_INVALID_ARG 2\n#define ESP_ERR_INVALID_STATE 3\n#define ESP_ERR_TIMEOUT 4\n')
(D/'audio_rta_host_port.h').write_text(r"""
#include <pthread.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdatomic.h>
#include <assert.h>
#include <stdio.h>
#include <time.h>
#include <stdbool.h>
#include <string.h>
#include <stdarg.h>
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_SPIRAM 2
#define MALLOC_CAP_DMA 8
#define MALLOC_CAP_8BIT 4
static bool cym_debug_enabled(void){return false;}
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
#define portMUX_TYPE pthread_mutex_t
#define portMUX_INITIALIZER_UNLOCKED PTHREAD_MUTEX_INITIALIZER
#define portENTER_CRITICAL(m) pthread_mutex_lock(m)
#define portEXIT_CRITICAL(m) pthread_mutex_unlock(m)
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY 0xffffffffu
#define pdMS_TO_TICKS(n) (n)
#define eSuspended 2
typedef struct task {pthread_t id;pthread_mutex_t mu;pthread_cond_t cv;unsigned notify;int suspended,quit;void(*fn)(void*);void*arg;} *TaskHandle_t;
static _Thread_local TaskHandle_t self;
static atomic_int task_stack_bytes;
static atomic_int allow_kernel_reap=1,self_delete_waiting;
static void (*after_free_hook)(void*);
static atomic_int live_tasks,alloc_call,fail_alloc,task_call,fail_task,live_alloc;
static void*heap_caps_calloc(size_t n,size_t z,int caps){assert(caps==5||caps==6);int k=atomic_fetch_add(&alloc_call,1)+1;if(k==fail_alloc)return NULL;void*p=calloc(n,z);if(p)live_alloc++;return p;}
static void*heap_caps_malloc(size_t z,int caps){return heap_caps_calloc(1,z,caps);}
static void heap_caps_free(void*p){if(p){live_alloc--;free(p);if(after_free_hook)after_free_hook(p);}}
static size_t heap_caps_get_free_size(int caps){(void)caps;return 100000;}
static size_t heap_caps_get_largest_free_block(int caps){(void)caps;return 50000;}
static int64_t esp_timer_get_time(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (int64_t)t.tv_sec*1000000+t.tv_nsec/1000;}
static void taskfree(TaskHandle_t t){pthread_mutex_destroy(&t->mu);pthread_cond_destroy(&t->cv);free(t);live_tasks--;}
static void*trampoline(void*p){self=p;self->fn(self->arg);abort();}
static int xTaskCreate(void(*fn)(void*),const char*n,unsigned stack,void*arg,unsigned prio,TaskHandle_t*out){(void)n;(void)prio;assert(stack==6144||stack==3072);task_stack_bytes+=stack;int k=atomic_fetch_add(&task_call,1)+1;if(k==fail_task)return 0;TaskHandle_t t=calloc(1,sizeof(*t));assert(t);pthread_mutex_init(&t->mu,NULL);pthread_cond_init(&t->cv,NULL);t->fn=fn;t->arg=arg;live_tasks++;*out=t;assert(!pthread_create(&t->id,NULL,trampoline,t));return pdPASS;}
static void xTaskNotifyGive(TaskHandle_t t){pthread_mutex_lock(&t->mu);t->notify++;pthread_cond_signal(&t->cv);pthread_mutex_unlock(&t->mu);}
static unsigned ulTaskNotifyTake(int clear,unsigned timeout){(void)clear;(void)timeout;pthread_mutex_lock(&self->mu);while(!self->notify)pthread_cond_wait(&self->cv,&self->mu);unsigned n=self->notify;self->notify=0;pthread_mutex_unlock(&self->mu);return n;}
static void vTaskDelay(unsigned n){usleep(n*1000);}
static void vTaskSuspend(void*x){(void)x;pthread_mutex_lock(&self->mu);self->suspended=1;while(!self->quit)pthread_cond_wait(&self->cv,&self->mu);pthread_mutex_unlock(&self->mu);pthread_exit(NULL);}
static int eTaskGetState(TaskHandle_t t){pthread_mutex_lock(&t->mu);int v=t->suspended?eSuspended:0;pthread_mutex_unlock(&t->mu);return v;}
static void vTaskDelete(TaskHandle_t t){if(!t){TaskHandle_t q=self;self_delete_waiting++;while(!allow_kernel_reap)usleep(1000);self_delete_waiting--;pthread_detach(pthread_self());taskfree(q);pthread_exit(NULL);}assert(eTaskGetState(t)==eSuspended);pthread_mutex_lock(&t->mu);t->quit=1;pthread_cond_signal(&t->cv);pthread_mutex_unlock(&t->mu);pthread_join(t->id,NULL);taskfree(t);}
""")
(D/'host.c').write_text(r"""
#define AUDIO_RTA_HOST 1
#include "audio_rta.c"
#include <math.h>
struct audio_rta_board {int opened;};
static atomic_int open_fail,read_mode,gain_fail,delay_close,slow_start,close_calls;
size_t audio_rta_board_bytes(void){return sizeof(audio_rta_board_t);}
esp_err_t audio_rta_board_open(audio_rta_board_t*b,void*bus,int gain){assert(bus&&gain_valid(gain));if(slow_start)usleep(30000);if(open_fail||gain_fail)return ESP_FAIL;b->opened=1;return ESP_OK;}
esp_err_t audio_rta_board_gain(audio_rta_board_t*b,int gain){assert(b->opened&&gain>=0&&gain<=42);return gain_fail?ESP_FAIL:ESP_OK;}
esp_err_t audio_rta_board_read(audio_rta_board_t*b,int16_t*pcm,size_t cap,size_t*n,bool*discontinuity){*discontinuity=false;assert(b->opened&&cap==512);usleep(2000);int mode=atomic_exchange(&read_mode,0);*n=mode==1?127:512;for(unsigned i=0;i<*n;i++)pcm[i]=(int16_t)(10000*sin(2*3.141592653589793*i/48));if(mode==2){*discontinuity=true;return ESP_OK;}if(mode==3){*n=0;return ESP_ERR_TIMEOUT;}if(mode==4)return ESP_FAIL;return mode==1?ESP_ERR_TIMEOUT:ESP_OK;}
esp_err_t audio_rta_board_close(audio_rta_board_t*b){close_calls++;if(delay_close){delay_close--;return ESP_FAIL;}b->opened=0;return ESP_OK;}
static uint32_t start(void){uint32_t g;assert(!audio_rta_start((void*)1,&g));assert(task_stack_bytes==6144);return g;}
static void settle(void){for(int i=0;i<3000;i++){if(audio_rta_closed()&&!live_tasks){assert(!live_alloc);return;}usleep(1000);}assert(!"cleanup timeout");}
static audio_rta_snapshot_t snap(uint32_t g){audio_rta_snapshot_t s;assert(audio_rta_snapshot(g,&s));return s;}
static void wait_ready(uint32_t g){for(int i=0;i<3000;i++){if(snap(g).sequence>=16&&snap(g).spectrum.valid)return;usleep(1000);}assert(!"fresh frames timeout");}
static void reset(void){settle();task_stack_bytes=alloc_call=task_call=fail_alloc=fail_task=open_fail=read_mode=gain_fail=delay_close=slow_start=0;}
static void cleanup_callers(void*p){(void)p;audio_rta_stop(latest.generation);audio_rta_controls(latest.generation,true,true,6,true);}
int main(void){uint32_t g;
 for(int k=1;k<=4;k++){reset();fail_alloc=k;assert(audio_rta_start((void*)1,&g)==ESP_ERR_NO_MEM);settle();}
 for(int k=1;k<=1;k++){reset();fail_task=k;after_free_hook=cleanup_callers;assert(audio_rta_start((void*)1,&g)==ESP_ERR_NO_MEM);after_free_hook=NULL;settle();}
 reset();open_fail=1;g=start();settle();assert(snap(g).state==RTA_ERROR);
 reset();slow_start=1;g=start();audio_rta_stop(g);audio_rta_stop(g);settle();
 reset();g=start();wait_ready(g);audio_rta_snapshot_t a=snap(g);assert(a.sequence&&a.spectrum.valid);uint32_t other;assert(audio_rta_start((void*)1,&other)==ESP_ERR_INVALID_STATE);
 audio_rta_controls(g,true,false,0,false);usleep(20000);a=snap(g);assert(a.state==RTA_FROZEN);usleep(20000);audio_rta_snapshot_t b=snap(g);assert(!memcmp(&a.spectrum,&b.spectrum,sizeof(a.spectrum))&&a.sequence==b.sequence&&a.timestamp_us==b.timestamp_us);
 read_mode=2;usleep(10000);b=snap(g);assert(b.state==RTA_FROZEN&&b.overruns==1);
 assert(!memcmp(&a.spectrum,&b.spectrum,sizeof(a.spectrum)));
 audio_rta_controls(g,true,false,6,false);usleep(20000);b=snap(g);assert(b.state==RTA_FROZEN && "gain must preserve Freeze intent");assert(!memcmp(&a.spectrum,&b.spectrum,sizeof(a.spectrum)));
 audio_rta_controls(g,false,true,6,true);usleep(10000);b=snap(g);assert(b.gain_db==6&&b.spectrum.samples<a.spectrum.samples);
 read_mode=1;usleep(10000);assert(snap(g).state==RTA_RUNNING);
 read_mode=2;usleep(10000);assert(snap(g).overruns==2);
 delay_close=3;audio_rta_stop(g);usleep(10000);assert(!audio_rta_closed());assert(audio_rta_start((void*)1,&other)==ESP_ERR_INVALID_STATE);settle();
 uint32_t old=g;reset();g=start();assert(g!=old);assert(!audio_rta_snapshot(old,&a));audio_rta_stop(old);usleep(10000);assert(!audio_rta_closed());audio_rta_stop(g);settle();
 reset();g=start();usleep(10000);gain_fail=1;audio_rta_controls(g,false,false,12,false);settle();assert(snap(g).state==RTA_ERROR);
 for(int mode=3;mode<=4;mode++){reset();g=start();read_mode=mode;settle();assert(snap(g).state==RTA_ERROR);}
 /* Saved zero is loaded before codec startup; unchanged controls never write. */
 reset();nvs_present=1;nvs_value=0;int writes=nvs_sets;g=start();wait_ready(g);
 assert(snap(g).gain_db==0&&snap(g).persisted_gain_db==0);
 audio_rta_controls(g,false,false,0,false);usleep(10000);assert(nvs_sets==writes);
 /* No worker can observe intermediate requests while mux is held: latest wins. */
 portENTER_CRITICAL(&mux);owner->gain=6;owner->gain_selected=true;owner->gain=12;owner->gain=18;latest.requested_gain_db=18;portEXIT_CRITICAL(&mux);
 for(int i=0;i<1000&&snap(g).persisted_gain_db!=18;i++)usleep(1000);
 assert(snap(g).gain_db==18&&snap(g).persisted_gain_db==18&&nvs_sets==writes+1);
 nvs_commit_error=63;audio_rta_controls(g,false,false,24,false);usleep(20000);
 b=snap(g);assert(b.gain_db==24&&b.requested_gain_db==24&&b.persisted_gain_db==18&&b.gain_store_error==63&&b.gain_store_stage==RTA_STORE_COMMIT);
 writes=nvs_sets;audio_rta_controls(g,false,false,24,false);usleep(10000);assert(nvs_sets==writes&&"unchanged failed saves do not retry every refresh");
 nvs_commit_error=0;gain_fail=1;audio_rta_controls(g,false,false,30,false);settle();
 b=snap(g);assert(b.state==RTA_ERROR&&b.gain_db==24&&b.requested_gain_db==30&&b.persisted_gain_db==18&&nvs_sets==writes);
 reset();g=start();wait_ready(g);assert(snap(g).gain_db==18&&snap(g).persisted_gain_db==18);audio_rta_stop(g);settle();
 writes=nvs_sets;audio_rta_controls(g,false,false,42,false);assert(nvs_sets==writes);
 reset();slow_start=1;g=start();audio_rta_controls(g,true,false,42,false);audio_rta_stop(g);settle();assert(nvs_sets==writes&&"exit before processing must not persist a queued selection");
 for(int i=0;i<30;i++){reset();g=start();usleep(i%3*1000);audio_rta_stop(g);audio_rta_stop(g);settle();}
 reset();allow_kernel_reap=0;g=start();usleep(10000);audio_rta_stop(g);
 for(int i=0;i<2000 && (!audio_rta_closed() || !self_delete_waiting);i++)usleep(1000);
 assert(audio_rta_closed() && !live_alloc && live_tasks==1 && self_delete_waiting==1);
 old=g;task_stack_bytes=0;g=start();wait_ready(g);assert(g!=old && snap(g).sequence);
 allow_kernel_reap=1;for(int i=0;i<1000 && live_tasks!=1;i++)usleep(1000);
 assert(live_tasks==1 && !audio_rta_closed() && snap(g).state==RTA_RUNNING);
 audio_rta_stop(old);assert(!audio_rta_closed());audio_rta_stop(g);settle();
 printf("PASS production lifecycle: 4 allocation/1 task faults; one 6144-byte internal stack, init/gain/read faults, partial reads, overrun, startup/duplicate stop, freeze/resume, delayed cleanup/busy, stale generations, 30 cycles; allocations=%d tasks=%d\n",live_alloc,live_tasks);
 return 0;}
""")
cmd=['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-pthread','-I'+str(D),'-I'+str(R/'ESP32C5/main'),str(D/'host.c'),str(R/'ESP32C5/main/audio_rta_dsp.c'),'-lm','-o',str(D/'host')]
subprocess.run(cmd,check=True);subprocess.run([str(D/'host')],check=True)
