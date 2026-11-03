#!/usr/bin/env python3
"""Production manager teardown fault injection; SDK/task mocks, not hardware proof."""
from pathlib import Path
import os,re,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1]
D=Path(os.environ['CYM_TEST_OUT'])/'pn532-manager';D.mkdir(parents=True,exist_ok=True)
p=R/'ESP32C5/components/rfid/src/rfid_manager.c';s=p.read_text()
def extract(name):
 m=re.search(r'(?:void|bool|rfid_err_t)\s+'+name+r'\([^;]*?\)\s*\{',s);assert m,name
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
names=['rfid_manager_deinit']
if re.search(r'bool\s+rfid_manager_release\(',s):names.insert(0,'rfid_manager_release')
pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
typedef void *TaskHandle_t;
static TaskHandle_t s_poll_task,s_emu_task;
static bool s_poll_stop,s_emu_stop,s_mgr_init,s_addr_ok,s_cleanup_pending;
static void *s_poll_card,*s_emu_card;
static bool owned,fail_release;
static int releases,frees;
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
static void rfid_manager_stop_poll(void){s_poll_stop=true;}
static bool pn532_driver_release(void){
 assert(!s_poll_task && !s_emu_task);releases++;
 if(fail_release)return false;owned=false;return true;
}
static void pn532_driver_deinit(void){(void)pn532_driver_release();}
static void counted_free(void *p){assert(!s_poll_task&&!s_emu_task&&!owned);if(p){frees++;free(p);}}
#define free counted_free
"""
code=pre+'\n'.join(extract(n) for n in names)
if len(names)==1:code+='\nstatic bool rfid_manager_release(void){rfid_manager_deinit();return !owned;}\n'
code+=r"""
static void setup(void){s_mgr_init=true;s_addr_ok=true;s_poll_card=malloc(8);owned=true;}
int main(void){
 setup();s_poll_task=(void*)1;
 assert(!rfid_manager_release());assert(s_poll_stop&&s_poll_card&&owned&&releases==0&&frees==0);
 s_poll_task=NULL;s_emu_task=(void*)2;
 assert(!rfid_manager_release());assert(s_emu_stop&&s_poll_card&&owned&&releases==0&&frees==0);
 s_emu_task=NULL;fail_release=true;
 for(int i=0;i<3;i++){assert(!rfid_manager_release());assert(!s_mgr_init&&s_poll_card&&owned&&frees==0);}
 fail_release=false;assert(rfid_manager_release());assert(!s_poll_card&&!s_mgr_init&&!owned&&frees==1);
 // Failed initialization can own a bus even when manager never became ready.
 setup();s_mgr_init=false;fail_release=true;
 assert(!rfid_manager_release());assert(owned&&s_poll_card&&frees==1);
 fail_release=false;assert(rfid_manager_release());assert(!owned&&!s_poll_card&&frees==2);
 assert(rfid_manager_release());assert(frees==2);
 puts("PASS manager: active poll/emulation retain resources; failed cleanup retains card+ownership; recovery and repeated release");
}
"""
(D/'host.c').write_text(code)
cmd=[os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie',str(D/'host.c'),'-o',str(D/'host')]
subprocess.run(cmd,check=True);subprocess.run([str(D/'host')],check=True)
(D/'provenance.json').write_text(json.dumps({'source':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'extracted_verbatim':names,'classification':'production-extracted with task/I2C mocks; no installed SDK execution'},indent=2))
