#!/usr/bin/env python3
# Production BLE apply + installed target enums, injected category failures.
import os,re,subprocess,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=Path(os.environ.get("CYM_POWER_SOURCE",R));s=(S/"ESP32C5/main/main.c").read_text();IDF=Path(os.environ.get("IDF_PATH","/home/dev/esp/esp-idf"))
O=Path(os.environ["CYM_TEST_OUT"])/"power-ble";O.mkdir(parents=True,exist_ok=False)
def fn(sig):
 m=re.search(re.escape(sig)+r"[^;{}]*\)\s*\{",s);assert m,sig
 a=m.start();i=m.end();d=1
 while d:d+=(s[i]=="{")-(s[i]=="}");i+=1
 return s[a:i]

state=s[s.index("/* POWER_BLE_STATE_BEGIN */"):s.index("/* POWER_BLE_STATE_END */")]
pre=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
typedef int esp_err_t;typedef int esp_ble_power_type_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_INVALID_ARG 0x102
#define ESP_ERR_TIMEOUT 0x107
#define PWR_LVL_NORMAL 1
#define PWR_LVL_MAX 2
#define PWR_RADIO_OFF 0
#define PWR_RADIO_FAILED 2
#define PWR_RADIO_APPLIED 3
#define ESP_BLE_PWR_TYPE_DEFAULT 0
#define ESP_BLE_PWR_TYPE_ADV 1
#define ESP_BLE_PWR_TYPE_SCAN 2
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
#define heap_caps_calloc(n,s,c) calloc(n,s)
uint8_t g_pwr_lvl=1;
bool nimble_initialized=true,nimble_stop_requested;
static int invalid_category=-1,fail_category=-1,wrong_category=-1,sets,owned,retire_on_set,retire_on_get;
static esp_power_level_t current[3];
static void ble_power_retire(void);
static bool bt_transition_enter(void){if(owned)return false;owned=1;return true;}
static void bt_transition_leave(void){assert(owned);owned=0;}
esp_power_level_t esp_ble_tx_power_get(int type){if(retire_on_get){retire_on_get=0;ble_power_retire();}return type==invalid_category?(esp_power_level_t)255:current[type];}
int esp_ble_tx_power_set(int type,esp_power_level_t value){assert(owned);sets++;if(type!=wrong_category)current[type]=value;if(retire_on_set){retire_on_set=0;ble_power_retire();}return type==fail_category?ESP_FAIL:ESP_OK;}
"""
post=r"""
int main(void){
 assert(ble_power_state_init());
 for(int c=0;c<3;c++){
  s_ble_power->captured=0;sets=0;invalid_category=c;
  current[0]=ESP_PWR_LVL_N3;current[1]=ESP_PWR_LVL_P3;current[2]=ESP_PWR_LVL_P6;
  assert(ble_power_apply_requested(2)!=0 && sets==0 && !(s_ble_power->captured&(1U<<c)) && "invalid category getter cannot override; valid categories retained independently");
 }
 invalid_category=-1;s_ble_power->captured=0;assert(ble_power_apply_requested(2)==0);assert(current[0]==ESP_PWR_LVL_P9);
 assert(ble_power_apply_requested(1)==0);assert(current[0]==ESP_PWR_LVL_N3 && current[1]==ESP_PWR_LVL_P3 && current[2]==ESP_PWR_LVL_P6 && "active Max to Normal restores independent categories");
 for(int c=0;c<3;c++){fail_category=c;assert(ble_power_apply_requested(2)!=0 && ble_power_applied_level()==0 && "partial category apply is not full success");}
 fail_category=-1;assert(ble_power_apply_requested(1)==0);
 wrong_category=1;assert(ble_power_apply_requested(2)!=0 && ble_power_applied_level()==0 && "setter success with wrong readback fails");wrong_category=-1;
 assert(ble_power_apply_requested(1)==0);owned=1;sets=0;assert(ble_power_apply_requested(2)==ESP_ERR_TIMEOUT && sets==0);owned=0;
 retire_on_set=1;assert(ble_power_apply_requested(2)!=0 && ble_power_applied_level()==0 && ble_power_status()==PWR_RADIO_OFF && "reset during setter rejects stale publication");
 assert(ble_power_apply_requested(1)==0 && current[0]==ESP_PWR_LVL_N3 && "reset must not poison default with Max");
 nimble_stop_requested=true;ble_power_retire();sets=0;assert(ble_power_apply_requested(2)!=0 && sets==0 && ble_power_applied_level()==0);
 nimble_stop_requested=false;assert(ble_power_apply_requested(2)==0);assert(ble_power_apply_requested(1)==0 && current[1]==ESP_PWR_LVL_P3);
 ble_power_retire();s_ble_power->captured=0;current[0]=current[1]=current[2]=ESP_PWR_LVL_N6;
 assert(ble_power_apply_requested(2)==0 && ble_power_apply_requested(1)==0 && current[0]==ESP_PWR_LVL_N6 && "full controller generation captures new defaults");
 assert(sizeof(ble_power_state_t)<=8);printf("PASS BLE owner admission/category validity/generation CAS/defaults/failures; allocation=%zu\n",sizeof(ble_power_state_t));
}
"""
results=[]
for target,header in [("esp32","esp32"),("esp32c5","esp32c5"),("esp32s3","esp32c3")]:
 text=(IDF/"components/bt/include"/header/"include/esp_bt.h").read_text()
 enum=re.search(r"typedef enum \{[^{}]*ESP_PWR_LVL_P9[^{}]*\} esp_power_level_t;",text).group()
 defs="\n#define CONFIG_IDF_TARGET_ESP32 "+str(int(target=="esp32"))+"\n#define CONFIG_IDF_TARGET_ESP32C5 "+str(int(target=="esp32c5"))+"\n"
 d=O/target;d.mkdir();(d/"host.c").write_text(enum.join(["", "\n"])+pre+defs+state+fn("static bool pwr_ble_level_valid(")+fn("static esp_err_t ble_power_apply_requested(")+post)
 c=["cc","-std=gnu11","-g","-fsanitize=address,undefined","-fno-pie","-no-pie",str(d/"host.c"),"-o",str(d/"host")]
 b=subprocess.run(c,capture_output=True,text=True);(d/"compile.log").write_text(b.stdout+b.stderr);assert b.returncode==0,b.stderr
 r=subprocess.run([str(d/"host")],capture_output=True,text=True);(d/"run.log").write_text(r.stdout+r.stderr);print(target,r.stdout+r.stderr);results.append(dict(target=target,exit=r.returncode,command=c));
(O/"results.json").write_text(json.dumps(results,indent=2));raise SystemExit(0 if all(x["exit"]==0 for x in results)else 1)
