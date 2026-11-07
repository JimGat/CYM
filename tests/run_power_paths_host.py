#!/usr/bin/env python3
# Package D production-path regression tests; no RF or hardware.
import os, subprocess, json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
O=Path(os.environ["CYM_TEST_OUT"])/"power-paths";O.mkdir(parents=True,exist_ok=False)
def extract(s,sig):
 a=s.index(sig);b=s.index("{",a);i=b+1;depth=1
 while depth:
  depth+=(s[i]=="{")-(s[i]=="}");i+=1
 return s[a:i]
s=(Path(os.environ.get("CYM_POWER_SOURCE",R))/"ESP32C5/components/wifi_cli/wifi_common.c").read_text()
state=s[s.index("/* POWER_WIFI_STATE_BEGIN */"):s.index("/* POWER_WIFI_STATE_END */")]
func=extract(s,"static esp_err_t wifi_power_apply_level(")+"\n"+extract(s,"esp_err_t wifi_power_apply_requested(")
pre=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>
typedef int esp_err_t;typedef int wifi_init_config_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_INVALID_ARG 0x102
#define ESP_ERR_TIMEOUT 0x107
#define ESP_ERR_WIFI_NOT_INIT 0x3001
#define ESP_ERR_WIFI_NOT_STARTED 0x3002
#define PWR_LVL_NORMAL 1
#define PWR_LVL_MAX 2
#define PWR_RADIO_OFF 0
#define PWR_RADIO_BUSY 1
#define PWR_RADIO_FAILED 2
#define PWR_RADIO_APPLIED 3
#define WIFI_PS_NONE 0
#define WIFI_PS_MIN_MODEM 1
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
static int allocation_fail;
#define heap_caps_calloc(n,s,c) (allocation_fail?NULL:calloc(n,s))
#define heap_caps_free free
uint8_t g_pwr_lvl=1;
static int get_rc,set_rc,ps_rc,tx=80,sets,stops,inits,init_default=80,read_fail,deinit_rc;
static int overlap,blocked,drain,inside_setter;
void power_policy_notify(void){}
void vTaskDelay(int ticks){(void)ticks;__atomic_store_n(&drain,1,__ATOMIC_RELEASE);usleep(1000);}
int esp_wifi_init(const wifi_init_config_t*c){(void)c;assert(!inside_setter);inits++;tx=init_default;return 0;}
int esp_wifi_start(void){assert(!inside_setter);return 0;}
int esp_wifi_stop(void){assert(!inside_setter && "teardown cannot overlap setter");stops++;return 0;}
int esp_wifi_deinit(void){assert(!inside_setter);return deinit_rc;}
int esp_wifi_get_max_tx_power(int8_t*p){*p=tx;return get_rc || (read_fail && sets)?ESP_FAIL:ESP_OK;}
int cym_wifi_init(const wifi_init_config_t*);
int esp_wifi_set_max_tx_power(int8_t p){
 __atomic_store_n(&inside_setter,1,__ATOMIC_RELEASE);
 if(overlap){overlap=0;int n=inits;assert(cym_wifi_init(NULL)!=0 && inits==n && "overlapping init must not reach SDK");}
 if(__atomic_load_n(&blocked,__ATOMIC_ACQUIRE))while(!__atomic_load_n(&drain,__ATOMIC_ACQUIRE))usleep(1000);
 sets++;if(!set_rc)tx=p;__atomic_store_n(&inside_setter,0,__ATOMIC_RELEASE);return set_rc;
}
int esp_wifi_set_ps(int p){(void)p;return ps_rc;}
"""
post=r"""
void*apply_thread(void*p){(void)p;assert(wifi_power_apply_requested(2)==0);return NULL;}
int main(void){
 assert(wifi_power_apply_requested(2)!=0 && sets==0 && "off request must not call setters");
 allocation_fail=1;assert(cym_wifi_init(NULL)!=0 && inits==0 && "no SDK fallback after lifecycle allocation refusal");allocation_fail=0;
 assert(cym_wifi_init(NULL)==0 && cym_wifi_start()==0);
 get_rc=-1;assert(wifi_power_apply_requested(2)!=0 && sets==0 && "getter failure rejects override");
 get_rc=0;assert(wifi_power_apply_requested(2)==0 && tx==80+2);
 assert(wifi_power_apply_requested(1)==0 && tx==80 && "active Max to Normal restores captured default");
 assert(wifi_power_apply_requested(2)==0);assert(cym_wifi_stop()==0);
 assert(wifi_power_applied_level()==0 && wifi_power_status()==PWR_RADIO_OFF && "no stale claim after retirement");
 assert(wifi_power_apply_requested(1)!=0);assert(cym_wifi_start()==0);
 assert(wifi_power_apply_requested(1)==0 && tx==80 && "plain restart must not recapture retained Max");
 assert(wifi_power_apply_requested(2)==0);deinit_rc=-1;assert(cym_wifi_deinit()!=0 && wifi_power_applied_level()==0 && wifi_power_status()==PWR_RADIO_FAILED);
 assert(cym_wifi_start()==0 && wifi_power_apply_requested(1)==0 && tx==80 && "failed deinit must not lose baseline or recapture Max");deinit_rc=0;
 assert(cym_wifi_deinit()==0);init_default=68;assert(cym_wifi_init(NULL)==0 && cym_wifi_start()==0);
 assert(wifi_power_apply_requested(2)==0);assert(wifi_power_apply_requested(1)==0 && tx==68 && "full new generation captures new default");
 set_rc=-1;assert(wifi_power_apply_requested(2)!=0 && wifi_power_applied_level()==0);set_rc=0;
 ps_rc=-1;assert(wifi_power_apply_requested(2)!=0 && wifi_power_applied_level()==0);ps_rc=0;
 read_fail=1;assert(wifi_power_apply_requested(2)!=0 && wifi_power_applied_level()==0);read_fail=0;
 overlap=1;assert(wifi_power_apply_requested(2)==0);assert(wifi_power_apply_requested(1)==0 && tx==68);
 __atomic_store_n(&blocked,1,__ATOMIC_RELEASE);__atomic_store_n(&drain,0,__ATOMIC_RELEASE);
 pthread_t thread;assert(!pthread_create(&thread,NULL,apply_thread,NULL));
 while(!__atomic_load_n(&inside_setter,__ATOMIC_ACQUIRE))usleep(1000);
 assert(cym_wifi_stop()==0);assert(!pthread_join(thread,NULL));
 assert(wifi_power_applied_level()==0 && "teardown invalidates drained apply result");
 assert(cym_wifi_start()==0);assert(wifi_power_apply_requested(1)==0 && tx==68);
 assert(sizeof(wifi_power_state_t)<=16 && "retained lifecycle allocation budget");
 printf("PASS WiFi production adapter: active transitions/off-start/teardown drain/overlapping init/getter+setter failures/default generation; allocation=%zu\n",sizeof(wifi_power_state_t));
}
"""
p=O/"wifi.c";p.write_text(pre+state+func+post)
c=["cc","-std=gnu11","-pthread","-g","-fsanitize=address,undefined","-fno-pie","-no-pie",str(p),"-o",str(O/"wifi")]
b=subprocess.run(c,capture_output=True,text=True);(O/"compile.log").write_text(b.stdout+b.stderr);assert b.returncode==0,b.stderr
r=subprocess.run([str(O/"wifi")],capture_output=True,text=True,timeout=30);(O/"run.log").write_text(r.stdout+r.stderr)
(O/"results.json").write_text(json.dumps(dict(command=c,exit=r.returncode,stdout=r.stdout,stderr=r.stderr),indent=2))
print(r.stdout+r.stderr);raise SystemExit(r.returncode)
