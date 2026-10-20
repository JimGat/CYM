#!/usr/bin/env python3
"""Production-extracted radio regressions, SDK/RTOS boundaries are synthetic, not RF proof."""
from pathlib import Path
import os,re,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];M=(R/'ESP32C5/main/main.c').read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'radio-repair';D.mkdir(parents=True,exist_ok=True)
def fn(n,src=M):
 m=re.search(r'^(?:static )?(?:void|bool|int|esp_err_t|BaseType_t) (?:IRAM_ATTR )?'+n+r'\([^;]*?\)\s*\{',src,re.M)
 assert m,n
 i=m.end();d=1
 while d:d+=(src[i]=='{')-(src[i]=='}');i+=1
 return src[m.start():i]
pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <limits.h>
#define IRAM_ATTR
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_STATE 9
#define ESP_ERR_NOT_SUPPORTED 10
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
#define portMUX_INITIALIZER_UNLOCKED 0
#define MALLOC_CAP_DMA 8
#define MALLOC_CAP_INTERNAL 0x800
#define MALLOC_CAP_8BIT 4
#define WSCOPE_CH_MAX 25
#define WIFI_PKT_MISC 2
typedef int portMUX_TYPE;typedef int esp_err_t;
typedef struct {struct{int rssi,channel;}rx_ctrl;}wifi_promiscuous_pkt_t;
typedef int wifi_promiscuous_pkt_type_t;
"""
results=[]
def run(name,code):
 p=D/(name+'.c');p.write_text(pre+code);exe=D/name
 c=subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=undefined',str(p),'-o',str(exe)],capture_output=True,text=True)
 if c.returncode==0:c=subprocess.run([str(exe)],capture_output=True,text=True)
 print(name,c.returncode,c.stdout+c.stderr,flush=True);results.append({'case':name,'exit_code':c.returncode,'output':c.stdout+c.stderr})
a=M.index('static volatile bool wscope_active');b=M.index('// Runtime canvas dims',a)
run('scope-rx-channel',M[a:b]+fn('wscope_prom_cb')+r"""
int main(void){wscope_active=true;wscope_cur_ch_idx=0;wscope_ch_peak[0]=-100;
#ifdef WSCOPE_EPOCH_STATE
 wscope_accepting=true;wscope_expected_channel=36;wscope_worker_epoch=wscope_epoch;
#endif
 wifi_promiscuous_pkt_t p={.rx_ctrl={-40,1}};wscope_prom_cb(&p,0);
 assert(wscope_ch_cnt[0]==0&&"wrong-channel packet must not be credited to software index");
 p.rx_ctrl.channel=36;wscope_prom_cb(&p,0);assert(wscope_ch_cnt[0]==1&&wscope_ch_peak[0]==-40);
 wscope_active=false;wscope_prom_cb(&p,0);assert(wscope_ch_cnt[0]==1);
 puts("PASS production Scope RX channel attribution");}
""")
run('channelizer-rejected-start',r"""
typedef int lv_event_t;
static bool wana_scanning;static int wana_ssid_count;static uint32_t wana_scan_ticket;
static void *wana_status_lbl=(void*)1;static char status[120];
static void wana_show_scanning_panel(void){}
static int wifi_scanner_start_scan(void){return 7;}
static int wifi_scanner_start_channelizer_scan(void){return 7;}
static uint32_t wifi_scanner_scan_generation(void){return 1;}
static void lv_label_set_text(void*p,const char*s){snprintf(status,sizeof(status),"%s",s);}
"""+fn('wana_rescan_btn_cb')+r"""
int main(void){wana_rescan_btn_cb(NULL);assert(!wana_scanning&&"rejected start must not wait for a nonexistent completion");assert(strstr(status,"failed"));puts("PASS production Channelizer start failure ownership");}
""")
run('channelizer-generation',r"""
typedef int lv_timer_t;typedef int wifi_ap_record_t;
#define WANA_MAX_APS 128
static bool wana_active=true,wana_scanning=true,done=true;static uint32_t wana_scan_ticket=10,completed=9;
static wifi_ap_record_t wana_aps[128];static int wana_ap_count,reads,groups,shows,result;
static void *wana_status_lbl=(void*)1;static char status[120];
static bool wifi_scanner_is_done(void){return done;}
static uint32_t wifi_scanner_completed_generation(void){return completed;}
static int wifi_scanner_result_status(void){return result;}
static bool copy_busy;
static int wifi_scanner_copy_completed(uint32_t ticket,int*p,uint16_t cap,uint16_t*n,bool*busy){assert(ticket==completed);reads++;*busy=copy_busy;*n=copy_busy||result?0:3;return copy_busy?ESP_ERR_INVALID_STATE:result;}
static int wifi_scanner_get_results(int*p,int n){reads++;return 3;}
static void wana_group_ssids(void){groups++;}static void show_wana_select_screen(void){shows++;}
static void lv_label_set_text(void*p,const char*s){snprintf(status,sizeof(status),"%s",s);}
"""+fn('wana_ui_timer_cb')+r"""
int main(void){wana_ui_timer_cb(NULL);assert(!reads&&!groups&&!shows);completed=10;wana_scanning=true;result=ESP_ERR_INVALID_STATE;wana_ui_timer_cb(NULL);assert(!wana_scanning&&!groups&&strstr(status,"failed"));
 wana_scanning=true;copy_busy=true;result=0;wana_ui_timer_cb(NULL);assert(wana_scanning&&!groups&&!shows);copy_busy=false;
 wana_scanning=true;result=0;wana_ui_timer_cb(NULL);assert(groups==1&&shows==1&&wana_ap_count==3&&!wana_scanning);puts("PASS production Channelizer ticket, SDK failure, result publication");}
""")
# The allocation hook must retain a non-allocating operational failure signal even with Debug OFF.
a=M.index('typedef struct {\n    uint32_t callbacks, legacy, extended, parse_fail, blacklisted, duplicate;');b=M.index('static bt_diag_counts_t bt_diag_read',a)
decl=M[a:b]
if 's_bt_resource_failures' not in decl:decl='static bool s_bt_resource_capture;static uint32_t s_bt_resource_failures;\n'+decl
run('ble-resource-off',decl+r"""
int main(void){s_bt_resource_capture=true;s_bt_alloc_capture=false;bt_alloc_failed(292,0x80c,"heap_caps_malloc");assert(s_bt_resource_failures==1&&"Debug OFF must not hide scan-window resource failure");s_bt_resource_capture=false;bt_alloc_failed(292,0x80c,"heap_caps_malloc");assert(s_bt_resource_failures==1);puts("PASS operational BLE allocation signal independent of Debug");}
""")
# Compile actual existing declarations with a host section marker; no replacement data model.
S=(R/'ESP32C5/components/rf_hat/src/ir_hat.c').read_text()
for psram in [0,1]:
 cap=re.search(r'^.*static ir_signal_t\s+s_cap_signal;',S,re.M).group(0)
 sig=re.search(r'^.*static ir_signal_t sig;',S,re.M).group(0)
 macro=re.search(r'#if CONFIG_BOARD_HAS_PSRAM\n.*?#endif',S,re.S)
 code=('#define CONFIG_BOARD_HAS_PSRAM %d\n'%psram)+'#include <stdint.h>\n#define EXT_RAM_BSS_ATTR __attribute__((section("ext_bss")))\n'+(macro.group(0) if macro else '')+'\ntypedef struct{uint8_t payload[4140];}ir_signal_t;\n'+cap+'\n'+sig+'\nint main(void){return 0;}\n'
 f=D/('ir-placement-%d.c'%psram);f.write_text(code);obj=f.with_suffix('.o')
 subprocess.run(['cc','-c',str(f),'-o',str(obj)],check=True)
 symbols=subprocess.check_output(['objdump','-t',str(obj)],text=True)
 good=all(('ext_bss' if psram else '.bss') in line for line in symbols.splitlines() if re.search(r'\b(s_cap_signal|sig)$',line))
 results.append({'case':'ir-placement-%d'%psram,'exit_code':0 if good else 1,'output':symbols});print('ir-placement',psram,good)
(D/'results.json').write_text(json.dumps(results,indent=2))
(D/'provenance.json').write_text(json.dumps({'main_sha256':hashlib.sha256(M.encode()).hexdigest(),'ir_sha256':hashlib.sha256(S.encode()).hexdigest()},indent=2))
assert all(x['exit_code']==0 for x in results),results
