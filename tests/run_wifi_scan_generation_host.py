#!/usr/bin/env python3
"""Execute production scanner tickets/start/event with a synthetic radio boundary."""
from pathlib import Path
import os,re,subprocess,hashlib,json
R=Path(__file__).resolve().parents[1];P=R/'ESP32C5/components/wifi_scanner/wifi_scanner.c';s=P.read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'wifi-tickets';D.mkdir(parents=True,exist_ok=True)
def function(name):
 m=re.search(r'(?:static void|void|esp_err_t|uint32_t) '+name+r'\([^;]*?\)\s*\{',s);assert m,name
 i=m.end();depth=1
 while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
pre=r"""
#include <stdatomic.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#define WIFI_EVENT 1
#define WIFI_EVENT_SCAN_DONE 2
#define MAX_SCAN_RESULTS 16
#define WIFI_SCAN_TYPE_ACTIVE 3
#define WIFI_SCAN_TYPE_PASSIVE 4
#define WIFI_PASSIVE_SCAN_DEFAULT_TIME 360
#define ESP_OK 0
#define ESP_ERR_INVALID_STATE 9
#define ESP_ERR_TIMEOUT 10
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define pdMS_TO_TICKS(x) (x)
typedef int esp_err_t;typedef int esp_event_base_t;
typedef struct{void*ssid,*bssid;int channel;bool show_hidden;int scan_type;struct{struct{int min,max;}active;int passive;}scan_time;}wifi_scan_config_t;
static volatile bool g_scan_in_progress,g_scan_done;
static _Atomic uint32_t g_scan_generation,g_scan_completed_generation;
static int g_shared_scan_results[16];static uint16_t g_shared_scan_count,g_scan_time_min=100,g_scan_time_max=300;
static int sdk_rc,starts,record_reads,last_type,last_passive;
static void cym_debug_memory_snapshot(const char*s){(void)s;}
static void esp_wifi_scan_stop(void){}
static void vTaskDelay(int n){assert(n==60);}
static int esp_wifi_scan_start(wifi_scan_config_t*c,bool block){assert(!block&&c->show_hidden);starts++;last_type=c->scan_type;last_passive=c->scan_time.passive;return sdk_rc;}
static void esp_wifi_scan_get_ap_num(uint16_t*n){*n=3;}
static void esp_wifi_scan_get_ap_records(uint16_t*n,int*r){assert(*n==3&&r==g_shared_scan_results);record_reads++;}
"""
post=r"""
int main(void){assert(!wifi_scanner_start_scan());uint32_t first=wifi_scanner_scan_generation();assert(first==1&&g_scan_in_progress&&last_type==WIFI_SCAN_TYPE_ACTIVE);
 assert(wifi_scanner_start_scan()==ESP_ERR_INVALID_STATE&&wifi_scanner_scan_generation()==first&&starts==1);
 wifi_scanner_event_handler(NULL,WIFI_EVENT,WIFI_EVENT_SCAN_DONE,NULL);assert(wifi_scanner_completed_generation()==first&&g_scan_done&&!g_scan_in_progress&&g_shared_scan_count==3&&record_reads==1);
 /* A new start between scanner and UI event handlers cannot rewrite the old completion ticket. */
 assert(!wifi_scanner_start_scan());assert(wifi_scanner_scan_generation()==2&&wifi_scanner_completed_generation()==first);
 wifi_scanner_event_handler(NULL,WIFI_EVENT,WIFI_EVENT_SCAN_DONE,NULL);assert(wifi_scanner_completed_generation()==2);
 sdk_rc=ESP_ERR_TIMEOUT;assert(wifi_scanner_start_scan()==ESP_ERR_TIMEOUT&&starts==4&&!g_scan_in_progress);assert(wifi_scanner_completed_generation()==2);
 sdk_rc=0;assert(!wifi_scanner_start_passive_scan(2000)&&last_type==WIFI_SCAN_TYPE_PASSIVE&&last_passive==1500);wifi_scanner_event_handler(NULL,WIFI_EVENT,WIFI_EVENT_SCAN_DONE,NULL);assert(wifi_scanner_completed_generation()==wifi_scanner_scan_generation());
 { /* Always run abort/reentry regression, not opt-in. */
  assert(!wifi_scanner_start_scan());uint32_t retired=wifi_scanner_scan_generation();
  wifi_scanner_abort();
  /* SDK documents SCAN_DONE after stop. Keep admission closed until A drains. */
  assert(wifi_scanner_start_scan()==ESP_ERR_INVALID_STATE);
  assert(wifi_scanner_start_passive_scan(100)==ESP_ERR_INVALID_STATE);
  assert(wifi_scanner_scan_generation()==retired);
  /* Late SDK event for the aborted scan, arriving after accepted reentry. */
  wifi_scanner_event_handler(NULL,WIFI_EVENT,WIFI_EVENT_SCAN_DONE,NULL);
  assert(wifi_scanner_completed_generation()==retired&&"aborted scan completion must not inherit new scan ticket");
  assert(!wifi_scanner_start_scan());assert(wifi_scanner_scan_generation()!=retired);
  assert(wifi_scanner_completed_generation()==retired);
  wifi_scanner_event_handler(NULL,WIFI_EVENT,WIFI_EVENT_SCAN_DONE,NULL);
  assert(wifi_scanner_completed_generation()==wifi_scanner_scan_generation());
 }
 puts("PASS production scan tickets: active/passive, busy/failed/retry, result sharing, event-to-UI interleaving");return 0;}
"""
names=['wifi_scanner_scan_generation','wifi_scanner_completed_generation','wifi_scanner_event_handler','wifi_scanner_start_scan','wifi_scanner_start_passive_scan','wifi_scanner_abort']
(D/'host.c').write_text(pre+'\n'.join(function(n) for n in names)+post)
(D/'provenance.json').write_text(json.dumps({'source_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'extracted':names},indent=2))
subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined',str(D/'host.c'),'-o',str(D/'host')],check=True)
subprocess.run([str(D/'host')],check=True)
