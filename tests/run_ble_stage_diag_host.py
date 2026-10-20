#!/usr/bin/env python3
"""Production breadcrumb header, faulted reset/storage/debug boundaries; no RTC emulation."""
from pathlib import Path
import os,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'ble-stage';D.mkdir(parents=True,exist_ok=True)
code=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#define RTC_NOINIT_ATTR
static bool enabled;static uint32_t dbg=1;static int locks,lines,previous;static char status[40];
#define BT_STAGE_ENABLED() enabled
#define BT_STAGE_GENERATION() dbg
#define BT_STAGE_LOCK() (++locks)
#define BT_STAGE_UNLOCK() (--locks)
#define BT_STAGE_CURRENT(g,q,s,r) do{assert(!locks);(void)(g);(void)(q);(void)(s);(void)(r);lines++;}while(0)
#define BT_STAGE_PREVIOUS(g,q,s,r) do{assert(!locks);(void)(g);(void)(q);(void)(s);(void)(r);previous++;}while(0)
#define BT_STAGE_BOOT_STATUS(s,r) do{assert(!locks);(void)(r);snprintf(status,sizeof(status),"%s",s);}while(0)
#include "ble_stage_diag.h"
int main(void){
 bt_stage_boot(1,false);bt_stage(BT_ST_UI_ENTER,0);bt_stage_report(1000000);assert(!lines&&!previous&&!s_bt_stage_seq&&!status[0]);
 enabled=true;dbg++;bt_stage(BT_ST_UI_ENTER,0);assert(s_bt_stage_seq==1);
 bt_stage_report(1500000);assert(lines==1);bt_stage_report(1600000);assert(lines==1);
 for(int n=0;n<40;n++)bt_stage(BT_ST_HEAP_QUERY,n);
 bt_stage_report(2100000);assert(lines==9); // bounded to 8, not a logging flood
 bt_stage_boot(4,true);assert(!strcmp(status,"valid")&&previous==8&&!s_bt_stage_seq);
 bt_stage(BT_ST_PORT_INIT,0);s_bt_stage_record.slot[0].check^=1;bt_stage_boot(4,true);assert(!strcmp(status,"corrupt"));
 s_bt_stage_record.tag^=1;bt_stage_boot(4,true);assert(!strcmp(status,"stale-or-unavailable"));
 bt_stage(BT_ST_HOST_CREATE,0);bt_stage_boot(1,false);assert(!strcmp(status,"unavailable"));
 bt_stage(BT_ST_SYNC_TIMEOUT,-1);enabled=false;dbg++;int old=lines;bt_stage_report(3000000);assert(lines==old&&!s_bt_stage_seq);
 enabled=true;dbg++;bt_stage_report(4000000);assert(lines==old&&!s_bt_stage_seq); // old debug generation cleared
 bt_stage((bt_stage_t)BT_ST_END,0);bt_stage((bt_stage_t)0,0);assert(!s_bt_stage_seq);
 s_bt_stage_seq=UINT32_MAX;bt_stage(BT_ST_GAP_RETURN,7);assert(s_bt_stage_seq==1&&bt_stage_valid(s_bt_stage_record.slot[0]));
 bt_stage(BT_ST_PORT_DEINIT_RETURN,-7);s_bt_stage_record.slot[1].stage=BT_ST_END;bt_stage_boot(4,true);assert(!strcmp(status,"corrupt"));
 assert(!locks);printf("PASS breadcrumb OFF/ON, bounded burst, valid/corrupt/stale/unavailable, debug generation, sequence wrap; RTC bytes=%zu\n",sizeof(s_bt_stage_record));
}
"""
(D/'host.c').write_text(code)
cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-I'+str(R/'ESP32C5/main'),str(D/'host.c'),'-o',str(D/'host')]
subprocess.run(cmd,check=True);p=subprocess.run([str(D/'host')],capture_output=True,text=True);print(p.stdout+p.stderr)
(D/'results.json').write_text(json.dumps({'command':cmd,'exit':p.returncode,'output':p.stdout+p.stderr,'header_sha256':hashlib.sha256((R/'ESP32C5/main/ble_stage_diag.h').read_bytes()).hexdigest(),'limitation':'No physical reset retention assertion'},indent=2));assert p.returncode==0
