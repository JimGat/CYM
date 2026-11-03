#!/usr/bin/env python3
"""Production-extracted emitter call-boundaries and checked-stop faults; synthetic SDK, no RF proof."""
from pathlib import Path
import os,re,json,subprocess,hashlib
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'hat-emitters';D.mkdir(parents=True,exist_ok=True)
C=R/'ESP32C5/components';core=C/'rf_hat/src/hat_tx.c';results=[]
def extract(s,n):
 m=re.search(r'^(?:static )?(?:void|bool|uint8_t|esp_err_t|ir_hat_err_t|rf433_hat_err_t) '+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
pre=r"""
#include <assert.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "hat_tx.h"
typedef int esp_err_t;typedef unsigned TickType_t;
#define ESP_OK 0
#define ESP_FAIL 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_TIMEOUT 3
#define ESP_ERR_NO_MEM 4
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
"""
def run(name,s,post,mutant=False):
 d=D/name;d.mkdir(exist_ok=True);(d/'host.c').write_text(pre+s+post)
 cmd=['cc','-std=gnu11','-O1','-g','-DHAT_TX_HOST','-pthread','-Werror=implicit-function-declaration','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I'+str(C/'rf_hat/include'),str(core),str(d/'host.c'),'-o',str(d/'host')]
 c=subprocess.run(cmd,capture_output=True,text=True);(d/'compile.log').write_text(c.stdout+c.stderr);assert c.returncode==0,c.stderr
 c=subprocess.run([str(d/'host')],capture_output=True,text=True,timeout=20);(d/'run.log').write_text(c.stdout+c.stderr)
 ok=c.returncode!=0 and 'Assertion' in c.stderr if mutant else c.returncode==0
 results.append(dict(name=name,ok=ok,exit_code=c.returncode,mutant=mutant));print(name,ok,c.stdout.strip());assert ok,c.stderr
ir=(C/'rf_hat/src/ir_hat.c').read_text()
irpre=r"""
#define IR_HAT_MAX_TIMINGS 1024
#define IR_CARRIER_HZ 38000
#define IR_CARRIER_DUTY 0.33f
#define LEDC_LOW_SPEED_MODE 0
#define IR_JAM_LEDC_CHANNEL 1
typedef enum{IR_HAT_OK,IR_HAT_ERR_NOT_INIT,IR_HAT_ERR_HW,IR_HAT_ERR_BUSY}ir_hat_err_t;
typedef struct{uint32_t count,freq_hz;float duty_cycle;uint32_t times_us[1024];}ir_signal_t;
typedef struct{unsigned duration0,level0,duration1,level1;}rmt_symbol_word_t;
typedef struct{unsigned frequency_hz;float duty_cycle;}rmt_carrier_config_t;
typedef struct{int loop_count;struct{bool queue_nonblocking;int eot_level;}flags;}rmt_transmit_config_t;
static bool s_init=true,s_tx_enabled=true,s_jamming,s_jam_configured;
static void*s_tx_chan=(void*)1,*s_tx_enc=(void*)2;
static rmt_symbol_word_t*s_tx_payload,*borrowed;
static int allocs,frees,requests,wait_fail,tx_fail,carrier_fail,ledc_fail,cancel_on_tx,cancel_carrier,alloc_fail;
static void*heap_caps_calloc(size_t n,size_t z,int caps){assert(caps==3);if(alloc_fail)return NULL;allocs++;return calloc(n,z);}
static void release(void*p){assert(p);frees++;if(p==borrowed){assert(!wait_fail);borrowed=NULL;}free(p);}
#define free release
static int ledc_stop(int m,int c,int level){assert(!level);return ledc_fail;}
static int rmt_apply_carrier(void*c,void*conf){assert(c==s_tx_chan);if(cancel_carrier)hat_tx_inhibit(true);return carrier_fail;}
static int rmt_transmit(void*c,void*enc,const void*data,size_t n,const rmt_transmit_config_t*cfg){requests++;assert(cfg->flags.queue_nonblocking&&cfg->flags.eot_level==0);if(tx_fail)return tx_fail;borrowed=(void*)data;assert(borrowed->duration0==100&&borrowed->level0==1);assert(borrowed->duration1==200&&borrowed->level1==0);assert(borrowed[1].duration0==300&&borrowed[1].duration1==0);if(cancel_on_tx)hat_tx_inhibit(true);return 0;}
static int rmt_tx_wait_all_done(void*c,int ms){assert(ms==2100||ms==0);assert(borrowed==s_tx_payload);return wait_fail;}
"""
ircode=irpre+'\n'.join(extract(ir,n)for n in ['ir_hat_tx_stop_checked','ir_hat_replay_owned','ir_hat_replay'])
irpost=r"""
int main(void){ir_signal_t s={.count=3,.freq_hz=38000,.duty_cycle=.33f,.times_us={100,200,300}};
 assert(ir_hat_replay(&s)==IR_HAT_OK&&requests==1&&allocs==frees&&!hat_tx_owned(HAT_TX_IR));
 hat_tx_inhibit(true);assert(ir_hat_replay(&s)==IR_HAT_ERR_BUSY&&requests==1);hat_tx_inhibit(false);
 cancel_carrier=1;assert(ir_hat_replay(&s)==IR_HAT_ERR_BUSY&&requests==1&&allocs==frees);cancel_carrier=0;hat_tx_inhibit(false);
 cancel_on_tx=1;assert(ir_hat_replay(&s)==IR_HAT_ERR_BUSY&&requests==2&&!borrowed);cancel_on_tx=0;hat_tx_inhibit(false);
 wait_fail=ESP_ERR_TIMEOUT;assert(ir_hat_replay(&s)==IR_HAT_ERR_HW&&borrowed&&s_tx_payload&&hat_tx_owned(HAT_TX_IR));
 assert(hat_tx_snapshot().state[HAT_TX_IR]==HAT_TX_ERROR);assert(ir_hat_tx_stop_checked()==ESP_ERR_TIMEOUT&&borrowed);
 hat_tx_inhibit(true);hat_tx_inhibit(false);assert(ir_hat_replay(&s)==IR_HAT_ERR_BUSY);
 wait_fail=0;hat_tx_ticket_t t;assert(hat_tx_claim_stop(HAT_TX_IR,&t));assert(ir_hat_tx_stop_checked()==0&&!borrowed);hat_tx_finish(t,true);
 tx_fail=1;assert(ir_hat_replay(&s)==IR_HAT_ERR_HW&&!borrowed&&allocs==frees);tx_fail=0;
 alloc_fail=1;int n=requests;assert(ir_hat_replay(&s)==IR_HAT_ERR_HW&&requests==n);alloc_fail=0;
 s.times_us[0]=32768;assert(ir_hat_replay(&s)==IR_HAT_ERR_HW&&requests==n);s.times_us[0]=100;
 assert(hat_tx_begin(HAT_TX_IR,&t));s_jamming=s_jam_configured=true;ledc_fail=1;hat_tx_cancel(HAT_TX_IR);
 assert(ir_hat_tx_stop_checked()!=0&&s_jamming&&s_jam_configured&&hat_tx_owned(HAT_TX_IR));ledc_fail=0;assert(ir_hat_tx_stop_checked()==0&&!s_jamming);hat_tx_finish(t,true);
 assert(allocs==frees);puts("PASS IR actual RMT request, exact normal symbols, pre-request inhibit, admitted frame drain, checked completion retention/error/retry, LEDC stop error");}
"""
run('ir-rmt',ircode,irpost)
run('ir-premature-free',ircode.replace('if (e!=ESP_OK) return IR_HAT_ERR_HW; // payload/channel retained for checked retry','if (false) return IR_HAT_ERR_HW; // mutant'),irpost,True)
cc=(C/'cc1101/src/cc1101.c').read_text()
ccpre=r"""
#define CC1101_STX 0x35
#define CC1101_SIDLE 0x36
#define CC1101_MARCSTATE 0x35
#define CC1101_READ 0x80
#define CC1101_BURST 0x40
#define CC1101_STATE_IDLE 1
#define RF_HAT_CC1101_GDO0_GPIO 8
static bool s_tx_session;static hat_tx_ticket_t s_tx_ticket;static void*s_spi=(void*)1;
static int requests,rx,fail,state=1,low_fail,delays;
static uint8_t s_strobe_raw(uint8_t s){if(s==CC1101_STX)requests++;else rx++;return 0;}
static int s_checked_xfer(uint8_t a,uint8_t*v,bool read){if(fail)return fail;if(read)*v=state;else if(a==CC1101_STX)requests++;return 0;}
static int gpio_set_level(int p,int v){assert(!v);return low_fail;}
static void vTaskDelay(int t){delays+=t;}
"""
cccode=ccpre+'\n'.join(extract(cc,n)for n in ['cc1101_strobe','cc1101_tx_stop_checked'])
ccpost=r"""
int main(void){hat_tx_ticket_t t;hat_tx_inhibit(true);assert(cc1101_strobe(CC1101_STX)==255&&!requests);cc1101_strobe(0x34);assert(rx==1);hat_tx_inhibit(false);
 cc1101_strobe(CC1101_STX);assert(requests==1&&hat_tx_owned(HAT_TX_CC1101));hat_tx_inhibit(true);hat_tx_inhibit(false);assert(cc1101_strobe(CC1101_STX)==255&&requests==1);
 assert(hat_tx_claim_stop(HAT_TX_CC1101,&t));fail=7;assert(cc1101_tx_stop_checked()==7);hat_tx_finish(t,false);assert(hat_tx_owned(HAT_TX_CC1101));
 fail=0;state=2;assert(cc1101_tx_stop_checked()==ESP_ERR_TIMEOUT&&delays==50);state=1;low_fail=1;assert(cc1101_tx_stop_checked()!=0&&s_tx_session);
 low_fail=0;assert(cc1101_tx_stop_checked()==0&&!s_tx_session);assert(hat_tx_claim_stop(HAT_TX_CC1101,&t));hat_tx_finish(t,true);
 cc1101_strobe(CC1101_STX);assert(requests==2);hat_tx_cancel(HAT_TX_CC1101);assert(hat_tx_claim_stop(HAT_TX_CC1101,&t));assert(cc1101_tx_stop_checked()==0);hat_tx_finish(t,true);
 puts("PASS CC actual STX boundary vs receive strobe, cancelled generation cannot rearm, SPI/IDLE/low faults retain session, fresh restart");}
"""
run('cc-stx',cccode,ccpost)
run('cc-bypass-admission',cccode.replace('if (!hat_tx_begin(HAT_TX_CC1101,&s_tx_ticket)) return 0xFF;','if(false)return 0xFF;'),ccpost,True)
nrf=(C/'nrf24/src/nrf24.c').read_text()
npre=r"""
#define RF_HAT_NRF24_CE_GPIO 8
#define RF_HAT_NRF24_CS_GPIO 9
#define CMD_W_REG 0x20
#define CMD_R_REG 0
#define REG_CONFIG 0
#define CONFIG_EN_CRC 8
#define CONFIG_CRCO 4
#define CONFIG_PWR_UP 2
#define CMD_NOP 255
#define REG_EN_AA 1
#define REG_SETUP_RETR 2
#define REG_RF_CH 3
#define REG_RF_SETUP 4
#define RF_SETUP_CONT_WAVE 128
#define RF_SETUP_PLL_LOCK 16
#define RF_SETUP_PWR(x) (x)
typedef struct{int length;const void*tx_buffer;void*rx_buffer;}spi_transaction_t;
static struct{void*spi;}drv;static void*sd_spi_mutex=(void*)1;static typeof(drv)*s_drv=&drv;
static int ce,cs,fail,gpio_fail,read_bad,requests,reg_config,reg_setup,ce_get_bad;static bool s_jam_fhss;
static int xSemaphoreTake(void*m,int wait){return fail==9?0:1;}static void xSemaphoreGive(void*m){}
static int gpio_set_level(int p,int v){if(p==8)ce=v;else cs=v;return gpio_fail;}
static int gpio_get_level(int p){return ce_get_bad?1:ce;}
static int spi_device_polling_transmit(void*d,spi_transaction_t*t){if(fail)return fail;uint8_t*tx=(void*)t->tx_buffer,*rx=t->rx_buffer;if(tx[0]==CMD_W_REG)reg_config=tx[1];else rx[1]=read_bad?2:reg_config;return 0;}
static void ce_low(void){ce=0;}static void ce_high(void){ce=1;requests++;if(requests==3)hat_tx_inhibit(true);}
static void nrf24_write_reg(int reg,int v){if(reg==REG_CONFIG)reg_config=v;if(reg==REG_RF_SETUP)reg_setup=v;}
static void esp_rom_delay_us(int us){assert(us==500);}static unsigned esp_random(void){return 0;}static void vTaskDelay(int ms){}
"""
ncode=npre+'\n'.join(extract(nrf,n)for n in ['nrf24_tx_stop_checked','s_contwave_jam'])
npost=r"""
int main(void){hat_tx_ticket_t t;assert(hat_tx_begin(HAT_TX_NRF24,&t)&&hat_tx_enter(t));uint8_t ch[]={1,2,3};volatile bool active=true;
 s_contwave_jam(&active,ch,3,t);assert(requests==3&&!active&&!ce&&!(reg_config&CONFIG_PWR_UP)&&!(reg_setup&RF_SETUP_CONT_WAVE));
 fail=7;assert(nrf24_tx_stop_checked()==7);hat_tx_leave(t);hat_tx_finish(t,false);assert(hat_tx_snapshot().state[HAT_TX_NRF24]==HAT_TX_ERROR);
 fail=0;read_bad=1;assert(nrf24_tx_stop_checked()!=0);read_bad=0;gpio_fail=1;assert(nrf24_tx_stop_checked()!=0);gpio_fail=0;ce_get_bad=1;assert(nrf24_tx_stop_checked()!=0);ce_get_bad=0;
 assert(nrf24_tx_stop_checked()==0);assert(hat_tx_claim_stop(HAT_TX_NRF24,&t));hat_tx_finish(t,true);hat_tx_inhibit(false);int n=requests;
 assert(hat_tx_begin(HAT_TX_NRF24,&t)&&hat_tx_enter(t));hat_tx_cancel(HAT_TX_NRF24);active=true;s_contwave_jam(&active,ch,3,t);assert(requests==n&&!active);hat_tx_leave(t);hat_tx_finish(t,true);
 puts("PASS nRF actual CE requests, cancel before delayed task, verified CE low and PWR_UP cleared vs standby, SPI/GPIO/readback faults");}
"""
run('nrf-ce',ncode,npost)
run('nrf-no-readback',ncode.replace('rx[1]!=(CONFIG_EN_CRC|CONFIG_CRCO)','false'),npost,True)

main=(R/'ESP32C5/main/main.c').read_text()
diagpre=r"""
#define RF_HAT_RF433_TX_GPIO 8
#define RF_HAT_RF433_RX_GPIO 9
#define GPIO_MODE_OUTPUT 1
#define GPIO_MODE_INPUT 0
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLUP_ENABLE 1
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_DISABLE 0
#define GPIO_INTR_ANYEDGE 1
#define LV_OBJ_FLAG_HIDDEN 1
#define ESP_LOGI(...) ((void)0)
typedef int gpio_num_t;
typedef struct{uint64_t pin_bit_mask;int mode,pull_up_en,pull_down_en,intr_type;}gpio_config_t;
static hat_tx_ticket_t s_lbk_ticket;static void*s_lbk_task;static bool s_lbk_isr_owned;
static int s_lbk_edges,highs,waits,cancel_wait,remove_fail,setup_fail,labels,inits;static uint32_t s_hat_ui_epoch=1;
static void*lvgl_mutex=(void*)1,*s_lbk_status_lbl=(void*)1,*s_lbk_result_lbl=(void*)1,*s_lbk_retry_btn=(void*)1;
static int gpio_config(void*c){return setup_fail;}
static int gpio_set_level(int p,int v){if(v)highs++;return 0;}
static int gpio_install_isr_service(int f){return 0;}
static void s_lbk_edge_isr(void*a){}
static int gpio_isr_handler_add(int pin,void(*f)(void*),void*a){return 0;}
static int gpio_isr_handler_remove(int pin){return remove_fail;}
static unsigned ulTaskNotifyTake(int clear,unsigned ms){waits++;if(waits==cancel_wait)hat_tx_inhibit(true);return 0;}
static int xSemaphoreTake(void*m,unsigned ms){return pdTRUE;}static void xSemaphoreGive(void*m){}
static bool lv_obj_is_valid(void*p){return true;}static void lv_label_set_text(void*p,const char*t){labels++;}
static void lv_label_set_recolor(void*p,bool e){}static void lv_obj_clear_flag(void*p,int f){}
static void rf433_hat_init(void){inits++;}static void vTaskDelete(void*t){}
"""
diagcode=diagpre+'\n'.join(extract(main,n)for n in ['hat_rf433_diag_stop_checked','rf433_lbk_task'])
diagpost=r"""
static void start(void){assert(hat_tx_begin(HAT_TX_RF433,&s_lbk_ticket)&&hat_tx_enter(s_lbk_ticket));waits=0;s_lbk_task=(void*)1;}
int main(void){start();rf433_lbk_task((void*)1);assert(highs==1&&!hat_tx_owned(HAT_TX_RF433)&&!s_lbk_isr_owned&&!s_lbk_task);
 start();hat_tx_cancel(HAT_TX_RF433);int n=highs;rf433_lbk_task((void*)1);assert(highs==n&&!hat_tx_owned(HAT_TX_RF433));
 start();cancel_wait=1;rf433_lbk_task((void*)1);assert(highs==n&&!hat_tx_owned(HAT_TX_RF433));hat_tx_inhibit(false);cancel_wait=0;
 start();remove_fail=7;rf433_lbk_task((void*)1);assert(s_lbk_isr_owned&&hat_tx_snapshot().state[3]==HAT_TX_ERROR);hat_tx_ticket_t t;assert(hat_tx_claim_stop(HAT_TX_RF433,&t));assert(hat_rf433_diag_stop_checked()==7);hat_tx_finish(t,false);remove_fail=0;assert(hat_tx_claim_stop(HAT_TX_RF433,&t));assert(hat_rf433_diag_stop_checked()==0);hat_tx_finish(t,true);
 start();setup_fail=1;n=highs;rf433_lbk_task((void*)1);assert(highs==n&&!hat_tx_owned(HAT_TX_RF433));setup_fail=0;
 start();n=labels;s_hat_ui_epoch++;rf433_lbk_task((void*)1);assert(labels==n&&!hat_tx_owned(HAT_TX_RF433));
 puts("PASS actual raw GPIO diagnostic admission, late start/cancel before high, checked setup and ISR ownership/error retry, stale UI epoch");}
"""
run('raw-gpio-diagnostic',diagcode,diagpost)
rf=(C/'rf_hat/src/rf433_hat.c').read_text()
rfpre=r"""
#define RF_HAT_RF433_TX_GPIO 8
#define portENTER_CRITICAL(p) ((void)0)
#define portEXIT_CRITICAL(p) ((void)0)
#define RF433_HAT_OK 0
#define RF433_HAT_ERR_BUSY 1
#define RF433_HAT_ERR_HW 2
typedef int rf433_hat_err_t;typedef struct{void(*callback)(void*);const char*name;}esp_timer_create_args_t;
static bool s_jamming,s_jam_gpio_state,timer_active;static void*s_jam_tmr;static hat_tx_ticket_t s_jam_ticket;static int s_jam_mux,highs,gpio_fail,stop_fail;
static void *s_cap_task;static bool s_cap_cancel;
static void s_setup_tx(void){}
static int gpio_set_level(int pin,int v){if(v)highs++;return gpio_fail;}
static int esp_timer_create(const esp_timer_create_args_t*c,void**p){*p=(void*)1;return 0;}
static int esp_timer_start_periodic(void*t,unsigned us){assert(us==500);timer_active=true;return 0;}
static bool esp_timer_is_active(void*t){return timer_active;}
static int esp_timer_stop(void*t){if(stop_fail)return stop_fail;timer_active=false;return 0;}
"""
rfcode=rfpre+'\n'.join(extract(rf,n)for n in ['s_jam_timer_cb','rf433_hat_jam_start','rf433_hat_tx_stop_checked'])
rfpost=r"""
int main(void){s_cap_task=(void*)1;assert(rf433_hat_jam_start()==RF433_HAT_ERR_BUSY && !highs && !hat_tx_owned(HAT_TX_RF433));assert(s_cap_cancel);s_cap_task=NULL;assert(rf433_hat_jam_start()==0&&highs==1);s_jam_timer_cb(NULL);hat_tx_inhibit(true);int n=highs;s_jam_timer_cb(NULL);assert(highs==n);hat_tx_inhibit(false);s_jam_timer_cb(NULL);assert(highs==n);hat_tx_ticket_t t;assert(hat_tx_claim_stop(HAT_TX_RF433,&t));stop_fail=7;assert(rf433_hat_tx_stop_checked()==7);hat_tx_finish(t,false);assert(hat_tx_owned(HAT_TX_RF433));stop_fail=0;gpio_fail=1;assert(rf433_hat_tx_stop_checked()!=0);gpio_fail=0;assert(hat_tx_claim_stop(HAT_TX_RF433,&t));assert(rf433_hat_tx_stop_checked()==0);hat_tx_finish(t,true);assert(!timer_active);
 assert(rf433_hat_jam_start()==0);gpio_fail=1;s_jam_timer_cb(NULL);assert(hat_tx_snapshot().state[3]==HAT_TX_ERROR);gpio_fail=0;assert(hat_tx_claim_stop(HAT_TX_RF433,&t));assert(rf433_hat_tx_stop_checked()==0);hat_tx_finish(t,true);
 puts("PASS RF433 actual timer GPIO boundary, sticky cancelled generation, callback GPIO error, checked timer/low stop retention and retry; no callback self-join");}
"""
run('rf-timer',rfcode,rfpost)

(D/'results.json').write_text(json.dumps({'results':results,'core_sha256':hashlib.sha256(core.read_bytes()).hexdigest(),'classification':'production extracted, ASAN/UBSAN + faulted SDK; no hardware qualification'},indent=2))
