#!/usr/bin/env python3
"""Execute production report insertion/name publication and callback admission."""
from pathlib import Path
import os,re,subprocess
R=Path(__file__).resolve().parents[1];s=(R/'ESP32C5/main/main.c').read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'ble-reports';D.mkdir(parents=True,exist_ok=True)
def fn(n):
 m=re.search(r'static int '+n+r'\([^;]*?\)\s*\{',s);assert m,n
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
pre=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define MYNEWT_VAL(x) EXT
#define BLE_GAP_EVENT_DISC_COMPLETE 1
#define BLE_GAP_EVENT_DISC 2
#define BLE_GAP_EVENT_EXT_DISC 3
#define BLE_HCI_ADV_SCAN_RSP_MASK 8
#define BLE_HCI_ADV_RPT_EVTYPE_SCAN_RSP 4
#define BLE_HCI_LE_PHY_1M 1
#define BT_MAX_DEVICES 16
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
struct addr {uint8_t val[6];uint8_t type;};
struct ble_gap_disc_desc{uint8_t *data;uint8_t length_data;struct addr addr;int8_t rssi;int event_type;};
struct ble_gap_ext_disc_desc{uint8_t *data;uint8_t length_data;struct addr addr;int8_t rssi;uint8_t prim_phy;int props;};
struct ble_gap_event{int type;struct ble_gap_disc_desc disc;struct ble_gap_ext_disc_desc ext_disc;};
struct uuid{uint16_t value;};
struct ble_hs_adv_fields{uint8_t *name;int name_len;uint8_t *mfg_data;int mfg_data_len;struct uuid *uuids16;int num_uuids16;};
typedef struct{uint8_t addr[6],addr_type;int rssi,phy;char name[32];uint16_t company_id,fp_svc_uuid;uint8_t apple_sub_type;bool is_airtag,is_smarttag,is_possible_airtag,is_fast_pair,is_matter,is_eddystone,is_bthome,is_tile,is_exposure;}bt_device_info_t;
static bt_device_info_t bt_devices[BT_MAX_DEVICES];static int bt_device_count,bt_airtag_count,bt_smarttag_count,bt_possible_airtag_count,bt_tile_count;
static uint32_t s_bt_ext_events,s_bt_leg_events,s_bt_cb_total,s_bt_blacklisted,s_bt_parse_fail,s_bt_already_seen,s_bt_results_revision,s_bt_rejected_reports;
static bool bt_tracking_mode,bt_tracking_found,bt_sas_needs_update,s_bt_reports_accept,blacklist;static uint8_t bt_tracking_mac[6];static int bt_tracking_rssi;
static int s_bt_report_mux;static unsigned s_bt_reports_inflight;
static void bt_diag_end(const char*b,uint32_t i){}
static bool bt_blacklist_check(const uint8_t*a){return blacklist;}
static bool bt_lookout_is_active(void){return false;}
static void bt_lookout_on_adv(const uint8_t*a,int r,const char*n){}
static int ble_hs_adv_parse_fields(struct ble_hs_adv_fields*f,const uint8_t*d,int n){assert(s_bt_reports_inflight==1);memset(f,0,sizeof(*f));if(n){f->name=(uint8_t*)d;f->name_len=n;}return 0;}
static bool bt_is_device_found(const uint8_t*a){return bt_device_count>0;}
static int bt_find_device_index(const uint8_t*a){return bt_device_count?0:-1;}
static void bt_add_found_device(const uint8_t*a){}
static bool bt_is_apple_airtag(const void*p,int n,bool h){return false;}
static bool bt_is_possible_airtag(const void*p,int n,bool h){return false;}
static bool bt_is_samsung_smarttag(const void*p,int n){return false;}
static bool wp_is_fast_pair_adv(void*p){return false;}
static bool bt_is_matter_adv(void*p){return false;}
"""
post=r"""
int main(void){
 struct ble_gap_event e={0};e.type=EXT?BLE_GAP_EVENT_EXT_DISC:BLE_GAP_EVENT_DISC;e.disc.rssi=e.ext_disc.rssi=-42;
 bt_gap_event_callback(&e,0);assert(s_bt_cb_total==0&&s_bt_rejected_reports==1);
 s_bt_reports_accept=true;bt_gap_event_callback(&e,0);assert(bt_device_count==1&&s_bt_results_revision==1&&bt_sas_needs_update&&!s_bt_reports_inflight);
 bt_sas_needs_update=false;bt_gap_event_callback(&e,0);assert(bt_device_count==1&&s_bt_results_revision==1&&!bt_sas_needs_update);
 e.disc.event_type=BLE_HCI_ADV_RPT_EVTYPE_SCAN_RSP;e.ext_disc.props=BLE_HCI_ADV_SCAN_RSP_MASK;
 e.disc.data=e.ext_disc.data=(uint8_t*)"Late name";e.disc.length_data=e.ext_disc.length_data=9;
 bt_gap_event_callback(&e,0);assert(!strcmp(bt_devices[0].name,"Late name")&&bt_device_count==1&&s_bt_results_revision==2&&bt_sas_needs_update);
 bt_sas_needs_update=false;bt_gap_event_callback(&e,0);assert(s_bt_results_revision==2&&!bt_sas_needs_update);
 blacklist=true;bt_gap_event_callback(&e,0);assert(s_bt_blacklisted==1);blacklist=false;
 bt_tracking_mode=true;bt_gap_event_callback(&e,0);assert(bt_tracking_found&&bt_tracking_rssi==-42&&s_bt_results_revision==2);
 s_bt_reports_accept=false;unsigned before=s_bt_cb_total;bt_gap_event_callback(&e,0);assert(s_bt_cb_total==before&&!s_bt_reports_inflight);
 e.type=BLE_GAP_EVENT_DISC_COMPLETE;bt_gap_event_callback(&e,0);assert(!s_bt_reports_inflight);
 puts("PASS production BLE report admission + late-name revision + duplicate stability + tracking + final callback");}
"""
(D/'host.c').write_text(pre+fn('bt_gap_report_process')+fn('bt_gap_event_callback')+post)
for ext in [0,1]:
 for psram in [0,1]:
  subprocess.run(['cc','-std=gnu11','-fsanitize=undefined',f'-DEXT={ext}',f'-DCONFIG_BOARD_HAS_PSRAM={psram}',str(D/'host.c'),'-o',str(D/'host')],check=True)
  subprocess.run([str(D/'host')],check=True)
