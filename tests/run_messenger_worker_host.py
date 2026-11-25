#!/usr/bin/env python3
"""Execute the complete production ESP-NOW worker with deterministic SDK/RTOS
fault endpoints, OpenSSL-backed PSA shim. Not embedded scheduling/RF evidence.
"""
from pathlib import Path
import os,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'messenger-worker';D.mkdir(parents=True,exist_ok=True)
stubs=r"""
#ifndef MOCK_SDK_H
#define MOCK_SDK_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NO_MEM 0x101
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_INVALID_ARG 0x102
#define ESP_ERR_ESPNOW_NOT_FOUND 0x3069
#define ESP_NOW_MAX_DATA_LEN 250
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
#define WIFI_MODE_STA 1
#define WIFI_IF_STA 0
#define ESP_MAC_WIFI_STA 0
#define WIFI_SECOND_CHAN_NONE 0
#define PWR_RADIO_APPLIED 2
#define CONFIG_BOARD_HAS_5GHZ 0
#define portMUX_INITIALIZER_UNLOCKED 0
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY 0xffffffff
#define pdMS_TO_TICKS(x) (x)
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
typedef int portMUX_TYPE,BaseType_t,wifi_second_chan_t,wifi_mode_t,esp_err_t;
typedef void *TaskHandle_t;
typedef struct {uint8_t schan,nchan;} wifi_country_t;
typedef struct {int unused;} wifi_ap_record_t;
typedef struct {uint8_t *src_addr,*des_addr;void *rx_ctrl;} esp_now_recv_info_t;
typedef struct {uint8_t peer_addr[6],lmk[16],channel;int ifidx;bool encrypt;} esp_now_peer_info_t;
typedef void(*esp_now_recv_cb_t)(const esp_now_recv_info_t*,const uint8_t*,int);
static int fail_at,step,fail_alloc,fail_task,cleanup_fail,radio_held,driver_held,allocs,notify_count,loops;
static bool drop_ack,interactive;static uint64_t clock_us;static unsigned seed;
static void(*scheduled)(void*);static esp_now_recv_cb_t callback,old_callback;
static int checks,scenarios;
#include <assert.h>
#define CHECK(x) do{checks++;assert(x);}while(0)
static int sdk(void){step++;return step==fail_at?ESP_FAIL:ESP_OK;}
static void*heap_caps_calloc(size_t n,size_t s,int caps){CHECK((caps&MALLOC_CAP_INTERNAL)!=0);if(fail_alloc){fail_alloc=0;return NULL;}void *p=calloc(n,s);if(p)allocs++;return p;}
static void heap_caps_free(void*p){if(p)allocs--;free(p);}
static BaseType_t xTaskCreate(void(*fn)(void*),const char*n,unsigned stack,void*arg,int priority,TaskHandle_t*out){(void)n;(void)arg;(void)priority;CHECK(stack==4096);if(fail_task)return 0;scheduled=fn;if(out)*out=(void*)0x1234;return pdPASS;}
static void xTaskNotifyGive(TaskHandle_t t){CHECK(t==(void*)0x1234);notify_count++;}
static unsigned ulTaskNotifyTake(int clear,unsigned timeout){(void)clear;(void)timeout;if(cleanup_fail){cleanup_fail=0;fail_at=0;}return 1;}
static void vTaskDelete(TaskHandle_t t){CHECK(t==NULL);}
static void vTaskDelay(unsigned ms);
static int64_t esp_timer_get_time(void){return clock_us;}
static void esp_fill_random(void *p,size_t n){memset(p,++seed,n);}
static int esp_read_mac(uint8_t *p,int which){(void)which;memset(p,0,6);p[0]=2;p[1]=1;return ESP_OK;}
static int esp_wifi_get_mac(int which,uint8_t *p){esp_read_mac(p,which);return sdk();}
static int esp_wifi_get_country(wifi_country_t*p){p->schan=1;p->nchan=11;return sdk();}
static int esp_wifi_get_mode(wifi_mode_t*p){*p=WIFI_MODE_STA;return sdk();}
static int esp_wifi_sta_get_ap_info(wifi_ap_record_t*p){(void)p;return ESP_FAIL;}
static int esp_wifi_get_promiscuous(bool*p){*p=false;return sdk();}
static int esp_wifi_get_channel(uint8_t*p,wifi_second_chan_t*s){*p=6;*s=0;return sdk();}
static int esp_wifi_set_channel(uint8_t c,wifi_second_chan_t s){(void)s;CHECK(c==1||c==6);return sdk();}
static int esp_now_init(void){return sdk();}
static int esp_now_set_pmk(const uint8_t*p){CHECK(p!=NULL);return sdk();}
static int esp_now_add_peer(const esp_now_peer_info_t*p){CHECK(p->encrypt&&p->channel==1&&p->ifidx==WIFI_IF_STA);return sdk();}
static int esp_now_register_recv_cb(esp_now_recv_cb_t cb){int r=sdk();if(!r)old_callback=callback=cb;return r;}
static int esp_now_unregister_recv_cb(void){if(cleanup_fail)return ESP_FAIL;callback=NULL;return ESP_OK;}
static int esp_now_del_peer(const uint8_t*p){CHECK(p!=NULL);return ESP_OK;}
static int esp_now_send(const uint8_t*p,const uint8_t*d,size_t n);
static bool cym_wifi_messenger_claim(void){if(sdk())return false;driver_held++;return true;}
static void cym_wifi_messenger_release(void){CHECK(driver_held==1);driver_held--;}
static int wifi_power_status(void){return PWR_RADIO_APPLIED;}
typedef int psa_status_t,mbedtls_svc_key_id_t;
typedef struct {int unused;} psa_key_attributes_t;
#define PSA_KEY_ATTRIBUTES_INIT {0}
#define PSA_KEY_TYPE_HMAC 1
#define PSA_KEY_USAGE_SIGN_MESSAGE 1
#define PSA_ALG_SHA_256 1
#define PSA_ALG_HMAC(x) (x)
#define PSA_SUCCESS 0
static uint8_t crypto_key[16];
static void psa_set_key_type(psa_key_attributes_t*p,int x){(void)p;(void)x;}
static void psa_set_key_usage_flags(psa_key_attributes_t*p,int x){(void)p;(void)x;}
static void psa_set_key_algorithm(psa_key_attributes_t*p,int x){(void)p;(void)x;}
static void psa_reset_key_attributes(psa_key_attributes_t*p){(void)p;}
static int psa_crypto_init(void){return ESP_OK;}
static int psa_import_key(psa_key_attributes_t*p,const uint8_t*k,size_t n,int*id){(void)p;CHECK(n==16);memcpy(crypto_key,k,16);*id=1;return 0;}
#include <openssl/hmac.h>
static int psa_mac_compute(int id,int a,const uint8_t*p,size_t n,uint8_t*out,size_t cap,size_t*written){(void)id;(void)a;CHECK(cap==32);unsigned len;CHECK(HMAC(EVP_sha256(),crypto_key,16,p,n,out,&len)!=NULL);*written=len;return 0;}
static int psa_destroy_key(int id){(void)id;memset(crypto_key,0,16);return 0;}
#endif
"""
(D/'mock.h').write_text(stubs)
for name in ['esp_now.h','esp_wifi.h','esp_random.h','esp_mac.h','esp_heap_caps.h','esp_timer.h','wifi_common.h','freertos/FreeRTOS.h','freertos/task.h','psa/crypto.h']:
 p=D/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#include "mock.h"\n')
harness=r"""
#include <stdio.h>
#include "mock.h"
#include "cym_messenger.c"
#undef status
#undef request
#undef context
#undef worker_task
#undef launching
#undef mux
static cm_core remote;static uint8_t own[6]={2,1},peer[6]={2,2};static cm_frame remote_reply;
static bool cym_auth(const uint8_t*k,const uint8_t*p,size_t n,uint8_t*out){return sdk_auth(k,p,n,out);}
bool cym_messenger_radio_claim(void){if(sdk())return false;radio_held++;return true;}
void cym_messenger_radio_release(void){CHECK(radio_held==1);radio_held--;}
static void inject(const cm_frame*f){if(!callback)return;esp_now_recv_info_t info={.src_addr=peer,.des_addr=own};uint8_t local[CM_FRAME_MAX];memcpy(local,f->bytes,f->len);callback(&info,local,(int)f->len);memset(local,0,sizeof(local));}
static int esp_now_send(const uint8_t*p,const uint8_t*d,size_t n){CHECK(!memcmp(p,peer,6));CHECK(n<=250);if(interactive){cm_result r=cm_receive(&remote,own,d,n,&remote_reply);if(remote_reply.len){if(r==CM_ACCEPTED&&drop_ack)drop_ack=false;else inject(&remote_reply);}}return ESP_OK;}
static void vTaskDelay(unsigned ms){clock_us+=(uint64_t)ms*1000;loops++;
 if(interactive&&loops==3){CHECK(ctl->snapshot.state==MSG_READY);CHECK(cym_messenger_send("hello",5));CHECK(!cym_messenger_send("again",5));}
 if(interactive&&loops==5){CHECK(ctl->snapshot.delivery==CM_PENDING);cm_frame f;CHECK(cm_submit(&remote,(const uint8_t*)"peer",4,0,&f));for(int i=0;i<8;i++)inject(&f);CHECK(ctl->snapshot.rx_dropped>=4);}
 if(interactive&&loops==60){CHECK(ctl->snapshot.delivery==CM_CONFIRMED);cm_message m;CHECK(cym_messenger_take(&m));CHECK(m.len==4&&!memcmp(m.text,"peer",4));CHECK(!cym_messenger_take(&m));cym_messenger_stop();}
 if(!interactive||loops>100)cym_messenger_stop();
}
static void scenario(int failure,bool flow,bool cancel){
 scenarios++;fail_at=failure;step=loops=0;clock_us=0;interactive=flow;drop_ack=true;
 ctl->initialized=false;uint8_t k[16]={1},nonce[16]={99};cm_init(&remote,k,peer,own,nonce,cym_auth);
 cym_messenger_config config={.peer={2,2},.key={1},.channel=1};CHECK(cym_messenger_start(&config));CHECK(!cym_messenger_start(&config));
 if(cancel)cym_messenger_stop();scheduled(NULL);CHECK(!cym_messenger_busy());CHECK(radio_held==0&&driver_held==0);CHECK(allocs==1);CHECK(ctl->session==NULL);
 if(old_callback){uint8_t garbage[CM_FRAME_MAX]={0};esp_now_recv_info_t info={.src_addr=peer,.des_addr=own};old_callback(&info,garbage,sizeof(garbage));}
}
int main(void){
 fail_alloc=1;cym_messenger_config config={.peer={2,2},.key={1},.channel=1};CHECK(!cym_messenger_start(&config));CHECK(controller_init());CHECK(allocs==1);
 fail_task=1;CHECK(!cym_messenger_start(&config));fail_task=0;CHECK(!cym_messenger_busy());
 scenario(0,true,false);scenario(0,false,true);
 for(int i=1;i<=11;i++)scenario(i,false,false);
 fail_alloc=1;scenario(0,false,false);
 cleanup_fail=1;scenario(0,false,false);CHECK(ctl->snapshot.state==MSG_STOPPED);
 uint8_t parsed[16];CHECK(cym_messenger_parse_key("0102030405060708090a0b0c0d0e0f10",parsed));CHECK(!cym_messenger_parse_key("00000000000000000000000000000000",parsed));CHECK(!cym_messenger_parse_mac("ff:ff:ff:ff:ff:ff",parsed));CHECK(cym_messenger_parse_mac("02:ab:cd:ef:01:23",parsed));
 printf("RESULT checks=%d failures=0 scenarios=%d\n",checks,scenarios);return 0;
}
"""
(D/'host.c').write_text(harness)
cmd=['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I'+str(D),'-I'+str(R/'ESP32C5/main'),str(D/'host.c'),str(R/'ESP32C5/main/cym_messenger_core.c'),'-lcrypto','-o',str(D/'host')]
x=subprocess.run(cmd,capture_output=True,text=True);(D/'compile.log').write_text(x.stdout+x.stderr);assert x.returncode==0,x.stderr[-4000:]
x=subprocess.run([str(D/'host')],capture_output=True,text=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'));(D/'run.log').write_text(x.stdout+x.stderr)
(D/'provenance.json').write_text(json.dumps({'command':cmd,'production_sha256':hashlib.sha256((R/'ESP32C5/main/cym_messenger.c').read_bytes()).hexdigest(),'exit_code':x.returncode},indent=2));print(x.stdout+x.stderr);raise SystemExit(x.returncode)
