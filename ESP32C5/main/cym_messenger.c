#include "cym_messenger.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "esp_random.h"
#include "esp_mac.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "psa/crypto.h"
#include "wifi_common.h"
#include <stdlib.h>
#include <string.h>
_Static_assert(CM_FRAME_MAX<=ESP_NOW_MAX_DATA_LEN,"installed SDK common MTU");
const cym_message_backend cym_message_backends[5]={
 {"ESP-NOW",true,CM_TEXT_MAX},{"BLE",false,0},{"LocalSend",false,0},
 {"LoRa / Reticulum",false,0},{"IR / CardputerZero",false,0}};
/* main.c owns the existing radio caller map, no UI object crosses this boundary. */
extern bool cym_messenger_radio_claim(void);
extern void cym_messenger_radio_release(void);
typedef struct {uint8_t source[6],data[CM_FRAME_MAX];size_t len;} rx_item;
typedef struct {
 cm_core core;rx_item rx[4];unsigned head,count;
 cm_message view[4];unsigned view_head,view_count;
 uint8_t tx[CM_TEXT_MAX];size_t tx_len;bool tx_queued,stop,accept;
 cym_messenger_config config;
} msg_context;
/* Classic DRAM has only eight baseline static bytes available. Retain just one
 * controller pointer; allocate the lock/mailbox/status lazily, not new globals. */
typedef struct {
 portMUX_TYPE lock;msg_context *session;TaskHandle_t task;
 bool starting,cancel; cym_messenger_config config;cym_messenger_status snapshot;
 bool initialized,key_busy_value,key_ready_value,key_generate_value,key_discard_value;
 char key_text[33];
} msg_controller;
static msg_controller *ctl;
static bool controller_init(void){
 if(__atomic_load_n(&ctl,__ATOMIC_ACQUIRE))return true;
 msg_controller *p=heap_caps_calloc(1,sizeof(*p),MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);if(!p)return false;
 p->lock=(portMUX_TYPE)portMUX_INITIALIZER_UNLOCKED;
 msg_controller *expected=NULL;
 if(!__atomic_compare_exchange_n(&ctl,&expected,p,false,__ATOMIC_RELEASE,__ATOMIC_ACQUIRE))heap_caps_free(p);
 return true;
}
#define mux (ctl->lock)
#define context (ctl->session)
#define worker_task (ctl->task)
#define launching (ctl->starting)
#define cancel_requested (ctl->cancel)
#define request (ctl->config)
#define status (ctl->snapshot)
#define now_initialized (ctl->initialized)
#define key_busy (ctl->key_busy_value)
#define key_ready (ctl->key_ready_value)
#define key_generate (ctl->key_generate_value)
#define key_discard (ctl->key_discard_value)
#define generated_key (ctl->key_text)
/* Copy while SDK data is valid. All context accesses are inside this same short
 * lock; unregister + pointer retirement cannot leave a callback using freed RAM.
 * An old queued callback after reentry still needs the new random session/HMAC. */
static void receive_cb(const esp_now_recv_info_t *info,const uint8_t *data,int len){
 if(!info||!info->src_addr||!info->des_addr||!data||len<CM_HEADER+CM_TAG||len>CM_FRAME_MAX)return;
 portENTER_CRITICAL(&mux);msg_context *c=context;
 if(c&&c->accept&&!memcmp(info->src_addr,c->config.peer,6)&&!memcmp(info->des_addr,status.own_mac,6)){
  if(c->count<4){rx_item *r=&c->rx[(c->head+c->count)%4];memcpy(r->source,info->src_addr,6);memcpy(r->data,data,len);r->len=len;c->count++;}
  else status.rx_dropped++;
 }
 portEXIT_CRITICAL(&mux);
}
static bool sdk_auth(const uint8_t key[16],const uint8_t *data,size_t len,uint8_t out[32]){
 psa_key_attributes_t attrs=PSA_KEY_ATTRIBUTES_INIT;
 psa_set_key_type(&attrs,PSA_KEY_TYPE_HMAC);
 psa_set_key_usage_flags(&attrs,PSA_KEY_USAGE_SIGN_MESSAGE);
 psa_set_key_algorithm(&attrs,PSA_ALG_HMAC(PSA_ALG_SHA_256));
 mbedtls_svc_key_id_t id=0;size_t written=0;
 psa_status_t rc=psa_import_key(&attrs,key,16,&id);psa_reset_key_attributes(&attrs);
 if(rc!=PSA_SUCCESS)return false;
 rc=psa_mac_compute(id,PSA_ALG_HMAC(PSA_ALG_SHA_256),data,len,out,32,&written);
 psa_status_t retired=psa_destroy_key(id);
 return rc==PSA_SUCCESS&&retired==PSA_SUCCESS&&written==32;
}
static void publish(cym_messenger_state state,int error){portENTER_CRITICAL(&mux);status.state=state;status.error=error;status.can_send=false;portEXIT_CRITICAL(&mux);}
static bool stopping(msg_context *c){portENTER_CRITICAL(&mux);bool stop=c->stop;portEXIT_CRITICAL(&mux);return stop;}
static bool transmit(msg_context *c,const cm_frame *f){
 /* Never NULL destination (broadcast/all-peers). Failure still consumes one of
  * the bounded application attempts. Radio callback status is NOT delivery. */
 return f->len&&f->len<=ESP_NOW_MAX_DATA_LEN&&esp_now_send(c->config.peer,f->bytes,f->len)==ESP_OK;
}
static void messenger_worker(void *unused){
 (void)unused;ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
 msg_context *c=heap_caps_calloc(1,sizeof(*c),MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
 bool radio=false,driver=false,peer=false,registered=false,channel_changed=false;
 uint8_t old_channel=0;wifi_second_chan_t old_second=WIFI_SECOND_CHAN_NONE;
#if CONFIG_BOARD_HAS_5GHZ
 wifi_band_mode_t old_band=WIFI_BAND_MODE_AUTO;bool band_changed=false;
#endif
 int err=ESP_ERR_NO_MEM;cym_messenger_state final=MSG_FAILED;
 if(!c)goto done;
 if(psa_crypto_init()!=PSA_SUCCESS){err=ESP_FAIL;goto done;}
 portENTER_CRITICAL(&mux);c->config=request;c->stop=cancel_requested;context=c;portEXIT_CRITICAL(&mux);
 /* Radio claim refuses active utility, scan, BLE, survey or non-idle driver.
  * D's gate drains pending power writes and excludes stop/deinit until restore. */
 if(!cym_messenger_radio_claim()){final=MSG_BUSY;err=ESP_ERR_INVALID_STATE;goto done;}radio=true;
 if(!cym_wifi_messenger_claim()){final=MSG_BUSY;err=ESP_ERR_INVALID_STATE;goto done;}driver=true;
 if(stopping(c)){final=MSG_STOPPED;err=ESP_OK;goto done;}
 wifi_country_t country;wifi_mode_t mode;wifi_ap_record_t associated;bool promisc=true;
 if((err=esp_wifi_get_country(&country))!=ESP_OK||
    (err=esp_wifi_get_mode(&mode))!=ESP_OK||mode!=WIFI_MODE_STA||
    esp_wifi_sta_get_ap_info(&associated)==ESP_OK||
    (err=esp_wifi_get_promiscuous(&promisc))!=ESP_OK||promisc){final=MSG_BUSY;goto done;}
 if(c->config.channel<1||c->config.channel>11||c->config.channel<country.schan||c->config.channel>=(unsigned)country.schan+country.nchan){err=ESP_ERR_INVALID_ARG;goto done;}
 if((err=esp_wifi_get_channel(&old_channel,&old_second))!=ESP_OK)goto done;
#if CONFIG_BOARD_HAS_5GHZ
 if((err=esp_wifi_get_band_mode(&old_band))!=ESP_OK)goto done;
 if((err=esp_wifi_set_band_mode(WIFI_BAND_MODE_2G_ONLY))!=ESP_OK)goto done;band_changed=true;
#endif
 if((err=esp_wifi_set_channel(c->config.channel,WIFI_SECOND_CHAN_NONE))!=ESP_OK)goto done;channel_changed=true;
 uint8_t own[6],nonce[16],pmk[16];
 if((err=esp_wifi_get_mac(WIFI_IF_STA,own))!=ESP_OK)goto done;
 if(!memcmp(own,c->config.peer,6)){err=ESP_ERR_INVALID_ARG;goto done;}
 esp_fill_random(nonce,sizeof(nonce));cm_init(&c->core,c->config.key,own,c->config.peer,nonce,sdk_auth);memset(nonce,0,sizeof(nonce));
 if(!now_initialized){if((err=esp_now_init())!=ESP_OK)goto done;now_initialized=true;}
 /* PMK wraps the LMK locally, it is not the shared over-air LMK. SDK header
  * explicitly describes this. No teardown of the retained SDK on S3/C5. */
 esp_fill_random(pmk,sizeof(pmk));err=esp_now_set_pmk(pmk);memset(pmk,0,sizeof(pmk));if(err!=ESP_OK)goto done;
 esp_now_peer_info_t p={0};memcpy(p.peer_addr,c->config.peer,6);memcpy(p.lmk,c->config.key,16);p.channel=c->config.channel;p.ifidx=WIFI_IF_STA;p.encrypt=true;
 err=esp_now_add_peer(&p);memset(p.lmk,0,sizeof(p.lmk));if(err!=ESP_OK)goto done;peer=true;
 portENTER_CRITICAL(&mux);memcpy(status.own_mac,own,6);c->accept=true;portEXIT_CRITICAL(&mux);
 if((err=esp_now_register_recv_cb(receive_cb))!=ESP_OK)goto done;registered=true;
 publish(MSG_WAITING,ESP_OK);
 cm_frame out;rx_item rx;uint8_t text[CM_TEXT_MAX];unsigned hellos=0;uint32_t last_hello=0;
 while(!stopping(c)){
  uint32_t now=(uint32_t)(esp_timer_get_time()/1000);
  if(!c->core.ready&&hellos<30&&(!hellos||(uint32_t)(now-last_hello)>=1000)){
   if(cm_hello(&c->core,&out))transmit(c,&out);last_hello=now;hellos++;
  }
  bool got=false;size_t txlen=0;
  portENTER_CRITICAL(&mux);
  if(c->count){rx=c->rx[c->head];c->head=(c->head+1)%4;c->count--;got=true;}
  if(c->tx_queued){txlen=c->tx_len;memcpy(text,c->tx,txlen);memset(c->tx,0,sizeof(c->tx));c->tx_queued=false;}
  portEXIT_CRITICAL(&mux);
  if(got){cm_receive(&c->core,rx.source,rx.data,rx.len,&out);if(out.len)transmit(c,&out);memset(&rx,0,sizeof(rx));}
  if(txlen){if(cm_submit(&c->core,text,txlen,now,&out))transmit(c,&out);memset(text,0,sizeof(text));}
  if(cm_retry(&c->core,now,&out))transmit(c,&out);
  /* Inbox acceptance precedes ACK. UI display consumes a second bounded ring;
   * if not polled, both rings fill and core refuses more DATA without ACK. */
  portENTER_CRITICAL(&mux);
  if(c->view_count<4&&c->core.in_count){cm_pop(&c->core,&c->view[(c->view_head+c->view_count)%4]);c->view_count++;}
  status.state=c->core.ready?MSG_READY:MSG_WAITING;status.delivery=c->core.delivery;
  status.can_send=c->core.ready&&c->core.delivery!=CM_PENDING&&!c->tx_queued;
  portEXIT_CRITICAL(&mux);
  vTaskDelay(pdMS_TO_TICKS(20));
 }
 final=MSG_STOPPED;err=ESP_OK;
done:
 publish(MSG_STOPPING,err);
 if(c){portENTER_CRITICAL(&mux);c->accept=false;portEXIT_CRITICAL(&mux);}
 /* Fail closed: bounded retry rounds, retaining owner/context on uncertainty.
  * A subsequent Stop requests another cleanup round; never reuse live state. */
 for(;;){
  int cleanup=ESP_OK;
  if(registered){cleanup=esp_now_unregister_recv_cb();if(cleanup==ESP_OK)registered=false;}
  if(cleanup==ESP_OK&&peer){cleanup=esp_now_del_peer(c->config.peer);if(cleanup==ESP_OK||cleanup==ESP_ERR_ESPNOW_NOT_FOUND){peer=false;cleanup=ESP_OK;}}
#if CONFIG_BOARD_HAS_5GHZ
  if(cleanup==ESP_OK&&band_changed){cleanup=esp_wifi_set_band_mode(old_band);if(cleanup==ESP_OK)band_changed=false;}
#endif
  if(cleanup==ESP_OK&&channel_changed){cleanup=esp_wifi_set_channel(old_channel,old_second);if(cleanup==ESP_OK)channel_changed=false;}
  if(cleanup==ESP_OK)break;
  publish(MSG_RETAINED,cleanup);ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
 }
 if(driver)cym_wifi_messenger_release();if(radio)cym_messenger_radio_release();
 portENTER_CRITICAL(&mux);context=NULL;status.state=final;status.error=err;status.can_send=false;
 memset(&request,0,sizeof(request));portEXIT_CRITICAL(&mux);
 if(c){memset(c,0,sizeof(*c));heap_caps_free(c);}
 portENTER_CRITICAL(&mux);worker_task=NULL;launching=false;portEXIT_CRITICAL(&mux);
 vTaskDelete(NULL); // ordinary IDF internal stack/TCB reclaimed by idle task
}
bool cym_messenger_busy(void){if(!__atomic_load_n(&ctl,__ATOMIC_ACQUIRE))return false;portENTER_CRITICAL(&mux);bool busy=worker_task||launching;portEXIT_CRITICAL(&mux);return busy;}
bool cym_messenger_start(const cym_messenger_config *config){
 if(!controller_init())return false;
 if(!config||config->channel<1||config->channel>11||(config->peer[0]&1))return false;
 uint8_t any=0,key=0;for(unsigned i=0;i<6;i++)any|=config->peer[i];for(unsigned i=0;i<16;i++)key|=config->key[i];if(!any||!key)return false;
 portENTER_CRITICAL(&mux);if(worker_task||launching){portEXIT_CRITICAL(&mux);return false;}launching=true;cancel_requested=false;request=*config;memset(&status,0,sizeof(status));status.state=MSG_STARTING;portEXIT_CRITICAL(&mux);
 TaskHandle_t created=NULL;BaseType_t ok=xTaskCreate(messenger_worker,"messenger",4096,NULL,4,&created);
 portENTER_CRITICAL(&mux);if(ok==pdPASS){worker_task=created;xTaskNotifyGive(created);}else{launching=false;memset(&request,0,sizeof(request));status.state=MSG_FAILED;status.error=ESP_ERR_NO_MEM;}portEXIT_CRITICAL(&mux);
 return ok==pdPASS;
}
void cym_messenger_stop(void){if(!__atomic_load_n(&ctl,__ATOMIC_ACQUIRE))return;portENTER_CRITICAL(&mux);cancel_requested=true;key_discard=true;key_ready=false;memset(generated_key,0,33);if(context)context->stop=true;status.can_send=false;if(worker_task)xTaskNotifyGive(worker_task);portEXIT_CRITICAL(&mux);}
bool cym_messenger_send(const char *text,size_t len){
 if(!__atomic_load_n(&ctl,__ATOMIC_ACQUIRE))return false;
 if(!cm_text_valid((const uint8_t *)text,len))return false;
 portENTER_CRITICAL(&mux);msg_context *c=context;bool ok=c&&status.can_send&&!c->tx_queued&&!c->stop;
 if(ok){memcpy(c->tx,text,len);c->tx_len=len;c->tx_queued=true;status.can_send=false;}portEXIT_CRITICAL(&mux);return ok;
}
void cym_messenger_snapshot(cym_messenger_status *out){if(!__atomic_load_n(&ctl,__ATOMIC_ACQUIRE)){memset(out,0,sizeof(*out));return;}portENTER_CRITICAL(&mux);*out=status;portEXIT_CRITICAL(&mux);}
bool cym_messenger_take(cm_message *out){if(!__atomic_load_n(&ctl,__ATOMIC_ACQUIRE))return false;portENTER_CRITICAL(&mux);msg_context *c=context;bool ok=c&&c->view_count;
 if(ok){*out=c->view[c->view_head];memset(&c->view[c->view_head],0,sizeof(*out));c->view_head=(c->view_head+1)%4;c->view_count--;}portEXIT_CRITICAL(&mux);return ok;}
static int unhex(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
bool cym_messenger_parse_key(const char *text,uint8_t out[16]){if(!text||strlen(text)!=32)return false;uint8_t temp[16],any=0;for(unsigned i=0;i<16;i++){int a=unhex(text[i*2]),b=unhex(text[i*2+1]);if(a<0||b<0)return false;temp[i]=(a<<4)|b;any|=temp[i];}if(!any)return false;memcpy(out,temp,16);memset(temp,0,sizeof(temp));return true;}
bool cym_messenger_parse_mac(const char *text,uint8_t out[6]){if(!text||strlen(text)!=17)return false;uint8_t temp[6],any=0;for(unsigned i=0;i<6;i++){int a=unhex(text[i*3]),b=unhex(text[i*3+1]);if(a<0||b<0||(i<5&&text[i*3+2]!=':'))return false;temp[i]=(a<<4)|b;any|=temp[i];}if(!any||(temp[0]&1))return false;memcpy(out,temp,6);return true;}
static void key_worker(void *arg){
 (void)arg;uint8_t key[16],own[6];char hex[33]={0};
 bool identified=esp_read_mac(own,ESP_MAC_WIFI_STA)==ESP_OK;
 portENTER_CRITICAL(&mux);bool generate=key_generate;portEXIT_CRITICAL(&mux);
 /* SDK guarantees hardware entropy with the WiFi RF source active. Refuse to
  * pretend an RF-off PRNG result is a newly generated hardware-random LMK. */
 bool random_ok=generate&&wifi_power_status()==PWR_RADIO_APPLIED;
 if(random_ok){esp_fill_random(key,16);static const char digits[]="0123456789abcdef";for(unsigned i=0;i<16;i++){hex[i*2]=digits[key[i]>>4];hex[i*2+1]=digits[key[i]&15];}}
 portENTER_CRITICAL(&mux);
 if(identified)memcpy(status.own_mac,own,6);
 if(!key_discard&&random_ok){memcpy(generated_key,hex,33);key_ready=true;}
 if(generate&&!random_ok)status.error=ESP_ERR_INVALID_STATE;
 key_busy=false;portEXIT_CRITICAL(&mux);memset(hex,0,sizeof(hex));memset(key,0,sizeof(key));vTaskDelete(NULL);
}
static bool info_request(bool generate){if(!controller_init())return false;portENTER_CRITICAL(&mux);bool ok=!key_busy;if(ok){key_busy=true;key_generate=generate;key_discard=false;key_ready=false;memset(generated_key,0,33);}portEXIT_CRITICAL(&mux);if(!ok)return false;
 if(xTaskCreate(key_worker,"msg_key",4096,NULL,3,NULL)!=pdPASS){portENTER_CRITICAL(&mux);key_busy=false;portEXIT_CRITICAL(&mux);return false;}return true;}
bool cym_messenger_key_request(void){return info_request(true);}
bool cym_messenger_info_request(void){return info_request(false);}
bool cym_messenger_key_take(char out[33]){if(!__atomic_load_n(&ctl,__ATOMIC_ACQUIRE))return false;portENTER_CRITICAL(&mux);bool ok=key_ready;if(ok){memcpy(out,generated_key,33);memset(generated_key,0,33);key_ready=false;}portEXIT_CRITICAL(&mux);return ok;}
