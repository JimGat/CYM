#!/usr/bin/env python3
"""Execute real replay mailbox/control/epoch functions with synthetic RTOS and labels, ASAN/UBSAN."""
from pathlib import Path
import os,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'hat-runtime';D.mkdir(parents=True,exist_ok=True)
S=(R/'ESP32C5/main/hat_tx_runtime.inc').read_text()
pre=r"""
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdio.h>
#include <setjmp.h>
#include "hat_tx.h"
typedef int esp_err_t;typedef void*TaskHandle_t;typedef int portMUX_TYPE;
typedef struct{char text[100];bool alive;}lv_obj_t;typedef int lv_timer_t;typedef struct{lv_obj_t*obj;}lv_event_t;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)0)
#define portEXIT_CRITICAL(p) ((void)0)
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY 0xffffffff
#define ESP_OK 0
#define ESP_FAIL -1
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
#define IR_HAT_OK 0
#define RF433_HAT_OK 0
#define LV_OBJ_FLAG_CLICKABLE 1
#define LV_EVENT_CLICKED 2
#define LV_EVENT_DELETE 3
#define LV_EVENT_SHORT_CLICKED 4
#define LV_EVENT_LONG_PRESSED 5
static int lv_font_montserrat_12;
static void screenshot_btn_event_cb(lv_event_t*e){}
static void lv_obj_remove_event_cb(lv_obj_t*p,void(*f)(lv_event_t*)){}
static bool s_hat_retry,retry_during_stop;
static int stops[4],stop_error[4],emissions,cancels,callback_result=-1,created;static size_t memory=50000;
static jmp_buf escape;static int waits;
static unsigned ulTaskNotifyTake(int clear,unsigned ms){if(waits++)longjmp(escape,1);return 1;}
static void xTaskNotifyGive(void*t){}
static int xTaskCreate(void(*f)(void*),const char*n,int bytes,void*a,int p,void**t){assert(bytes==4096);created++;*t=(void*)1;return pdPASS;}
static void*heap_caps_calloc(size_t n,size_t z,int caps){assert(caps==3);return calloc(n,z);}
static size_t heap_caps_get_free_size(int caps){assert(caps==3);return memory;}
static size_t heap_caps_get_largest_free_block(int caps){return memory;}
static lv_timer_t*xTimer;static lv_timer_t*lv_timer_create(void(*f)(lv_timer_t*),int ms,void*a){assert(ms==50);return (void*)1;}
static void lv_label_set_text(lv_obj_t*p,const char*s){assert(p&&p->alive);snprintf(p->text,sizeof(p->text),"%s",s);}
static void lv_obj_add_flag(lv_obj_t*p,int f){}static void lv_obj_add_event_cb(lv_obj_t*p,void(*f)(lv_event_t*),int e,void*a){}
static void lv_obj_set_style_text_letter_space(lv_obj_t*p,int n,int s){}
static void lv_obj_set_style_text_font(lv_obj_t*p,void*f,int s){}static lv_obj_t*lv_event_get_target(lv_event_t*e){return e->obj;}
static int stop(int i){stops[i]++;if(retry_during_stop){retry_during_stop=false;__atomic_store_n(&s_hat_retry,true,__ATOMIC_RELEASE);}return stop_error[i];}
static int cc1101_tx_stop_checked(void){return stop(0);}static int nrf24_tx_stop_checked(void){return stop(1);}
static int ir_hat_tx_stop_checked(void){return stop(2);}static int rf433_hat_tx_stop_checked(void){return stop(3);}
static int ir_hat_replay_owned(void*s,hat_tx_ticket_t t){assert(*(int*)s==123);if(!hat_tx_valid(t))return 1;emissions++;return stop_error[2]?1:0;}
static int rf433_hat_replay_owned(void*s,int n,hat_tx_ticket_t t){assert(n==3);return ir_hat_replay_owned(s,t);}
"""
post=r"""
static int hat_rf433_diag_stop_checked(void){return 0;}
static void hat_cancel_producers(void){cancels++;}
static void done(bool ok){callback_result=ok;}
static void work(void){waits=0;if(!setjmp(escape))hat_worker(NULL);}
int main(void){lv_obj_t label={.alive=true},title={.alive=true};int sig=123;
 memory=100;assert(!hat_submit(HAT_TX_IR,&sig,sizeof(sig),&label,done)&&!created&&!hat_tx_owned(HAT_TX_IR));memory=50000;
 hat_control_attach(&title);assert(strstr(title.text,"ALLOWED"));
 assert(hat_submit(HAT_TX_IR,&sig,sizeof(sig),&label,done));sig=456;assert(!hat_submit(HAT_TX_IR,&sig,sizeof(sig),&label,done));
 work();assert(emissions==1&&s_hat_job->done);int old=stops[2];work();assert(stops[2]==old&&emissions==1);hat_ui_poll(NULL);assert(!s_hat_job&&callback_result==1&&strstr(label.text,"Sent"));
 sig=123;assert(hat_submit(HAT_TX_IR,&sig,sizeof(sig),&label,done));callback_result=-1;hat_ui_depart();label.alive=false;work();hat_ui_poll(NULL);assert(emissions==1&&callback_result==-1&&!s_hat_job);
 label.alive=true;stop_error[2]=1;assert(hat_submit(HAT_TX_IR,&sig,sizeof(sig),&label,done));work();old=stops[2];hat_ui_poll(NULL);assert(callback_result==0&&strstr(label.text,"failed"));work();assert(stops[2]==old);assert(hat_tx_owned(HAT_TX_IR));
 hat_control_attach(&title);assert(strstr(title.text,"ERROR"));stop_error[2]=0;hat_control_clicked(NULL);work();hat_ui_poll(NULL);assert(!hat_tx_owned(HAT_TX_IR)&&strstr(title.text,"ALLOWED"));
 hat_tx_ticket_t a,b;assert(hat_tx_begin(HAT_TX_CC1101,&a));assert(hat_tx_begin(HAT_TX_NRF24,&b)&&hat_tx_enter(b));hat_control_clicked(NULL);hat_ui_poll(NULL);assert(strstr(title.text,"STOPPING"));work();assert(!hat_tx_owned(HAT_TX_CC1101)&&hat_tx_owned(HAT_TX_NRF24));
 assert(!hat_tx_enter(b));hat_tx_leave(b);work();hat_ui_poll(NULL);assert(strstr(title.text,"STOPPED"));old=emissions;hat_control_clicked(NULL);work();assert(emissions==old&&!hat_tx_snapshot().inhibit);assert(!hat_tx_valid(b));
 for(int i=0;i<100;i++){hat_control_clicked(NULL);work();hat_control_clicked(NULL);work();}assert(emissions==old&&created==1);
 hat_tx_ticket_t retry_ticket;assert(hat_tx_begin(HAT_TX_IR,&retry_ticket));hat_tx_cancel(HAT_TX_IR);stop_error[2]=1;retry_during_stop=true;__atomic_store_n(&s_hat_retry,true,__ATOMIC_RELEASE);work();assert(s_hat_retry&&"retry arriving during checked stop must survive for next service wake");stop_error[2]=0;work();assert(!hat_tx_owned(HAT_TX_IR));
 puts("PASS actual runtime mailbox copy/completion, worker wake after completion, error retention/manual retry, mixed STOPPING/STOPPED, memory rejection, epoch departure and no automatic restart");}
"""
(D/'host.c').write_text(pre+S+post);cmd=['cc','-std=gnu11','-O1','-g','-DHAT_TX_HOST','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I'+str(R/'ESP32C5/components/rf_hat/include'),str(R/'ESP32C5/components/rf_hat/src/hat_tx.c'),str(D/'host.c'),'-o',str(D/'host')]
c=subprocess.run(cmd,capture_output=True,text=True);(D/'compile.log').write_text(c.stdout+c.stderr);assert not c.returncode,c.stderr
c=subprocess.run([str(D/'host')],capture_output=True,text=True);(D/'run.log').write_text(c.stdout+c.stderr);print(c.stdout+c.stderr);(D/'results.json').write_text(json.dumps({'exit_code':c.returncode,'runtime_sha256':hashlib.sha256(S.encode()).hexdigest(),'classification':'production-extracted synthetic RTOS/labels, not hardware'},indent=2));assert not c.returncode
