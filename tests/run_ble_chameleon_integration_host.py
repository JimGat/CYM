#!/usr/bin/env python3
"""Production arbiter + Chameleon lifecycle; deterministic SDK/RTOS fault boundaries.
No radio/security simulator: controller functions are fault stubs; live security
handler is not executed. Real callback admission and scan parser are extracted.
"""
from pathlib import Path
import re,os,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1]
M=(R/'ESP32C5/main/main.c').read_text();C=(R/'ESP32C5/main/chameleon_ble.c').read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'ble-chameleon';D.mkdir(parents=True,exist_ok=True)
def fn(s,n):
 m=re.search(r'(?:static )?(?:int|bool|void|BaseType_t|esp_err_t) '+n+r'\([^;]*?\)\s*\{',s);assert m,n
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
#include <string.h>
#include "chameleon_ble.h"
typedef void *TaskHandle_t;typedef int BaseType_t;typedef int esp_err_t;typedef int portMUX_TYPE;typedef int lv_event_t;typedef int lv_timer_t;typedef void lv_obj_t;
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define ESP_OK 0
#define TAG "host"
#define pdPASS 1
#define pdFAIL 0
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
#define pdMS_TO_TICKS(x) (x)
#define MYNEWT_VAL(x) EXT
#define CONFIG_IEEE802154_ENABLED 0
#define BLE_HS_EBUSY 15
#define BLE_HS_EALREADY 2
#define BLE_HS_ENOTSUP 8
#define BLE_HS_CONN_HANDLE_NONE 0xffff
#define BLE_GAP_EVENT_DISC 1
#define BLE_GAP_EVENT_EXT_DISC 2
#define BLE_GAP_EVENT_DISC_COMPLETE 3
#define BLE_GAP_EVENT_CONNECT 4
#define BLE_GAP_EVENT_DISCONNECT 5
#define BLE_ERR_REM_USER_CONN_TERM 19
#define BLE_OWN_ADDR_PUBLIC 0
#define BLE_HCI_SCAN_FILT_NO_WL 0
#define BLE_SM_IO_CAP_KEYBOARD_DISP 4
#define BLE_SM_PAIR_KEY_DIST_ENC 1
#define BLE_SM_PAIR_KEY_DIST_ID 2
#define BLE_GAP_INITIAL_CONN_ITVL_MIN 24
#define BLE_GAP_INITIAL_CONN_ITVL_MAX 40
#define CHAM_CMD_OUTCOME_NONE 0
#define MALLOC_CAP_DMA 1
#define RADIO_MODE_NONE 0
#define RADIO_MODE_WIFI 1
#define RADIO_MODE_BLE 2
typedef struct {uint8_t type,val[6];} ble_addr_t;
struct ble_gap_disc_desc{const uint8_t*data;uint8_t length_data;ble_addr_t addr;int8_t rssi;};
struct ble_gap_ext_disc_desc{const uint8_t*data;unsigned length_data;ble_addr_t addr;int8_t rssi;};
struct ble_gap_event{int type;struct ble_gap_disc_desc disc;struct ble_gap_ext_disc_desc ext_disc;struct{int status;uint16_t conn_handle;}connect;};
struct ble_gap_ext_disc_params{int itvl,window,passive;};
struct ble_gap_disc_params{int itvl,window,filter_policy,limited,passive,filter_duplicates;};
struct ble_gap_conn_params{int scan_itvl,scan_window,itvl_min,itvl_max,latency,supervision_timeout,min_ce_len,max_ce_len;};
struct uuid{int u;};static struct uuid s_nus_svc_uuid;
struct ble_hs_adv_fields{struct uuid*uuids128;int num_uuids128;const uint8_t*name;int name_len;};
static int ble_uuid_cmp(const void*a,const void*b){return 0;}
static int ble_hs_adv_parse_fields(struct ble_hs_adv_fields*f,const uint8_t*d,int n){memset(f,0,sizeof(*f));f->name=d;f->name_len=n;return 0;}
static bool s_bt_scan_api_busy,bt_scan_worker_busy,bt_scan_create_pending,bt_scan_active,ble_scan_finished;
static uint32_t s_bt_cham_token;static void *s_bt_scan_owner,*bt_scan_task_handle,*self=(void*)1;
static int s_bt_report_mux;static unsigned s_bt_reports_inflight;static bool s_bt_reports_accept,bt_tracking_mode;
static bool nimble_initialized=true,nimble_port_initialized=true,nimble_stop_requested,nimble_cleanup_busy,nimble_deinit_failed,nimble_host_exited=true,wifi_initialized;
static void*nimble_host_handle;static int current_radio_mode=RADIO_MODE_BLE;
static cham_state_t s_state=CHAM_STATE_DISCONNECTED;
static cham_scan_result_t s_scan_results[16];static int s_scan_count,s_connect_idx=-1;

static bool s_scan_legacy,s_changed;
static char s_status_msg[64];static portMUX_TYPE s_radio_mux;
static uint32_t s_radio_token,s_next_token,s_defer_token;static unsigned s_radio_callbacks;
static bool s_scan_owned,s_scan_accept,s_scan_restart_pending,s_closing,s_connect_pending,s_connect_inflight;
static int64_t s_defer_at,now;
static int64_t esp_timer_get_time(void){return now;}
static uint16_t s_conn_handle=BLE_HS_CONN_HANDLE_NONE,s_svc_start,s_svc_end,s_tx_val_hdl,s_rx_val_hdl,s_cccd_hdl;
static int s_rx_wr,s_rx_rd,s_pend_cmd;static void*s_pend_cb;static bool s_pend_cancelled;
static struct {int outcome,cmd,status;}s_last_result;
static bool s_ev_connected,s_ev_disconnected,s_ev_cccd_ok,s_ev_error,s_ev_passkey,s_await_enc;
static struct{int x;}s_rxs;
static struct{void(*sync_cb)(void);void(*reset_cb)(int);int sm_io_cap,sm_bonding,sm_mitm,sm_sc,sm_our_key_dist,sm_their_key_dist;}ble_hs_cfg;
struct ble_gatt_error{int status;};struct ble_gatt_attr{int unused;};
static bool s_pend_write_ok;
static int starts,cancels,connects,conn_cancels,terminates,deinits,creates;
static int start_rc,cancel_rc,connect_rc,terminate_rc,conn_cancel_rc,init_rc,create_rc=pdPASS;
static bool debug,publish_interleave,init_interleave;static void*connect_arg;static ble_addr_t peer_seen;
static TaskHandle_t xTaskGetCurrentTaskHandle(void){return self;}
static void vTaskDelay(int ms);
static void bt_scan_task(void*a){}
static int xTaskCreate(void(*f)(void*),const char*n,int sz,void*a,int pr,void**out){
 creates++;if(publish_interleave){assert(bt_scan_create_pending&&bt_scan_worker_busy);unsigned n=starts;cham_scan_start();assert(starts==n&&!s_radio_token&&strstr(s_status_msg,"busy"));}
 if(create_rc!=pdPASS)return create_rc;*out=(void*)2;return pdPASS;
}
static int ble_gap_ext_disc(int a,int b,int c,int d,int e,int f,struct ble_gap_ext_disc_params*g,void*h,int(*cb)(struct ble_gap_event*,void*),void*arg){starts++;return start_rc;}
static int ble_gap_disc(int a,int b,struct ble_gap_disc_params*c,int(*cb)(struct ble_gap_event*,void*),void*arg){starts++;return start_rc==BLE_HS_ENOTSUP?0:start_rc;}
static bool cleanup_probe,host_exit_on_delay=true;static int cleanup_probes,port_init_calls,host_creates,deinit_rc;
static int ble_gap_disc_cancel(void){cancels++;return cancel_rc;}
static int ble_gap_connect(int a,const ble_addr_t*p,int timeout,const struct ble_gap_conn_params*cp,int(*cb)(struct ble_gap_event*,void*),void*arg){assert(cp&&cp->scan_itvl==0x10&&cp->supervision_timeout==0x200);peer_seen=*p;connect_arg=arg;connects++;return connect_rc;}
static int ble_gap_conn_cancel(void){conn_cancels++;return conn_cancel_rc;}
static int ble_gap_terminate(int h,int why){terminates++;return terminate_rc;}
static int nimble_port_deinit(void){deinits++;return deinit_rc;}
static bool clock_radio_admit(void){return true;}
static bool cym_debug_enabled(void){return debug;}
static void heap_caps_print_heap_info(int x){}
static void log_heap_stats(const char*x){}
static void esp_wifi_stop(void){}
static void esp_wifi_deinit(void){}
static bool nav_to_menu_flag,s_cham_nav_child;
static void (*nav_deferred_show_fn)(void),(*g_screen_stop_fn)(void),(*g_screen_back_fn)(void);
static int nav_stack_depth,nav_stack[4],parent_calls,home_calls,stop_calls;
static void *s_cham_tmr,*s_cham_prog_lbl,*s_cham_content,*s_cham_bat_lbl,*s_cham_scan_list;
static int s_cham_ui_st,s_cham_list_n;
static void lv_timer_del(void*p){}
static void clock_cancel_radio_navigation(void){}
static void run_screen_stop_fn(void);
static void parent(void){parent_calls++;}
static void (*nav_show_lookup(int n))(void){return parent;}
static void show_menu(void){home_calls++;run_screen_stop_fn();}
static int bt_nimble_init(void);
static void bt_reset_counters(void){}
static void bt_scan_stop(void){bt_scan_active=false;
 if(cleanup_probe){assert(nimble_cleanup_busy);int n=port_init_calls;assert(!cym_ble_cham_acquire(998));assert(!s_bt_cham_token&&port_init_calls==n);cleanup_probes++;}
}
static bool bt_stop_scan(void){return false;}
static int s_scan_gap_cb(struct ble_gap_event*,void*);
static int s_gap_cb(struct ble_gap_event*,void*);
static int s_gap_cb_process(struct ble_gap_event*e,void*a){
 // Payload handler excluded; only production handle publications needed by boundary.
 if(e->type==BLE_GAP_EVENT_CONNECT&&!e->connect.status)s_conn_handle=e->connect.conn_handle;
 if(e->type==BLE_GAP_EVENT_DISCONNECT)s_conn_handle=BLE_HS_CONN_HANDLE_NONE;
 return 0;
}
static bool ensure_ble_mode_unreserved(void);
static void cham_cancel_pending_stub(void){}
#define cham_cancel_pending cham_cancel_pending_stub
#ifndef REAL_INIT
static int bt_nimble_init(void){if(init_interleave){assert(s_bt_cham_token);assert(!cym_ble_cham_acquire(999));}return init_rc;}
#else
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_NO_MEM 0x101
#define ESP_FAIL -1
#define BLE_SM_IO_CAP_NO_IO 3
#define CONFIG_BT_NIMBLE_HOST_TASK_STACK_SIZE 4096
#define CONFIG_BT_NIMBLE_PINNED_TO_CORE 0
#define configMAX_PRIORITIES 25
static bool s_bt_alloc_hook_registered,s_bt_alloc_capture,nimble_stop_complete,s_ble_for_blueduck;
static void bt_alloc_failed(size_t size,uint32_t caps,const char*fn){}
static int heap_caps_register_failed_alloc_callback(void(*cb)(size_t,uint32_t,const char*)){return ESP_OK;}
static int nimble_port_init(void){assert(!nimble_port_initialized&&!nimble_stop_requested);port_init_calls++;return init_rc;}
static void ble_svc_gap_init(void){}static void ble_svc_gatt_init(void){}
static void blueduck_register_services(void){}static void honeypair_register_services(void){}
static void nimble_host_task(void*arg){} // RTOS boundary; real sync callback runs below.
static void apply_ble_power_settings(void){}
static int xTaskCreatePinnedToCore(void(*fn)(void*),const char*n,int sz,void*a,int pr,void**out,int core){
 assert(nimble_port_initialized&&!nimble_stop_requested&&!nimble_host_exited);host_creates++;*out=(void*)3;ble_hs_cfg.sync_cb();return pdPASS;
}
#endif
static void vTaskDelay(int ms){
 if(cleanup_probe&&nimble_cleanup_busy){int n=port_init_calls;assert(!cym_ble_cham_acquire(997));assert(!s_bt_cham_token&&port_init_calls==n);cleanup_probes++;}
 if(nimble_stop_requested&&host_exit_on_delay)nimble_host_exited=true;
}

"""
ui_stubs=r"""
static char rendered_status[64];
static void lv_label_set_text(void*p,const char*t){if(p==s_cham_prog_lbl)snprintf(rendered_status,sizeof(rendered_status),"%s",t);}
static void s_cham_rebuild_content(cham_state_t st){}
static void s_cham_add_scan_row(void*l,const cham_scan_result_t*r,int idx){}
bool cham_poll(void){bool out=s_changed;s_changed=false;return out;}
cham_state_t cham_get_state(void){return s_state;}
const char *cham_get_status_msg(void){return s_status_msg;}
int cham_scan_result_count(void){return s_scan_count;}
const cham_scan_result_t *cham_scan_result_get(int idx){return &s_scan_results[idx];}
const cham_device_info_t *cham_get_device_info(void){return NULL;}
"""
mainnames=['bt_cancel_unreserved_discovery','cym_ble_cham_release','cym_ble_cham_acquire','ensure_ble_mode_unreserved','ensure_ble_mode','bt_scan_session_begin','bt_scan_session_start_result','bt_scan_worker_start','bt_nimble_cleanup_bounded']
chamnames=['s_callback_enter','s_callback_leave','s_callbacks_quiet','s_write_cb_process','s_write_cb','s_cccd_write_cb_process','s_cccd_write_cb','s_radio_busy','s_radio_claim','s_scan_cancel_owned','s_cham_scan_begin','s_scan_gap_cb_process','s_scan_gap_cb','s_link_event_begin','s_gap_cb','s_defer_connect_cb','cham_init','cham_scan_start','cham_scan_stop','cham_connect','cham_radio_poll','cham_disconnect']
code=pre+'\n'.join(fn(M,n) for n in mainnames)+'\n#ifdef REAL_INIT\n'+'\n'.join(fn(M,n) for n in ['bt_on_sync','bt_on_reset','bt_nimble_init'])+'\n#endif\n'+ '\n'.join(fn(C,n) for n in chamnames)
# Link payload security/ATT handler is NOT simulated. The real lifecycle prefix
# and admission helper are driven directly below; full security stays hardware.
code+=r"""

static bool airtag_scan_active,airtag_scan_ui_active;static void*airtag_scan_task_handle;
static void bt_nimble_deinit(void){bt_nimble_cleanup_bounded();}
"""+fn(M,'airtag_scan_stop')+fn(M,'s_cham_scan_btn_cb')+fn(M,'run_screen_stop_fn')+fn(M,'home_btn_event_cb')+fn(M,'nav_back_cb')+fn(M,'chameleon_screen_stop')+ui_stubs+fn(M,'s_cham_poll_timer')+r"""
static void counted_stop(void){stop_calls++;chameleon_screen_stop();}
static void clear(void){s_state=CHAM_STATE_DISCONNECTED;s_status_msg[0]=0;s_scan_count=1;s_scan_results[0].addr_type=1;s_scan_results[0].addr[0]=42;}
static void link_event(int type,int status){struct ble_gap_event e={.type=type,.connect={.status=status,.conn_handle=7}};s_gap_cb(&e,connect_arg);}
int main(int argc,char**argv){assert(argc==2||argc==3);
 for(int dbg=0;dbg<2;dbg++){debug=dbg;if(argc==3&&dbg!=(argv[2][0]=='1'))continue;clear();starts=cancels=connects=conn_cancels=terminates=deinits=creates=0;start_rc=cancel_rc=connect_rc=terminate_rc=conn_cancel_rc=init_rc=0;create_rc=pdPASS;
 if(!strcmp(argv[1],"reentry")){
#ifdef REAL_INIT
  // No lifecycle flag resets: actual successful cleanup -> claim -> actual init/sync.
  assert(nimble_initialized&&nimble_port_initialized&&!nimble_stop_requested);
  airtag_scan_stop();assert(!nimble_initialized&&!nimble_port_initialized&&nimble_stop_requested&&!nimble_cleanup_busy&&current_radio_mode==RADIO_MODE_NONE);
  assert(cym_ble_cham_acquire(301)&&"successful cleanup must permit fresh Chameleon init");
  puts("PASS reentry: completed cleanup retains stop flag, fresh production init/sync succeeds");
  assert(port_init_calls==1&&host_creates==1&&nimble_initialized&&nimble_port_initialized&&!nimble_stop_requested&&s_bt_cham_token==301);
  cym_ble_cham_release(301);
  // Actual live cleanup rejects admission before/during stop, then times out.
  cleanup_probe=true;host_exit_on_delay=false;
  assert(!bt_nimble_cleanup_bounded());assert(cleanup_probes>0);
  assert(nimble_port_initialized&&nimble_stop_requested&&!nimble_initialized&&!nimble_host_exited&&!nimble_cleanup_busy);
  assert(!cym_ble_cham_acquire(302)&&!s_bt_cham_token&&port_init_calls==1&&nimble_stop_requested);
  puts("PASS reentry: in-flight cleanup and retained-port stop timeout reject claim/init");
  // Model host exit availability, not application lifecycle flag resets; retry real stop.
  cleanup_probe=false;host_exit_on_delay=true;airtag_scan_stop();
  assert(!nimble_port_initialized&&nimble_stop_requested&&current_radio_mode==RADIO_MODE_NONE);
  assert(cym_ble_cham_acquire(303));assert(port_init_calls==2&&host_creates==2&&nimble_initialized&&!nimble_stop_requested);cym_ble_cham_release(303);
  // Failed SDK deinit keeps live port/stop flags; acquisition must not clear them.
  deinit_rc=7;airtag_scan_stop();
  assert(nimble_port_initialized&&nimble_deinit_failed&&nimble_stop_requested&&current_radio_mode==RADIO_MODE_BLE);
  assert(!cym_ble_cham_acquire(304)&&!s_bt_cham_token&&port_init_calls==2&&nimble_stop_requested&&nimble_deinit_failed);
  assert(!bt_nimble_cleanup_bounded());
  puts("PASS reentry: stop retry permits fresh init, failed deinit retains flags and rejects claim/init");
#else
  assert(0&&"reentry requires production init extraction");
#endif
 }else if(!strcmp(argv[1],"pending")){
  bt_scan_worker_busy=bt_scan_create_pending=true;assert(!ensure_ble_mode());s_cham_scan_btn_cb(NULL);assert(!s_radio_token&&!starts&&!cancels&&strstr(s_status_msg,"busy"));
  s_cham_content=s_cham_prog_lbl=(void*)1;s_cham_ui_st=s_state;s_cham_poll_timer(NULL);assert(strstr(rendered_status,"Lookout")&&strstr(rendered_status,"retry"));
  bt_scan_worker_busy=bt_scan_create_pending=false;publish_interleave=true;assert(bt_scan_worker_start()==pdPASS);publish_interleave=false;
  assert(!s_radio_token);bt_scan_worker_busy=bt_scan_create_pending=false;bt_scan_task_handle=NULL;
  create_rc=pdFAIL;assert(bt_scan_worker_start()==pdFAIL);create_rc=pdPASS;assert(!bt_scan_worker_busy);
  s_bt_scan_owner=(void*)9;s_cham_scan_btn_cb(NULL);assert(!s_radio_token&&strstr(s_status_msg,"Lookout"));s_bt_scan_owner=NULL;
  s_cham_scan_btn_cb(NULL);assert(s_radio_token&&s_scan_owned);cham_disconnect();assert(!s_radio_token&&!s_bt_cham_token);
 }else if(!strcmp(argv[1],"foreign")){
  start_rc=BLE_HS_EALREADY;cham_scan_start();assert(s_state==CHAM_STATE_ERROR&&!s_scan_owned&&!cancels);cham_radio_poll();assert(!s_radio_token&&!s_bt_cham_token&&!cancels);
  start_rc=0;clear();cham_scan_start();assert(s_scan_owned);cancel_rc=7;cham_scan_stop();assert(s_closing&&s_radio_token&&s_bt_cham_token&&s_scan_owned&&strstr(s_status_msg,"pending"));assert(!cym_ble_cham_acquire(999));
  cancel_rc=0;cham_radio_poll();assert(!s_radio_token&&!s_bt_cham_token);clear();cham_scan_start();assert(s_scan_owned);cham_disconnect();
 }else if(!strcmp(argv[1],"deferred")){
  current_radio_mode=RADIO_MODE_NONE;init_interleave=true;cham_scan_start();init_interleave=false;assert(s_radio_token);s_scan_count=1;s_scan_results[0].addr_type=1;s_scan_results[0].addr[0]=42;
  assert(cham_connect(0));uint32_t old=s_radio_token;assert(!connects&&s_connect_pending);assert(bt_scan_worker_start()==pdFAIL);assert(!bt_scan_session_begin());unsigned oldc=cancels;assert(bt_cancel_unreserved_discovery()==BLE_HS_EBUSY&&cancels==oldc);assert(!bt_nimble_cleanup_bounded()&&!deinits);
  cham_disconnect();assert(!s_radio_token);clear();cham_scan_start();assert(s_radio_token!=old);s_defer_connect_cb((void*)(uintptr_t)old);assert(!connects);cym_ble_cham_release(old);assert(s_bt_cham_token==s_radio_token);
  s_scan_count=1;s_scan_results[0].addr_type=1;s_scan_results[0].addr[0]=42;assert(cham_connect(0));now=s_defer_at;cham_radio_poll();assert(connects==1&&s_connect_inflight&&peer_seen.type==1&&peer_seen.val[0]==42);
  link_event(BLE_GAP_EVENT_CONNECT,0);assert(s_conn_handle==7&&!s_connect_inflight);assert(!bt_nimble_cleanup_bounded()&&!deinits);assert(!ensure_ble_mode());
  terminate_rc=7;cham_disconnect();assert(s_radio_token&&s_bt_cham_token&&s_conn_handle==7);terminate_rc=0;cham_radio_poll();assert(s_radio_token);link_event(BLE_GAP_EVENT_DISCONNECT,0);cham_radio_poll();assert(!s_radio_token&&!s_bt_cham_token);
 }else if(!strcmp(argv[1],"callback")){
  cham_scan_start();uint32_t old=s_radio_token;assert(s_callback_enter((void*)(uintptr_t)old,false));cham_scan_stop();assert(s_radio_token&&s_closing);s_callback_leave();cham_radio_poll();assert(!s_radio_token);
  clear();cham_scan_start();unsigned n=starts;struct ble_gap_event done={.type=BLE_GAP_EVENT_DISC_COMPLETE};s_scan_gap_cb(&done,(void*)(uintptr_t)old);assert(s_scan_owned&&!s_scan_restart_pending&&starts==n);
  struct ble_gap_event adv={.type=BLE_GAP_EVENT_DISC,.disc={.data=(const uint8_t*)"Chameleon Ultra",.length_data=15}};
  s_scan_gap_cb(&adv,(void*)(uintptr_t)s_radio_token);assert(s_scan_count==1);s_scan_gap_cb(&done,(void*)(uintptr_t)s_radio_token);assert(s_scan_restart_pending&&starts==n);cham_radio_poll();assert(starts>n&&s_scan_owned);
  assert(!s_callback_enter((void*)(uintptr_t)old,true));
  struct ble_gatt_error ge={0};s_pend_write_ok=s_ev_cccd_ok=false;s_write_cb(7,&ge,NULL,(void*)(uintptr_t)old);s_cccd_write_cb(7,&ge,NULL,(void*)(uintptr_t)old);assert(!s_pend_write_ok&&!s_ev_cccd_ok);
  s_write_cb(7,&ge,NULL,(void*)(uintptr_t)s_radio_token);s_cccd_write_cb(7,&ge,NULL,(void*)(uintptr_t)s_radio_token);assert(s_pend_write_ok&&s_ev_cccd_ok);cham_disconnect();
 }else if(!strcmp(argv[1],"errors")){
  init_rc=7;current_radio_mode=RADIO_MODE_NONE;cham_scan_start();assert(!s_radio_token&&!s_bt_cham_token&&strstr(s_status_msg,"busy"));init_rc=0;current_radio_mode=RADIO_MODE_BLE;
  clear();cham_scan_start();s_scan_count=1;cancel_rc=7;assert(!cham_connect(0)&&!connects&&s_scan_owned&&s_closing);cancel_rc=0;cham_radio_poll();assert(!s_radio_token);
  clear();cham_scan_start();s_scan_count=1;assert(cham_connect(0));connect_rc=7;now=s_defer_at;cham_radio_poll();assert(s_closing&&s_ev_error);cham_radio_poll();assert(!s_radio_token);connect_rc=0;
  clear();cham_scan_start();s_scan_count=1;assert(cham_connect(0));now=s_defer_at;cham_radio_poll();assert(s_connect_inflight);conn_cancel_rc=7;cham_disconnect();assert(s_radio_token&&s_connect_inflight);conn_cancel_rc=0;cham_radio_poll();assert(s_radio_token);link_event(BLE_GAP_EVENT_CONNECT,7);cham_radio_poll();assert(!s_radio_token);consume_error();assert(!s_closing);clear();cham_scan_start();assert(s_radio_token);cham_disconnect();
 }else if(!strcmp(argv[1],"retained")){
  current_radio_mode=RADIO_MODE_BLE;s_bt_scan_owner=(void*)9;airtag_scan_stop();assert(nimble_port_initialized&&current_radio_mode==RADIO_MODE_BLE&&!deinits);s_bt_scan_owner=NULL;
  assert(cym_ble_cham_acquire(99));airtag_scan_stop();assert(nimble_port_initialized&&current_radio_mode==RADIO_MODE_BLE&&!deinits);cym_ble_cham_release(99);
 }else if(!strcmp(argv[1],"navigation")){
  for(int route=0;route<2;route++){
   clear();cham_scan_start();s_cham_content=(void*)1;s_cham_tmr=(void*)1;g_screen_stop_fn=counted_stop;g_screen_back_fn=parent;nav_stack_depth=2;
   int oldstop=stop_calls,oldparent=parent_calls,oldhome=home_calls;
   if(route==0)home_btn_event_cb(NULL);else nav_back_cb(NULL);
   assert(stop_calls==oldstop&&s_radio_token);dispatch_navigation();
   assert(stop_calls==oldstop+1&&!g_screen_stop_fn&&!s_radio_token&&!s_cham_content&&!s_cham_tmr);
   assert(route?parent_calls==oldparent+1:home_calls==oldhome+1);
   dispatch_navigation();assert(stop_calls==oldstop+1);
  }
 }else if(!strcmp(argv[1],"legacy")){
  start_rc=BLE_HS_ENOTSUP;cham_scan_start();assert(s_scan_legacy&&s_scan_owned&&s_state==CHAM_STATE_SCANNING);cham_disconnect();
 }else assert(0);
 assert(!s_radio_token&&!s_bt_cham_token&&!s_radio_callbacks);current_radio_mode=RADIO_MODE_BLE;s_closing=false;
 }printf("PASS production Chameleon/arbiter %s debug %s\n",argv[1],argc==3?(argv[2][0]=='1'?"ON":"OFF"):"OFF/ON");}
"""
def block_at(marker):
 a=M.index(marker);i=M.index('{',a)+1;d=1
 while d:d+=(M[i]=='{')-(M[i]=='}');i+=1
 return M[a:i]
err=fn(C,'cham_poll');a=err.index('if (s_ev_error) {');i=err.index('{',a)+1;d=1
while d:d+=(err[i]=='{')-(err[i]=='}');i+=1
error_consume='static void consume_error(void){bool changed=false;'+err[a:i]+'}'
code=code.replace('static void clear(void){',error_consume+'\nstatic void clear(void){')
nav='static void dispatch_navigation(void){' +block_at('if (nav_to_menu_flag) {')+block_at('if (nav_deferred_show_fn) {')+'}'
code=code.replace('static void clear(void){',nav+'\nstatic void clear(void){')
(D/'host.c').write_text(code)
(D/'provenance.json').write_text(json.dumps({'main_sha256':hashlib.sha256(M.encode()).hexdigest(),'chameleon_sha256':hashlib.sha256(C.encode()).hexdigest(),'main_functions':mainnames,'chameleon_functions':chamnames,'limits':'security/ATT payload body not executed; link handle publication is boundary stub'},indent=2))
subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=undefined','-DEXT=1','-I'+str(R/'ESP32C5/main'),str(D/'host.c'),'-o',str(D/'host')],check=True)
results=[]
for case in ['pending','foreign','deferred','callback','errors','retained','legacy','navigation']:
 p=subprocess.run([str(D/'host'),case],capture_output=True,text=True);print(p.stdout+p.stderr,end='');results.append({'case':case,'exit_code':p.returncode})
# Existing eight scenarios retain their original SDK init boundary. The ninth
# additionally extracts actual production init and sync alongside real cleanup.
subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=undefined','-DEXT=1','-DREAL_INIT=1','-I'+str(R/'ESP32C5/main'),str(D/'host.c'),'-o',str(D/'reentry-host')],check=True)
variants=[]
for debug in ['0','1']:
 p=subprocess.run([str(D/'reentry-host'),'reentry',debug],capture_output=True,text=True);print(p.stdout+p.stderr,end='');variants.append({'debug':debug,'exit_code':p.returncode})
results.append({'case':'reentry','exit_code':0 if all(x['exit_code']==0 for x in variants) else 1,'variants':variants})
(D/'reentry-provenance.json').write_text(json.dumps({'main_sha256':hashlib.sha256(M.encode()).hexdigest(),'real_functions':['bt_nimble_cleanup_bounded','bt_nimble_init','bt_on_sync','bt_on_reset','airtag_scan_stop','cym_ble_cham_acquire','cym_ble_cham_release','ensure_ble_mode_unreserved'],'limits':'SDK port/RTOS/host-exit event boundaries fault-controlled; no live RF/security/ATT'},indent=2))
(D/'results.json').write_text(json.dumps(results,indent=2));assert all(x['exit_code']==0 for x in results),results
