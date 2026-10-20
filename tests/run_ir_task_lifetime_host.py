#!/usr/bin/env python3
"""Extract task-only IR replay and fault its allocation/stop boundaries; no RF proof."""
from pathlib import Path
import os,re,subprocess,json
R=Path(__file__).resolve().parents[1];M=(R/'ESP32C5/components/rf_hat/src/ir_hat.c').read_text();D=Path(os.environ['CYM_TEST_OUT'])/'ir-task-lifetime';D.mkdir(parents=True,exist_ok=True)
m=re.search(r'(void|esp_err_t) ir_hat_tvbgone\([^;]*?\)\s*\{',M);assert m
i=m.end();d=1
while d:d+=(M[i]=='{')-(M[i]=='}');i+=1
fn=M[m.start():i];call='ir_hat_tvbgone(NULL,NULL)' if m.group(1)=='esp_err_t' else '(ir_hat_tvbgone(NULL,NULL),0)'
pre=r"""
#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_ERR_NO_MEM 7
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
#define IR_TASK_DATA_ATTR
#define ESP_LOGE(...) ((void)0)
#define IR_HAT_NAME_LEN 20
#define IR_CARRIER_DUTY 33
#define TVBG_COUNT 3
#define TVBG_REPEATS 2
#define TVBG_REPEAT_GAP_MS 1
#define TVBG_CODE_GAP_MS 2
#define pdMS_TO_TICKS(x) (x)
typedef void(*ir_hat_progress_cb_t)(int,int,void*);
typedef struct{char name[20];int freq_hz,duty_cycle,count;uint32_t times_us[1024];}ir_signal_t;
typedef struct{int freq,count;uint32_t t[2];}tvbg_code_t;
static const tvbg_code_t TVBG_CODES[3]={{38000,2,{10,20}},{38000,2,{10,20}},{38000,2,{10,20}}};
static bool s_tvbg_stop,fail,stop;static int allocs,frees,replays;
static void *heap_caps_malloc(size_t n,int caps){allocs++;assert(n==sizeof(ir_signal_t));assert(caps==(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT));return fail?NULL:malloc(n);}
static void heap_caps_free(void*p){assert(p);frees++;free(p);}
static void ir_hat_replay(ir_signal_t*p){assert(p->freq_hz==38000&&p->count==2&&p->times_us[1]==20);replays++;if(stop)s_tvbg_stop=true;}
static void vTaskDelay(int ms){(void)ms;}
"""
post=r"""
int main(void){assert(CALL==ESP_OK);assert(replays==6);
#if CONFIG_BOARD_HAS_PSRAM
 assert(!allocs&&!frees);
#else
 assert(allocs==1&&frees==1);fail=true;assert(CALL==ESP_ERR_NO_MEM&&replays==6&&allocs==2&&frees==1);fail=false;
#endif
 stop=true;replays=0;assert(CALL==ESP_OK);assert(replays==2);
#if !CONFIG_BOARD_HAS_PSRAM
 assert(allocs==3&&frees==2);
#endif
 puts("PASS production IR task: eligible storage, allocation failure, complete/stop release and repeat entry");}
""".replace('CALL',call)
(D/'host.c').write_text(pre+fn+post);result=[]
for psram in [0,1]:
 exe=D/('host-'+str(psram));subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=undefined','-DCONFIG_BOARD_HAS_PSRAM='+str(psram),str(D/'host.c'),'-o',str(exe)],check=True)
 p=subprocess.run([str(exe)],capture_output=True,text=True);print(psram,p.returncode,p.stdout+p.stderr);result.append({'psram':psram,'exit_code':p.returncode,'output':p.stdout+p.stderr})
(D/'results.json').write_text(json.dumps(result,indent=2));assert all(x['exit_code']==0 for x in result)
