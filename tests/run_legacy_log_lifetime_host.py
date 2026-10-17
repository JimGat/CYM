#!/usr/bin/env python3
from pathlib import Path
import subprocess,re
r=Path(__file__).resolve().parents[1];d=Path('/home/dev/projects/cym-targeted-refactor-20261017/logs');d.mkdir(exist_ok=True)
s=(r/'ESP32C5/main/legacy_log_lifetime.h').read_text();s=re.sub(r'^#include .*$', '',s,flags=re.M)
stub=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
typedef void *QueueHandle_t;
#define portMUX_TYPE int
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)p)
#define portEXIT_CRITICAL(p) ((void)p)
static int deleted;static void vQueueDelete(void*q){assert(q);deleted++;free(q);}
"""
main=r"""
int main(void){QueueHandle_t q=malloc(5120);assert(q);cym_log_enter();cym_log_enter();assert(!cym_log_retire(&q,false)&&q);cym_log_leave();assert(!cym_log_retire(&q,false)&&q);cym_log_leave();assert(!cym_log_retire(&q,true)&&q);assert(cym_log_retire(&q,false)&&!q&&deleted==1);assert(cym_log_retire(&q,false)&&deleted==1);for(int i=0;i<100;i++){q=malloc(i==3?3200:5120);cym_log_enter();cym_log_leave();assert(cym_log_retire(&q,false));}puts("PASS log retained during concurrent producers; disabled retirement; same bounded internal capacities");}
"""
p=d/'logs.c';p.write_text(stub+s+main);exe=d/'logs';subprocess.run(['cc','-std=c11','-fsanitize=address,undefined','-no-pie',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
