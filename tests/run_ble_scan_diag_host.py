#!/usr/bin/env python3
"""Execute production Debug OFF/ON and allocation-failure instrumentation."""
from pathlib import Path
import os,re,subprocess
R=Path(__file__).resolve().parents[1];s=(R/'ESP32C5/main/main.c').read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'ble-diag';D.mkdir(parents=True,exist_ok=True)
def fn(n):
 m=re.search(r'static (?:void|uint32_t|bt_diag_counts_t) '+n+r'\([^;]*?\)\s*\{',s);assert m,n
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
pre=r"""
#include <assert.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stddef.h>
#define MALLOC_CAP_DMA 8
typedef int portMUX_TYPE;
#define portMUX_INITIALIZER_UNLOCKED 0
#define ESP_LOGI(...) (++logs)
#define TAG "host"
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
static unsigned logs,heaps;static bool debug;
static bool cym_debug_enabled(void){return debug;}
static void log_heap_stats(const char*s){if(debug)heaps++;}
static uint32_t s_bt_cb_total,s_bt_leg_events,s_bt_ext_events,s_bt_parse_fail,s_bt_blacklisted,s_bt_already_seen;
"""
a=s.index('typedef struct {\n    uint32_t callbacks, legacy, extended, parse_fail, blacklisted, duplicate;');b=s.index('static bt_diag_counts_t bt_diag_read',a)
decls=s[a:b]
post=r"""
int main(void){
 assert(bt_diag_begin()==0);bt_alloc_failed(44,MALLOC_CAP_DMA,"fixture");bt_diag_end("off",0);assert(!logs&&!heaps&&!s_bt_alloc_failures);
 debug=true;unsigned id=bt_diag_begin();assert(id&&heaps==1);
 bt_alloc_failed(44,MALLOC_CAP_DMA,"fixture");bt_alloc_failed(55,0,"fixture");assert(s_bt_alloc_failures==2&&s_bt_alloc_dma_failures==1&&s_bt_alloc_last_size==55);
 bt_diag_end("done",id);assert(logs==2&&heaps==2);bt_diag_end("duplicate",id);assert(logs==2);
 debug=false;assert(bt_diag_begin()==0);bt_alloc_failed(3,MALLOC_CAP_DMA,"fixture");assert(s_bt_alloc_failures==2);
 debug=true;id=bt_diag_begin();debug=false;bt_diag_end("off-after-on",id);assert(logs==2&&!s_bt_alloc_capture);
 puts("PASS production BLE diagnostics: debug OFF silent, ON counters, failed-allocation caps/size, one end, OFF transition");}
"""
(D/'host.c').write_text(pre+decls+fn('bt_diag_read')+fn('bt_diag_delta')+fn('bt_diag_begin')+fn('bt_diag_end')+post)
subprocess.run(['cc','-std=gnu11','-fsanitize=undefined',str(D/'host.c'),'-o',str(D/'host')],check=True);subprocess.run([str(D/'host')],check=True)
