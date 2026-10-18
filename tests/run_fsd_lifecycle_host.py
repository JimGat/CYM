#!/usr/bin/env python3
"""ASan/UBSan, real mailbox, real concurrent caller/owner; synthetic work payload."""
from pathlib import Path
import os,subprocess
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'fsd-concurrency';D.mkdir(parents=True,exist_ok=True)
(D/'sdkconfig.h').write_text('#define CONFIG_ESP_CONSOLE_NONE 0\n#define CONFIG_BOARD_HAS_PSRAM 1\n')
(D/'host.c').write_text(r"""
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <assert.h>
#include <sched.h>
#include <stdio.h>
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_8BIT 2
#include "fsd.h"
static atomic_int live,stop;
static void *heap_caps_calloc(size_t n,size_t s,int caps){assert(caps==3);void*p=calloc(n,s);assert(p);atomic_fetch_add(&live,1);return p;}
static void heap_caps_free(void*p){if(p){free(p);atomic_fetch_sub(&live,1);}}
#include "fsd_lifecycle.h"
static void *owner(void*unused){(void)unused;
 while(!atomic_load(&stop)){
  cym_fsd_request_t*r=fsd_take();if(!r){sched_yield();continue;}
  if(!__atomic_load_n(&r->cancelled,__ATOMIC_ACQUIRE)){
   r->data=fsd_alloc(16);strcpy(r->data,"owned payload");
   /* Delay after data allocation so cancellation overlaps live owner storage. */
   for(int i=0;i<3;i++)sched_yield();r->status=1;r->length=13;
  }fsd_complete(r);
 }return NULL;}
int main(void){pthread_t t;assert(!pthread_create(&t,NULL,owner,NULL));int done=0,cancel=0;
 for(int i=0;i<10000;i++){
  cym_fsd_request_t*r;while(!(r=cym_fsd_submit(FSD_WHERE,0,0,0,"concurrency")))sched_yield();
  if(i%2){__atomic_store_n(&r->cancelled,1,__ATOMIC_RELEASE);cancel++;}
  else{while(!__atomic_load_n(&r->done,__ATOMIC_ACQUIRE))sched_yield();assert(r->status&&!strcmp(r->data,"owned payload"));done++;}
  cym_fsd_release(r);
 }
 while(__atomic_load_n(&s_fsd_busy,__ATOMIC_ACQUIRE))sched_yield();atomic_store(&stop,1);assert(!pthread_join(t,NULL));assert(!live&&!s_fsd_pending);
 printf("PASS real mailbox concurrency: requests=10000 completed=%d cancelled=%d outstanding=%d\n",done,cancel,live);return 0;}
""")
cmd=['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-pthread','-I'+str(D),'-I'+str(R/'ESP32C5/main'),str(D/'host.c'),'-o',str(D/'host')]
subprocess.run(cmd,check=True);subprocess.run([str(D/'host')],check=True)
