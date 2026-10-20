#!/usr/bin/env python3
"""Execute production Clock service startup and cooperative owner helpers."""
from pathlib import Path
import os, re, subprocess, resource
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
r=Path(__file__).resolve().parents[1];e=Path(os.environ.get('CYM_TEST_OUT','/home/dev/projects/cym-targeted-refactor-20261017'));os.environ['TMPDIR']=str(e)
s=(r/'ESP32C5/main/main.c').read_text()
def function(name):
    text=s
    baseline=os.environ.get('CYM_CLOCK_RADIO_BASELINE')
    if baseline and name in ['ensure_wifi_mode','ensure_ble_mode']:
        text=Path(baseline).read_text()
    match=re.search(r'^static (?:void|bool) '+re.escape(name)+r'\([^;]*?\)\s*\{',text,re.M)
    if not match: raise RuntimeError('missing production definition: '+name)
    start=match.start()
    brace=text.index('{',start);depth=1;i=brace+1
    while depth:
        depth+=(text[i]=='{')-(text[i]=='}');i+=1
    return text[start:i]
names=['clock_mdns_release','ntp_start_mdns_and_server']
if 'static void clock_network_release(' in s: names+=['clock_network_release','clock_network_cleanup_poll','clock_stop','clock_radio_admit','clock_radio_reset_admit','clock_defer_radio_navigation','clock_cancel_radio_navigation','clock_radio_handoff_poll','ensure_wifi_mode','ensure_ble_mode','clock_attack_route_uses_radio']
if 'static bool ensure_ble_mode_unreserved(' in s: names.insert(names.index('ensure_ble_mode'),'ensure_ble_mode_unreserved')
names=['bt_transition_enter','bt_transition_leave']+names+['ensure_wifi_mode_transition','ensure_ble_mode_transition']
prod='\n'.join(function(n) for n in names)
code=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define bt_stage(s,r) ((void)0)
#define BOARD_TIME_HAS_MDNS 1
#define CONFIG_BOARD_HAS_5GHZ 1
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_TIMEOUT 0x107
#define ESP_ERR_NO_MEM 0x101
#define ESP_ERR_INVALID_STATE 0x103
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 4
#define WIFI_MODE_STA 1
#define WIFI_BAND_MODE_AUTO 0
#define CLOCK_MODE_DISPLAY_ONLY 0
#define CLOCK_MODE_AP_NTP 1
#define CLOCK_MODE_CLIENT_NTP 2
#define NTP_PUBLIC_IDLE 0
#define pdMS_TO_TICKS(n) (n)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
#define CYM_DEBUG_LOGI(...) ((void)0)
typedef int esp_err_t;
typedef int clock_mode_t;
typedef void *TaskHandle_t;
static TaskHandle_t s_ntp_wifi_task;
static atomic_bool s_ntp_stopping,s_clock_radio_reserved,s_clock_idle_reset_pending;
static _Atomic(TaskHandle_t) s_clock_radio_task;
static void (*s_clock_deferred_radio_fn)(void);
static TaskHandle_t current_task=(void *)9;
static TaskHandle_t xTaskGetCurrentTaskHandle(void) { return current_task; }
static bool clock_radio_admit(void),clock_radio_reset_admit(void);
static void clock_stop(void),clock_network_cleanup_poll(void);
static int resets,radio_writes,ble_inits,wifi_inits,new_calls;
static void radio_reset_to_idle(void) { if(clock_radio_reset_admit()){resets++;} }
static void new_ble(void);
static void new_wifi(void);

static _Atomic(const char *) s_ntp_mdns_status;
static bool s_ntp_mdns_ok,s_ntp_mdns_owned,s_ntp_udp_ok,s_ntp_wifi_connected,s_ntp_wifi_failed;
static int s_clock_mode=CLOCK_MODE_AP_NTP,s_ntp_public_state;
static char s_ntp_ip_str[20],s_ntp_ap_ssid[24];
static int fail, cancel_at, calls, advertised, freed, ntp_started, stopped, running, deletes, wait_calls;
static int64_t now;
enum { eRunning, eSuspended };
static int phase;
static bool s_ntp_clock_active;
static int s_ntp_saved_brightness=70,brightness,timer_deleted;
static void *s_ntp_ui_timer,*s_ntp_time_lbl,*s_ntp_date_lbl,*s_ntp_source_lbl,*s_ntp_ip_lbl,*s_ntp_host_lbl,*s_ntp_service_lbl,*s_ntp_age_lbl,*s_ntp_uncert_lbl,*s_ntp_req_lbl,*s_ntp_offset_lbl,*s_ntp_network_lbl,*s_clock_reliability_lbl,*s_clock_caps_lbl,*s_clock_maidenhead_lbl,*s_ntp_retry_btn;
static void lv_timer_del(void *p) { assert(p);timer_deleted++; }
static void set_backlight_percent(int n) { brightness=n; }

static int eTaskGetState(TaskHandle_t h) { assert(h);return phase; }
static void vTaskDelete(TaskHandle_t h) { assert(h && phase==eSuspended);deletes++; }
static bool cym_debug_enabled(void) { return false; }
static const char *esp_err_to_name(int e) { (void)e;return "mock"; }
static size_t heap_caps_get_free_size(unsigned c) { (void)c;return 1024; }
static size_t heap_caps_get_largest_free_block(unsigned c) { (void)c;return 512; }
static int boundary(int which) { calls++;if(cancel_at==which)s_ntp_stopping=true;return fail==which?ESP_FAIL:ESP_OK; }
static int cym_ntp_server_start(void) { assert(calls==0);int rc=boundary(1);ntp_started=rc==0;return rc; }
static int mdns_init(void) { assert(ntp_started);return boundary(2); }
static int mdns_hostname_set(const char *n) { assert(!strcmp(n,"cym-ntp"));return boundary(3); }
static int mdns_service_add(const char *a,const char *b,const char *c,int p,void *d,int n) { (void)a;(void)b;(void)c;(void)p;(void)d;(void)n;assert(!s_ntp_stopping);advertised++;return boundary(4); }
static int mdns_free_wait(void) { freed++;return ESP_OK; }
static int cym_ntp_server_stop_wait(uint32_t ms) { assert(ms==0);wait_calls++;if(running)return ESP_ERR_TIMEOUT;stopped++;return ESP_OK; }
static void vTaskDelay(unsigned ms) { assert(ms);now+=100000;running=0; }
static int64_t esp_timer_get_time(void) { return now; }
static int esp_wifi_set_mode(int mode) { (void)mode;assert(!running);radio_writes++;return 0; }
static int esp_wifi_disconnect(void) { assert(!running);radio_writes++;return 0; }
static int esp_wifi_set_band_mode(int mode) { (void)mode;radio_writes++;return 0; }

#define CONFIG_IEEE802154_ENABLED 0
#define MALLOC_CAP_DMA 8
#define WIFI_IF_STA 0
#define WIFI_COUNTRY_POLICY_MANUAL 1
#define WIFI_COUNTRY_POLICY_AUTO 2
#define RADIO_MODE_NONE 0
#define RADIO_MODE_WIFI 1
#define RADIO_MODE_BLE 2
static bool nimble_port_initialized,nimble_initialized,nimble_stop_requested,wifi_initialized;
static TaskHandle_t s_bt_transition_owner;static unsigned s_bt_transition_depth;static bool s_bt_scan_api_busy;
static bool ensure_wifi_mode_transition(void),ensure_ble_mode_transition(void);
static void *s_bt_scan_owner;
static void *wardrive_task_handle;static bool wardrive_active,wardrive_task_done,wdp_ble_cleanup_pending;
static uint32_t s_bt_cham_token;
static bool bt_scan_worker_busy,bt_scan_create_pending,nimble_cleanup_busy;
static int current_radio_mode;
typedef struct { char cc[3];int schan,nchan,policy; } wifi_country_t;
typedef struct { int dummy; } wifi_config_t;
static bool bt_nimble_cleanup_bounded(void) { radio_writes++;return true; }
static void _ot_ble_dwell_end(void) { radio_writes++; }
static void bt_nimble_deinit(void) { radio_writes++; }
static int bt_nimble_init(void) { assert(!s_clock_radio_reserved);ble_inits++;nimble_initialized=true;return 0; }
static int wifi_cli_init(void) { wifi_inits++;radio_writes++;return 0; }
static int esp_wifi_set_config(int i,void *p) { (void)i;(void)p;radio_writes++;return 0; }
static int esp_wifi_start(void) { radio_writes++;return 0; }
static int esp_wifi_stop(void) { radio_writes++;return 0; }
static int esp_wifi_deinit(void) { radio_writes++;return 0; }
static int esp_wifi_set_country(void *p) { (void)p;radio_writes++;return 0; }
static void esp_restart(void) { assert(0); }
static void apply_wifi_power_settings(void) { }
static void heap_caps_print_heap_info(unsigned c) { (void)c; }
static void log_heap_stats(const char *p) { (void)p; }
__PRODUCTION__
static void new_ble(void) { assert(!s_clock_radio_reserved);if(ensure_ble_mode())new_calls++; }
static void new_wifi(void) { assert(!s_clock_radio_reserved);if(ensure_wifi_mode())new_calls++; }
int main(int argc,char **argv) {
    assert(argc==2);int c=atoi(argv[1]);
    if(c<=4)fail=c;
    if(c>=11 && c<=14)cancel_at=c-10;
    if(c==20)s_ntp_stopping=true;
    if(c<30) {
        ntp_start_mdns_and_server();
        assert(!s_ntp_mdns_ok || s_ntp_udp_ok);
        if(fail==1 || c==20)assert(!advertised && !s_ntp_mdns_ok);
        if(fail>=2)assert(!s_ntp_mdns_ok && !s_ntp_mdns_owned && freed==1);
        if(cancel_at && cancel_at<4)assert(!advertised);
        if(!fail && !cancel_at && c!=20)assert(s_ntp_mdns_ok && advertised==1);
    }
__OWNER_CASES__
    printf("clock-case-%d\n",c);return 0;
}
"""
owner=r"""
    if(c==30) {
        s_ntp_stopping=true;s_ntp_wifi_task=(void *)1;phase=eRunning;
        clock_network_cleanup_poll();assert(!deletes && s_ntp_wifi_task && s_ntp_stopping);
        phase=eSuspended;clock_network_cleanup_poll();assert(deletes==1 && !s_ntp_wifi_task && !s_ntp_stopping);
    }
    if(c==31) {
        s_ntp_stopping=true;s_ntp_mdns_owned=true;running=1;
        clock_network_release(s_clock_mode,true);assert(freed==1 && stopped==1 && wait_calls>=2);
    }
    if(c==32) {
        s_ntp_clock_active=true;s_ntp_wifi_task=(void *)1;phase=eRunning;
        s_ntp_ui_timer=(void *)2;s_ntp_time_lbl=(void *)3;
        clock_stop();
        assert(s_ntp_stopping && s_ntp_wifi_task && !deletes && !freed && !wait_calls);
        assert(!s_ntp_clock_active && !s_ntp_ui_timer && !s_ntp_time_lbl);
        assert(timer_deleted==1 && brightness==70);
        phase=eSuspended;clock_network_cleanup_poll();assert(!s_ntp_stopping && deletes==1);
    }
    if(c==33) {
        s_clock_mode=CLOCK_MODE_DISPLAY_ONLY;s_ntp_clock_active=true;
        clock_stop();assert(!s_ntp_stopping && !freed && !wait_calls && !deletes);
    }

    if(c>=34 && c<=39) {
        assert(clock_attack_route_uses_radio("BLE Scan") && clock_attack_route_uses_radio("Scan"));
        assert(clock_attack_route_uses_radio("Handshakes"));
        assert(!clock_attack_route_uses_radio("Saved Clones") && !clock_attack_route_uses_radio("Browse Networks"));
        assert(!clock_attack_route_uses_radio("BT Attacks") && !clock_attack_route_uses_radio("List Wizard"));
        assert(!clock_attack_route_uses_radio("Unknown offline page with a long display name"));

        s_ntp_stopping=true;s_ntp_wifi_task=(void *)1;phase=eRunning;
        s_clock_radio_reserved=true;s_clock_radio_task=(void *)1;
        assert(!ensure_wifi_mode() && !ensure_ble_mode() && !radio_writes && !ble_inits && !wifi_inits);
        radio_reset_to_idle();assert(!resets && s_clock_idle_reset_pending);
        assert(clock_defer_radio_navigation(new_ble));
        clock_radio_handoff_poll();assert(!new_calls && !resets && !radio_writes && !deletes);
        if(c==34 || c==35) {
            // Delayed old NTP retains the reservation; only old owner may restore.
            current_task=(void *)1;assert(clock_radio_admit());running=1;
            clock_network_release(c==34?CLOCK_MODE_AP_NTP:CLOCK_MODE_CLIENT_NTP,true);
            assert(wait_calls>=2 && radio_writes && !new_calls && s_clock_radio_reserved);
            current_task=(void *)9;
        }
        if(c==36) { clock_cancel_radio_navigation(); }
        if(c==37) { assert(clock_defer_radio_navigation(new_wifi)); }
        if(c==38) {
            clock_network_release(CLOCK_MODE_AP_NTP,false);
            assert(!radio_writes && !wait_calls && !freed);
        }
        phase=eSuspended;clock_radio_handoff_poll();
        assert(!s_clock_radio_reserved && !s_clock_idle_reset_pending && !s_clock_radio_task && deletes==1 && resets==1);
        if(c==36)assert(!new_calls);else assert(new_calls==1);
        clock_radio_handoff_poll();assert(resets==1 && deletes==1 && new_calls<=1);
    }
""" if len(names)>1 else ''
p=e/'ntp_clock_owner_generated.c';p.write_text(code.replace('__PRODUCTION__',prod).replace('__OWNER_CASES__',owner))
b=e/'ntp_clock_owner_host'
subprocess.run(['cc','-std=c11','-D_DEFAULT_SOURCE','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-variable',str(p),'-o',str(b)],check=True)
cases=[0,1,2,3,4,11,12,13,14,20]+([30,31,32,33,34,35,36,37,38,39] if len(names)>1 else [])
for c in cases: subprocess.run([str(b),str(c)],check=True)
print(f'PASS {len(cases)} production Clock owner/startup cases')
