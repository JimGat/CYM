#!/usr/bin/env python3
"""Actual Package B worker/admission extraction. Scheduled interleavings with
mock SDK primitive boundaries; not SMP, hardware, UI or emission proof.
Compile failures and arbitrary crashes never qualify as semantic mutant kills.
"""
import os, subprocess, json, hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1]
O=Path(os.environ['CYM_TEST_OUT'])/'ap-worker';O.mkdir(parents=True,exist_ok=True)
p=R/'ESP32C5/components/wifi_attacks/wifi_attacks.c';s=p.read_text()
def block(begin,end): return s[s.index(begin):s.index(end)+len(end)]
def fun(sig):
 a=s.index(sig);b=s.index('{',a);d=1;i=b+1
 while d:
  d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
idf=Path(os.environ.get('IDF_PATH','/home/dev/esp/esp-idf'))
err=idf/'components/esp_common/include/esp_err.h'
assert err.exists(),'installed esp_err.h prerequisite unavailable'
(O/'sdkconfig.h').write_text('/* Native extraction: no target configuration options enabled. */\n')

pre=r"""
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_err.h"
#define portENTER_CRITICAL(x) ((void)0)
#define portEXIT_CRITICAL(x) ((void)0)
#define xTaskNotifyGive(x) ((void)0)
typedef void *TaskHandle_t;
typedef struct {uint8_t bssid[6];char ssid[33];uint8_t channel;uint32_t last_seen;bool active;} target_bssid_t;
#define MAX_TARGET_BSSIDS 50
"""
types=block('/* >>> CYM_AP_OWNER_TYPES_BEGIN','CYM_AP_OWNER_TYPES_END */')+'\n'+block('/* >>> CYM_AP_QUEUE_TYPES_BEGIN','CYM_AP_QUEUE_TYPES_END */')
a=s.index('typedef struct {\n    ap_owner_t own;');b=s.index('} ap_ctx_t;',a)+len('} ap_ctx_t;');types+='\n'+s[a:b]
types+='\n'+block('/* >>> CYM_AP_ADMIT_TYPES_BEGIN','CYM_AP_ADMIT_TYPES_END */')
funcs='\n'.join(fun(x)for x in ['int ap_snapshot_build(', 'ap_own_state_t ap_owner_begin(', 'ap_admit_t ap_admit(', 'int ap_reqq_push(', 'int ap_reqq_pop(', 'ap_own_state_t ap_owner_suspend_result(', 'ap_own_state_t ap_owner_resume_result(', 'ap_own_state_t ap_owner_dispatch('])
globals_=r"""
static ap_ctx_t ctx,*s_apctx=&ctx;
static int s_ap_radio_owner=1;
static int starts,stops,late,stop_fail,start_fail,partial_fail;
static bool s_ap_initializing;
static bool (*s_utility_ap_cb)(void);
static int alloc_fail,task_fail,alloc_live;
static bool utility(void){return false;}
static void ap_owner_worker(void *c){(void)c;}
static void *heap_caps_calloc(size_t n,size_t sz,int caps){(void)caps;if(alloc_fail)return NULL;void*p=calloc(n,sz);if(p)alloc_live++;return p;}
static void mock_free(void*p){if(p)alloc_live--;free(p);}
#define free mock_free
#define pdPASS 1
static int xTaskCreate(void(*fn)(void*),const char*n,int sz,void*c,int pri,TaskHandle_t*h){(void)fn;(void)n;(void)sz;(void)c;(void)pri;if(task_fail)return 0;*h=(void*)1;return pdPASS;}
static void wifi_scanner_save_target_bssids(void){}
static int wifi_scanner_get_targets(target_bssid_t*t,int n){(void)n;memset(t,0,sizeof(*t));t->active=true;t->channel=6;t->bssid[0]=2;return 1;}
static int ap_ensure_worker(void);
static esp_err_t ap_start_owned(const ap_req_snapshot_t *snap);
static esp_err_t ap_stop_owned(void){++stops;return (stop_fail || (partial_fail && stops>1))?ESP_ERR_TIMEOUT:ESP_OK;}
"""
heap=(idf/'components/heap/include/esp_heap_caps.h').read_text()
pre+='\n'.join(line for line in heap.splitlines()if line.startswith(('#define MALLOC_CAP_INTERNAL ', '#define MALLOC_CAP_8BIT ')))+'\n'
actual='\n'.join(fun(x)for x in ['int ap_ensure_worker(', 'esp_err_t ap_request_start(', 'bool wifi_attacks_radio_claim(', 'void wifi_attacks_radio_release(', 'esp_err_t ap_enqueue(', 'void wifi_attacks_ap_invalidate(', 'bool ap_worker_step('])

post=r"""
#define CHECK(x) do{if(!(x)){fprintf(stderr,"SEMANTIC_FAILURE line=%d: %s\n",__LINE__,#x);return 86;}}while(0)
static esp_err_t ap_start_owned(const ap_req_snapshot_t *snap){
 ++starts;
 if(start_fail)return ESP_ERR_NO_MEM;
 if(strcmp(snap->ssid,"identity"))return ESP_FAIL;
 if(late){wifi_attacks_ap_invalidate(); if(wifi_attacks_radio_claim(3))return ESP_FAIL;}
 return ESP_OK;
}
static void reset(void){s_apctx=&ctx;s_utility_ap_cb=utility;memset(&ctx,0,sizeof(ctx));s_ap_radio_owner=1;
 ctx.own.generation=7;ctx.own.req.kind=AP_REQ_ROGUE;ctx.own.req.generation=7;
 strcpy(ctx.own.req.ssid,"identity");ctx.own.state=AP_OWN_ACTIVE;starts=stops=late=stop_fail=start_fail=partial_fail=0;}
int main(void){
 s_apctx=NULL;alloc_fail=1;CHECK(!ap_ensure_worker());CHECK(!s_apctx && !s_ap_initializing && alloc_live==0);
 alloc_fail=0;task_fail=1;CHECK(!ap_ensure_worker());CHECK(!s_apctx && alloc_live==0);
 task_fail=0;CHECK(ap_ensure_worker());CHECK(s_apctx && alloc_live==1);free(s_apctx);s_apctx=NULL;
 reset();s_ap_radio_owner=0;ctx.own.state=AP_OWN_IDLE;s_utility_ap_cb=NULL;
 CHECK(ap_request_start(AP_REQ_EVIL_TWIN,"identity",NULL,NULL,0)==ESP_ERR_INVALID_STATE);CHECK(ctx.q.count==0 && alloc_live==0);
 s_utility_ap_cb=utility;alloc_fail=1;CHECK(ap_request_start(AP_REQ_EVIL_TWIN,"identity",NULL,NULL,0)==ESP_ERR_NO_MEM);CHECK(!s_ap_radio_owner && ctx.q.count==0);
 alloc_fail=0;CHECK(ap_request_start(AP_REQ_EVIL_TWIN,"identity",NULL,NULL,0)==ESP_OK);
 CHECK(ctx.target_count==1 && ctx.targets[0].channel==6 && ctx.own.state==AP_OWN_RESUMING && alloc_live==0);
 CHECK(ap_worker_step(&ctx));CHECK(ctx.own.state==AP_OWN_ACTIVE);
 reset();ctx.own.state=AP_OWN_HELD;CHECK(ap_enqueue(AP_OP_RESUME)==ESP_OK);start_fail=partial_fail=1;
 ap_worker_step(&ctx);CHECK(ctx.own.state==AP_OWN_ERROR);CHECK(ctx.error==ESP_ERR_NO_MEM);CHECK(ctx.cleanup_error==ESP_ERR_TIMEOUT);
 reset();ctx.q.count=AP_REQQ_CAP;
 CHECK(ap_enqueue(AP_OP_SUSPEND)!=ESP_OK);CHECK(ctx.own.state==AP_OWN_ACTIVE);
 reset();ctx.own.state=AP_OWN_IDLE;
 CHECK(ap_enqueue(AP_OP_RESUME)!=ESP_OK);CHECK(ctx.q.count==0);
 reset();CHECK(ap_enqueue(AP_OP_SUSPEND)==ESP_OK);
 CHECK(ap_enqueue(AP_OP_SUSPEND)!=ESP_OK);CHECK(ctx.q.count==1);
 CHECK(ap_worker_step(&ctx));CHECK(ctx.own.state==AP_OWN_HELD);
 CHECK(ap_enqueue(AP_OP_RESUME)==ESP_OK);CHECK(ap_worker_step(&ctx));
 CHECK(starts==1 && ctx.own.state==AP_OWN_ACTIVE && ctx.own.generation==7);
 reset();ctx.own.state=AP_OWN_LIVE_UNCERTAIN;
 CHECK(ap_enqueue(AP_OP_SUSPEND)==ESP_OK);ap_worker_step(&ctx);CHECK(ctx.own.state==AP_OWN_HELD);
 ctx.own.state=AP_OWN_ERROR;CHECK(ap_enqueue(AP_OP_RESUME)==ESP_OK);ap_worker_step(&ctx);CHECK(ctx.own.state==AP_OWN_ACTIVE);
 reset();ap_reqq_push(&ctx.q,AP_OP_RESUME,6);ap_worker_step(&ctx);
 CHECK(starts==0 && stops==0);
 reset();CHECK(ap_enqueue(AP_OP_SUSPEND)==ESP_OK);wifi_attacks_ap_invalidate();
 CHECK(ctx.q.count==0);ap_worker_step(&ctx);CHECK(starts==0 && ctx.own.state==AP_OWN_IDLE);
 reset();ctx.own.state=AP_OWN_HELD;CHECK(ap_enqueue(AP_OP_RESUME)==ESP_OK);late=1;
 ap_worker_step(&ctx);CHECK(starts==1 && stops==2);CHECK(ctx.own.state==AP_OWN_IDLE);
 CHECK(wifi_attacks_radio_claim(3));ap_worker_step(&ctx);CHECK(stops==2);
 reset();wifi_attacks_ap_invalidate();stop_fail=1;ap_worker_step(&ctx);
 CHECK(ctx.own.state==AP_OWN_LIVE_UNCERTAIN);CHECK(!wifi_attacks_radio_claim(3));
 stop_fail=0;CHECK(ap_enqueue(AP_OP_SUSPEND)==ESP_OK);ap_worker_step(&ctx);CHECK(ctx.own.state==AP_OWN_IDLE);CHECK(wifi_attacks_radio_claim(3));
 for(int i=0;i<100;i++){reset();CHECK(ap_enqueue(AP_OP_SUSPEND)==ESP_OK);ap_worker_step(&ctx);
 CHECK(ap_enqueue(AP_OP_RESUME)==ESP_OK);ap_worker_step(&ctx);CHECK(ctx.q.count==0 && ctx.own.state==AP_OWN_ACTIVE);}
 puts("PASS worker admission/cancellation/retry/reservation 100 rapid cycles");return 0;
}
"""
variants=[('production',actual,False),
 ('stale-side-effects',actual.replace('req.generation == c->own.generation','true'),True),
 ('orphan-late-success',actual.replace('if (retired && !cancel) cleanup = ap_stop_owned();','if (false) rc = ap_stop_owned();'),True),
 ('forget-uncertain-owner',actual.replace('} else c->own.state = AP_OWN_LIVE_UNCERTAIN;','} else { c->own.state = AP_OWN_IDLE; s_ap_radio_owner = 0; }'),True),
 ('resume-bumps-lifetime',actual.replace('} else ap_owner_dispatch(&c->own, &req, rc == ESP_OK && cleanup == ESP_OK);','} else { ++c->own.generation; ap_owner_dispatch(&c->own, &req, rc == ESP_OK); }'),True)]
variants.append(('erase-acquisition-error',actual.replace('cleanup = ap_stop_owned(); /* retain original acquisition error separately */','cleanup = ap_stop_owned(); rc = cleanup;'),True))
expected={'stale-side-effects':'starts==0 && stops==0','orphan-late-success':'starts==1 && stops==2','forget-uncertain-owner':'ctx.own.state==AP_OWN_LIVE_UNCERTAIN','resume-bumps-lifetime':'ctx.own.state==AP_OWN_ACTIVE','erase-acquisition-error':'ctx.error==ESP_ERR_NO_MEM'}
results=[]
for name,v,mutant in variants:
 assert not mutant or v!=actual,'mutation did not match'
 d=O/name;d.mkdir(exist_ok=True);c=d/'host.c';c.write_text(pre+types+funcs+globals_+v+post)
 cmd=[os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fno-pie','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(err.parent),'-I'+str(O),str(c),'-o',str(d/'host')]
 b=subprocess.run(cmd,capture_output=True,text=True);(d/'compile.log').write_text(b.stdout+b.stderr);assert b.returncode==0,b.stderr
 b=subprocess.run([str(d/'host')],capture_output=True,text=True);(d/'run.log').write_text(b.stdout+b.stderr)
 ok=(b.returncode==86 and 'SEMANTIC_FAILURE' in b.stderr and expected[name] in b.stderr)if mutant else b.returncode==0 and 'PASS' in b.stdout
 results.append(dict(name=name,mutant=mutant,exit=b.returncode,ok=ok));print(results[-1])
(O/'results.json').write_text(json.dumps(dict(results=results,source_sha256=hashlib.sha256(p.read_bytes()).hexdigest()),indent=2))
assert all(x['ok']for x in results)
print('PASS semantic mutants',sum(x['mutant']for x in results))
