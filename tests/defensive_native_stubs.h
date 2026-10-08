/* Offline SDK substitutes: no radio backend. UUID helpers and LVGL are HAL stubs. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#define MYNEWT_VAL(x) CFG_##x
#ifndef CFG_BLE_EXT_ADV
#define CFG_BLE_EXT_ADV 1
#endif
#define CFG_BLE_STATIC_TO_DYNAMIC 0
#define CFG_BLE_EXTRA_ADV_FIELDS 0
#define CFG_ENC_ADV_DATA 0
#define CFG_BLE_ADV_UUID_CONCAT 0
#define BLE_HCI_MAX_ADV_DATA_LEN 31
#define BLE_HS_EMSGSIZE 4
#define BLE_HS_EBADDATA 10
#define BLE_HS_EALREADY 2
#define BLE_HS_ENOTSUP 8
#define BLE_HS_DBG_ASSERT(x) assert(x)
#define BLE_HS_LOG(...) ((void)0)
typedef struct {uint8_t type;} ble_uuid_t;
typedef struct {ble_uuid_t u; uint16_t value;} ble_uuid16_t;
typedef struct {ble_uuid_t u; uint32_t value;} ble_uuid32_t;
typedef struct {ble_uuid_t u; uint8_t value[16];} ble_uuid128_t;
typedef union {ble_uuid16_t u16; ble_uuid32_t u32; ble_uuid128_t u128;} ble_uuid_any_t;
static uint16_t get_le16(const uint8_t *p){return p[0]|(p[1]<<8);}
static int ble_uuid_init_from_buf(ble_uuid_any_t *u,const uint8_t *p,int n){memset(u,0,sizeof(*u));if(n==2)u->u16.value=get_le16(p);else if(n==4)memcpy(&u->u32.value,p,4);else memcpy(u->u128.value,p,16);return 0;}
static uint16_t ble_uuid_u16(const ble_uuid_t *u){return ((const ble_uuid16_t *)u)->value;}
#define WP_SVC_UUID16 0xFE2C
#define TAG "offline"
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
#define pdMS_TO_TICKS(x) (x)
#define portMUX_TYPE int
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(x) ((void)0)
#define portEXIT_CRITICAL(x) ((void)0)
static uint64_t clock_ms=0;
static uint64_t esp_timer_get_time(void){return clock_ms*1000;}
static void vTaskDelay(int t){(void)t;}
typedef struct {bool deleted;} lv_timer_t;
typedef struct {char text[160];} lv_obj_t;
typedef int lv_event_t;
static lv_timer_t timer_storage;
static bool fail_timer=false, fail_init=false;
static int deleted_timers=0;
static lv_timer_t *lv_timer_create(void (*cb)(lv_timer_t*),int ms,void *p){(void)cb;(void)ms;(void)p;timer_storage.deleted=false;return fail_timer?NULL:&timer_storage;}
static void lv_timer_del(lv_timer_t *t){t->deleted=true;deleted_timers++;}
static bool lv_obj_is_valid(lv_obj_t *o){return o!=NULL;}
static void lv_label_set_text(lv_obj_t *o,const char *s){assert(o);snprintf(o->text,sizeof(o->text),"%s",s);}
static lv_obj_t *lv_obj_get_child(lv_obj_t *o,int n){(void)n;return o;}
#define lv_obj_set_style_bg_color(...) ((void)0)
#define lv_obj_set_style_text_color(...) ((void)0)
#define lv_obj_set_style_text_font(...) ((void)0)
#define lv_obj_set_width(...) ((void)0)
#define lv_obj_clean(...) ((void)0)
#define lv_bar_set_value(...) ((void)0)
static lv_obj_t *lv_label_create(lv_obj_t *o){return o;}
#define lv_color_make(...) 0
#define lv_pct(x) (x)
#define LV_STATE_DEFAULT 0
#define LV_SYMBOL_WARNING "!"
#define LV_SYMBOL_BLUETOOTH "BLE"
#define LV_ANIM_ON 0
#define COLOR_MATERIAL_RED 0
#define COLOR_MATERIAL_GREEN 0
#define ui_text_color() 0
static bool ensure_ble_mode(void){return !fail_init;}
#define BLE_SPAM_ADV_INSTANCE 1
#define BLE_OWN_ADDR_RANDOM 1
#define BLE_ADDR_RANDOM 1
#define BLE_HCI_LE_PHY_1M 1
#define BLE_GAP_ADV_ITVL_MS(x) (x)
typedef struct {uint8_t type;uint8_t val[6];} ble_addr_t;
struct ble_gap_ext_adv_params {int connectable,scannable,legacy_pdu,own_addr_type,primary_phy,secondary_phy,itvl_min,itvl_max,tx_power,sid;};
enum {BLE_SPAM_MODE_APPLE,BLE_SPAM_MODE_SAMSUNG,BLE_SPAM_MODE_GOOGLE,BLE_SPAM_MODE_WINDOWS,BLE_SPAM_MODE_ALL,BLE_SPAM_MODE_AIRTAG,BLE_SPAM_MODE_SMARTTAG,BLE_SPAM_MODE_SOUR_APPLE};
static bool ble_spam_active=false,ble_spam_needs_ui_update=false,ble_spam_ui_active=true;
static int ble_spam_count=0,ble_spam_mode=0;
static lv_obj_t status_obj,button_obj,counter_obj;
static lv_obj_t *ble_spam_status_label=&status_obj,*ble_spam_start_btn=&button_obj,*ble_spam_counter_label=&counter_obj;
static uint32_t rng=0x43594d;
static uint32_t esp_random(void){rng=rng*1664525u+1013904223u;return rng;}
static void esp_fill_random(void *p,size_t n){uint8_t *b=p;while(n--)*b++=(uint8_t)esp_random();}
static int fail_config=0,fail_stop=0,fail_addr=0,fail_gen=0,fail_set=0,fail_data=0,fail_start=0;
static bool fail_alloc=false;
static int start_calls=0,addr_calls=0,fail_addr_at=0,stop_calls=0;
static int ble_gap_ext_adv_configure(int n,void *p,void *a,void *b,void *c){(void)n;(void)p;(void)a;(void)b;(void)c;return fail_config;}
static int ble_gap_ext_adv_stop(int n){(void)n;stop_calls++;return fail_stop;}
static int ble_gap_ext_adv_set_addr(int n,ble_addr_t *p){(void)n;(void)p;addr_calls++;return fail_addr_at==addr_calls?7:fail_addr;}
static int ble_hs_id_gen_rnd(int n,ble_addr_t *p){(void)n;memset(p,0,sizeof(*p));p->type=1;p->val[5]=0xc0;return fail_gen;}
static int ble_gap_ext_adv_start(int n,int a,int b){(void)n;(void)a;(void)b;start_calls++;return fail_start;}
#define NIMBLE_BLE_ADVERTISE 1
#define SOC_ESP_NIMBLE_CONTROLLER 1
#define BLE_HS_EINVAL 3
#define htole16(x) (x)
#define htole32(x) (x)
static void put_le16(uint8_t *p,uint16_t v){p[0]=v;p[1]=v>>8;}
static void put_le32(uint8_t *p,uint32_t v){for(int i=0;i<4;i++)p[i]=v>>(8*i);}
struct os_mbuf {int n;uint8_t data[96];};
static int os_mbuf_append(struct os_mbuf *o,const void *p,int n){if(o->n+n>96)return BLE_HS_EMSGSIZE;memcpy(o->data+o->n,p,n);o->n+=n;return 0;}
static int ble_uuid_flat(const ble_uuid_t *u,void *p){assert(u->type==16);put_le16(p,ble_uuid_u16(u));return 0;}
static int ble_uuid_to_mbuf(const ble_uuid_t *u,struct os_mbuf *o){uint8_t b[2];ble_uuid_flat(u,b);return os_mbuf_append(o,b,2);}
static struct os_mbuf mbuf;
static struct ble_hs_adv_fields captured;
static uint8_t captured_mfg[64],captured_svc[64],captured_name[64];
static struct os_mbuf *os_msys_get_pkthdr(int n,int a){(void)n;(void)a;return fail_alloc?NULL:&mbuf;}
static void os_mbuf_free_chain(struct os_mbuf *o){(void)o;}
static int os_mbuf_len(struct os_mbuf *o){return o->n;}
static int ble_hs_adv_set_fields_mbuf(const struct ble_hs_adv_fields *f,struct os_mbuf *o){captured=*f;if(f->mfg_data){memcpy(captured_mfg,f->mfg_data,f->mfg_data_len);captured.mfg_data=captured_mfg;}if(f->svc_data_uuid16){memcpy(captured_svc,f->svc_data_uuid16,f->svc_data_uuid16_len);captured.svc_data_uuid16=captured_svc;}if(f->name){memcpy(captured_name,f->name,f->name_len);captured.name=captured_name;}o->n=0;return fail_set?fail_set:adv_set_fields(f,NULL,NULL,0,o);}
static int ble_gap_ext_adv_set_data(int n,struct os_mbuf *o){(void)n;(void)o;return fail_data;}
#define BLE_GAP_EVENT_DISC 1
#define BLE_GAP_EVENT_EXT_DISC 2
struct ble_gap_disc_desc {const uint8_t *data;uint8_t length_data;ble_addr_t addr;int8_t rssi;};
struct ble_gap_ext_disc_desc {const uint8_t *data;uint16_t length_data;ble_addr_t addr;int8_t rssi;};
struct ble_gap_event {int type;struct ble_gap_disc_desc disc;struct ble_gap_ext_disc_desc ext_disc;};
