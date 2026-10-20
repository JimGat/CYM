#!/usr/bin/env python3
"""Run actual Scope worker/callback/tune/publication/stop with SDK boundary faults."""
from pathlib import Path
import os,re,subprocess,json
R=Path(__file__).resolve().parents[1];M=(R/'ESP32C5/main/main.c').read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'scope-lifecycle';D.mkdir(parents=True,exist_ok=True)
def fn(n):
 m=re.search(r'^static (?:void|bool) (?:IRAM_ATTR )?'+n+r'\([^;]*?\)\s*\{',M,re.M);assert m,n
 i=m.end();d=1
 while d:d+=(M[i]=='{')-(M[i]=='}');i+=1
 return M[m.start():i]
pre=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define IRAM_ATTR
#define ESP_OK 0
#define WIFI_SECOND_CHAN_NONE 0
#define WSCOPE_CH_MAX 25
#define WSCOPE_2G_N 13
#define WSCOPE_5G_N 25
#define WIFI_PKT_MISC 2
#define WIFI_PROMIS_FILTER_MASK_ALL 0xff
#define WIFI_BAND_MODE_AUTO 3
#define WIFI_BAND_MODE_5G_ONLY 2
#define WIFI_BAND_MODE_2G_ONLY 1
#define pdMS_TO_TICKS(x) (x)
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
typedef int portMUX_TYPE,esp_err_t,wifi_second_chan_t,wifi_promiscuous_pkt_type_t;
typedef void*TaskHandle_t;
typedef struct{int filter_mask;}wifi_promiscuous_filter_t;
typedef struct{struct{int channel,rssi;}rx_ctrl;}wifi_promiscuous_pkt_t;
static TaskHandle_t wscope_task_handle;
static unsigned delays,packets,published,deletes,sets,cleanups;
static int scenario,hardware_channel=1,set_rc,get_rc,start_rc,cleanup_fail,band_rc;
static bool mismatch,drain;
static int esp_wifi_set_channel(uint8_t c,int sc){sets++;if(!set_rc&&!mismatch)hardware_channel=c;return set_rc;}
static int esp_wifi_get_channel(uint8_t*c,int*sc){*c=hardware_channel;*sc=0;return get_rc;}
static int esp_wifi_set_band_mode(int m){return m==WIFI_BAND_MODE_AUTO?0:band_rc;}
static int esp_wifi_set_promiscuous_filter(const wifi_promiscuous_filter_t*f){return start_rc;}
static int esp_wifi_set_promiscuous_rx_cb(void(*cb)(void*,int)){return 0;}
static int esp_wifi_set_promiscuous(bool on){if(!on){cleanups++;if(cleanup_fail){cleanup_fail--;return 7;}}return 0;}
static void vTaskDelay(int ms);
static void vTaskDelete(void*p){assert(!p);deletes++;}
"""
a=M.index('static volatile bool wscope_active');b=M.index('// Runtime canvas dims',a)
c=M.index('static const uint8_t wscope_2g_ch[]');e=M.index('#define WSCOPE_2G_N',c)
code=pre+M[a:b]+M[c:e]+''.join(fn(n) for n in ['wifi_set_channel_verified','wscope_prom_cb','wscope_publish_sweep','wscope_worker_stop','wscope_task'])+r"""
static void vTaskDelay(int ms){
 if(drain){wscope_task_handle=NULL;return;}
 if(wscope_create_pending){assert(ms==1);wscope_task_handle=(void*)42;wscope_create_pending=false;return;}
 if(ms==10){delays++;wifi_promiscuous_pkt_t p={.rx_ctrl={wscope_expected_channel,-50}};
  wscope_prom_cb(&p,0);packets++;p.rx_ctrl.channel=255;wscope_prom_cb(&p,0);
  if(delays==2&&scenario==1){wscope_5g_mode=true;wscope_epoch++;wscope_accepting=false;wscope_sweep_done=false;}
  if(delays==2&&scenario==2){wscope_active=false;wscope_epoch++;wscope_accepting=false;}
 }
 if(ms==1&&wscope_sweep_done){published++;assert(wscope_ready_cnt[0]==(scenario==3?0:12));
  assert(wscope_ready_rejected==(scenario==3?WSCOPE_2G_N:0));wscope_active=false;}
}
int main(void){
 hardware_channel=36;set_rc=7;assert(!wifi_set_channel_verified(36));set_rc=0;mismatch=true;assert(!wifi_set_channel_verified(40));mismatch=false;get_rc=7;assert(!wifi_set_channel_verified(40));get_rc=0;assert(wifi_set_channel_verified(40));
 for(scenario=0;scenario<6;scenario++){
  if(!CONFIG_SOC_WIFI_SUPPORT_5G&&scenario==1)continue;
  delays=packets=published=deletes=sets=cleanups=0;wscope_active=true;wscope_epoch++;wscope_sweep_done=false;wscope_5g_mode=false;wscope_error=0;
  wscope_create_pending=scenario==0;wscope_task_handle=(void*)42;
  set_rc=scenario==3?7:0;start_rc=scenario==4?7:0;cleanup_fail=scenario==5?2:0;
  wscope_task(NULL);assert(!wscope_task_handle&&!wscope_accepting&&deletes==1);
  if(scenario==2)assert(!published&&!wscope_sweep_done);
  else if(scenario==4)assert(wscope_error==7&&!published);
  else assert(published==1);
  if(scenario==1)assert(wscope_5g_mode&&wscope_ready_cnt[24]==12);
  if(scenario==5)assert(cleanups==3&&wscope_error==7);
 }
 wscope_active=true;wscope_worker_epoch=wscope_epoch;wscope_ch_cnt[0]=3;assert(wscope_publish_sweep(wscope_epoch));wscope_ch_cnt[0]=7;assert(wscope_ready_cnt[0]==3);
 ++wscope_epoch;wscope_sweep_done=false;assert(!wscope_publish_sweep(wscope_epoch-1)&&!wscope_sweep_done);
 wscope_task_handle=(void*)42;assert(!wscope_worker_stop()&&wscope_task_handle);drain=true;assert(wscope_worker_stop()&&!wscope_task_handle);
 puts("PASS production Scope: scheduling, RX attribution, tune errors/readback, epochs, immutable sweeps, cancellation, setup/cleanup faults, retained ownership");}
"""
# UI band changes invalidate ownership; they must not erase a newly-started worker epoch.
toggle=fn('wscope_band_toggle_cb')
assert 'wscope_ch_peak' not in toggle and 'wscope_ch_cnt' not in toggle
(D/'host.c').write_text(code);results=[]
for c5 in [0,1]:
 exe=D/('host-%d'%c5)
 subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=undefined','-DCONFIG_SOC_WIFI_SUPPORT_5G=%d'%c5,str(D/'host.c'),'-o',str(exe)],check=True)
 p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=15);print(c5,p.returncode,p.stdout+p.stderr);results.append({'c5':c5,'exit_code':p.returncode,'output':p.stdout+p.stderr})
(D/'results.json').write_text(json.dumps(results,indent=2));assert all(x['exit_code']==0 for x in results)
