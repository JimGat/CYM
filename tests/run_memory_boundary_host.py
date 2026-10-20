"""Execute actual production debug memory and BLE counter helpers with host fakes."""
from pathlib import Path
import os,re,resource,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'ESP32C5/main/main.c').read_text()
def extract(name):
    m=re.search(r'^static (?:void|bool|uint32_t|bt_diag_counts_t) '+name+r'\([^;]*?\)\s*\{',source,re.M)
    if not m: raise RuntimeError(name)
    i=m.end(); depth=1
    while depth:
        depth+=(source[i]=='{')-(source[i]=='}');i+=1
    return source[m.start():i]
helpers='\n'.join(extract(n) for n in ['log_heap_stats','bt_diag_read','bt_diag_delta','bt_diag_begin','bt_diag_end'])
typedef=re.search(r'typedef struct \{\s*uint32_t callbacks, legacy, extended, parse_fail, blacklisted, duplicate;\s*\} bt_diag_counts_t;',source)[0]
text=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
#define MALLOC_CAP_DMA 4
#define MALLOC_CAP_SPIRAM 8
#define TAG "host"
static bool debug;
static int queries,logs;
static char lines[12][1024];
static bool cym_debug_enabled(void) { return debug; }
static size_t heap_caps_get_free_size(unsigned c) { queries++;return 1000+c; }
static size_t heap_caps_get_largest_free_block(unsigned c) { queries++;return 100+c; }
static size_t heap_caps_get_minimum_free_size(unsigned c) { queries++;return 10+c; }
static void log_line(const char *tag,const char *fmt,...) {
    (void)tag; assert(logs<12);va_list ap;va_start(ap,fmt);
    vsnprintf(lines[logs++],sizeof(lines[0]),fmt,ap);va_end(ap);
}
#define ESP_LOGI(...) log_line(__VA_ARGS__)
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
static int s_bt_diag_mux;
static volatile uint32_t s_bt_cb_total,s_bt_leg_events,s_bt_ext_events,s_bt_parse_fail,s_bt_blacklisted,s_bt_already_seen;
__TYPEDEF__
static bt_diag_counts_t s_bt_diag_start;
static uint32_t s_bt_diag_id;
static bool s_bt_diag_active;
static bool s_bt_alloc_capture;
static uint32_t s_bt_alloc_start,s_bt_alloc_dma_start,s_bt_rejected_start;
static uint32_t s_bt_alloc_failures,s_bt_alloc_dma_failures,s_bt_alloc_last_size,s_bt_alloc_last_caps,s_bt_rejected_reports;
__HELPERS__
int main(void) {
    log_heap_stats("off");assert(!queries && !logs);
    assert(!bt_diag_begin());bt_diag_end("off",0);assert(!queries && !logs);
    debug=true;log_heap_stats("matched");assert(queries==7 && logs==1);
    assert(strstr(lines[0],"int_free=1003 int_largest=103 int_min=13 dma_free=1004 dma_largest=104 psram_free=1008 psram_largest=108"));
    bt_diag_counts_t a={.callbacks=UINT32_MAX-1,.legacy=12,.extended=6,.parse_fail=8,.blacklisted=2,.duplicate=9};
    bt_diag_counts_t b={.callbacks=2,.legacy=14,.extended=8,.parse_fail=11,.blacklisted=3,.duplicate=12};
    bt_diag_counts_t d=bt_diag_delta(b,a);
    assert(d.callbacks==4 && d.legacy==2 && d.extended==2 && d.parse_fail==3 && d.blacklisted==1 && d.duplicate==3);
    s_bt_cb_total=100;s_bt_leg_events=90;s_bt_ext_events=10;
    s_bt_parse_fail=20;s_bt_blacklisted=3;s_bt_already_seen=50;
    uint32_t id=bt_diag_begin();assert(id && s_bt_diag_active);
    assert(!bt_diag_begin()); // overlapping failed start must not replace baseline
    s_bt_cb_total+=6;s_bt_leg_events+=4;s_bt_ext_events+=2;
    s_bt_parse_fail+=3;s_bt_blacklisted+=1;s_bt_already_seen+=3;
    bt_diag_end("wrong-generation",id+1);assert(s_bt_diag_active);
    bt_diag_end("cancel-return",id);assert(!s_bt_diag_active);
    assert(strstr(lines[logs-2],"callbacks=6 legacy=4 extended=2 parse_fail=3 blacklisted=1 duplicate=3"));
    assert(strstr(lines[logs-2],"overlapping counters; boundary deltas, not RF proof"));
    int oldlogs=logs;bt_diag_end("gap-complete",0);assert(logs==oldlogs);
    assert(bt_diag_begin());debug=false;bt_diag_end("debug-switched-off",0);
    assert(!s_bt_diag_active && logs==oldlogs+1);
    puts("PASS production memory gating/classes; BLE snapshot/delta/wrap/overlap/end gating");
}
""".replace('__TYPEDEF__',typedef).replace('__HELPERS__',helpers)
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
with tempfile.TemporaryDirectory(prefix='memory-host-',dir=os.environ.get('TMPDIR')) as work:
    p=Path(work);(p/'test.c').write_text(text)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
