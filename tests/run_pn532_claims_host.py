#!/usr/bin/env python3
"""Shared-pin entry refusal through extracted real call-site functions."""
from pathlib import Path
import os,re,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];p=R/'ESP32C5/main/main.c';s=p.read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'pn532-claims';D.mkdir(parents=True,exist_ok=True)
names=['ir_hat_claim','rf433_hat_claim','cc1101_hat_claim','nrf24_hat_claim','rf433_lbk_run','rf433_rx_prepare']
def extract(name):
 m=re.search(r'static (?:bool|void|esp_err_t) '+name+r'\(void\)\s*\{',s);assert m,name
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
typedef int esp_err_t;
#define ESP_ERR_INVALID_STATE (-1)
#define ESP_OK 0
#define IR_HAT_OK 0
#define RF433_HAT_OK 0
static int ir_hat_init(void){return 0;}static int rf433_hat_init(void){return 0;}
#define HAT_TX_COUNT 4
#define HAT_TX_RF433 3
#define pdPASS 1
typedef int hat_tx_id_t;typedef int hat_tx_ticket_t;
static int s_lbk_task,s_hat_ui_epoch;static hat_tx_ticket_t s_lbk_ticket;
static bool hat_tx_owned(hat_tx_id_t id){return false;}
static void hat_cancel_all(void){}
static bool hat_tx_begin(int id,hat_tx_ticket_t*t){return true;}
static bool hat_tx_enter(hat_tx_ticket_t t){return true;}
static void hat_tx_leave(hat_tx_ticket_t t){}
static void hat_tx_finish(hat_tx_ticket_t t,bool s){}
#define ESP_LOGW(...) ((void)0)
static bool release_ok;static int hardware_calls,release_calls;
static bool rfid_manager_release(void){release_calls++;return release_ok;}
static bool nrf24_hat_ready(void){return true;}
static bool rf433_ook_quiesce(void){return true;}
static bool rf433_rx_owners_ready(void){return true;}
static bool ir_hat_quiesce(void){return true;}
static bool rf433_hat_quiesce(void){return true;}
static bool ir_hat_release(void){hardware_calls++;return true;}
#define INIT_FN(n) static bool n(void){return true;}
INIT_FN(cc1101_is_init) INIT_FN(nrf24_is_init) INIT_FN(ir_hat_is_init) INIT_FN(rf433_hat_is_init) INIT_FN(ir_hat_is_jamming) INIT_FN(rf433_hat_is_jamming)
#define HW_FN(n) static void n(void){hardware_calls++;}
HW_FN(cc1101_deinit) HW_FN(nrf24_deinit) HW_FN(ir_hat_deinit) HW_FN(rf433_hat_deinit)  HW_FN(rf433_hat_capture_cancel) HW_FN(rf433_hat_jam_stop)
static int s_lbk_result_lbl,s_lbk_retry_btn,s_lbk_status_lbl;
static bool lv_obj_is_valid(int o){(void)o;return false;}
static void lv_label_set_text(int o,const char*s){(void)o;(void)s;}
static void lv_obj_add_flag(int o,int f){(void)o;(void)f;}
#define LV_OBJ_FLAG_HIDDEN 1
#define tskIDLE_PRIORITY 0
static void rf433_lbk_task(void*a){(void)a;}
static int xTaskCreate(void(*f)(void*),const char*n,int z,void*a,int p,void*t){(void)f;(void)n;(void)z;(void)a;(void)p;(void)t;hardware_calls++;return pdPASS;}
#define RF_HAT_RF433_TX_GPIO 8
#define GPIO_MODE_OUTPUT 1
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_DISABLE 0
typedef int gpio_num_t;
typedef struct{uint64_t pin_bit_mask;int mode,pull_up_en,pull_down_en,intr_type;}gpio_config_t;
static int gpio_config(gpio_config_t*c){(void)c;hardware_calls++;return 0;}
static int gpio_set_level(int p,int v){(void)p;(void)v;hardware_calls++;return 0;}
"""
post=r"""
int main(void){
 release_ok=false;
 assert(!ir_hat_claim());assert(!rf433_hat_claim());assert(!cc1101_hat_claim());assert(!nrf24_hat_claim());rf433_lbk_run();assert(rf433_rx_prepare()==ESP_ERR_INVALID_STATE);
 assert(release_calls==6 && hardware_calls==0);
 release_ok=true;
 assert(ir_hat_claim());assert(rf433_hat_claim());assert(cc1101_hat_claim());assert(nrf24_hat_claim());rf433_lbk_run();assert(rf433_rx_prepare()==ESP_OK);
 assert(release_calls==12 && hardware_calls>0);
 puts("PASS six actual shared-pin callers refuse all hardware access on retained PN532 ownership; recovery admits normal paths");
}
"""
code='\n'.join(extract(n) for n in names)
(D/'host.c').write_text(pre+code+post)
cmd=[os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie',str(D/'host.c'),'-o',str(D/'host')]
subprocess.run(cmd,check=True);subprocess.run([str(D/'host')],check=True)
(D/'provenance.json').write_text(json.dumps({'source':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'extracted_verbatim':names,'extracted_sha256':hashlib.sha256(code.encode()).hexdigest(),'callers':6,'classification':'mocked-host production call-site execution; no GPIO/hardware access'},indent=2))
