#!/usr/bin/env python3
"""Installed ESP-IDF I2C release branches, verbatim, with hardware/RTOS mocks.
No claim that mock fault injection reproduces a physical I2C failure.
"""
from pathlib import Path
import os,re,subprocess,json,hashlib
D=Path(os.environ['CYM_TEST_OUT'])/'pn532-idf-contract';D.mkdir(parents=True,exist_ok=True)
P=Path(os.environ['IDF_PATH'])/'components/esp_driver_i2c/i2c_master.c';s=P.read_text()
names=['i2c_master_bus_destroy','i2c_master_bus_rm_device','i2c_del_master_bus']
def extract(n):
 m=re.search(r'(?:static )?esp_err_t '+n+r'\([^;]*?\)\s*\{',s);assert m,n
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <stdio.h>
#include <sys/queue.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_ERR_INVALID_ARG 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_RETURN_ON_FALSE(c,e,...) do{if(!(c))return(e);}while(0)
#define ESP_RETURN_ON_ERROR(c,...) do{int e=(c);if(e)return e;}while(0)
#define ESP_LOGD(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define portMAX_DELAY 99
#define I2C_TRANS_QUEUE_MAX 3
#define I2C_STATUS_START 1
struct base{int port_num;};
typedef struct i2c_master_bus_t i2c_master_bus_t;
typedef struct i2c_master_dev_t{ i2c_master_bus_t *master_bus;}i2c_master_dev_t;
typedef i2c_master_bus_t *i2c_master_bus_handle_t;
typedef i2c_master_dev_t *i2c_master_dev_handle_t;
typedef struct i2c_master_device_list{ i2c_master_dev_t *device; SLIST_ENTRY(i2c_master_device_list) next;}i2c_master_device_list_t;
struct i2c_master_bus_t{struct base*base;atomic_int status;void *bus_lock_mux,*cmd_semphr,*event_queue,*queues_storage,*i2c_async_ops,*trans_queues[3];SLIST_HEAD(,i2c_master_device_list) device_list;};
static bool fail_pins;static int release_calls;
static int i2c_common_deinit_pins(struct base*b){assert(b);return fail_pins?ESP_ERR_INVALID_STATE:ESP_OK;}
static int i2c_release_bus_handle(struct base*b){assert(b);release_calls++;free(b);return 0;}
static void xSemaphoreTake(void*p,int t){(void)p;(void)t;}
static void xSemaphoreGive(void*p){(void)p;}
static void vSemaphoreDeleteWithCaps(void*p){free(p);}
static void vQueueDeleteWithCaps(void*p){free(p);}
"""
post=r"""
int main(void){
 i2c_master_bus_t *b=calloc(1,sizeof(*b));assert(b);b->base=calloc(1,sizeof(*b->base));assert(b->base);
 SLIST_INIT(&b->device_list);
 i2c_master_dev_t*d=calloc(1,sizeof(*d));assert(d);d->master_bus=b;
 i2c_master_device_list_t*item=calloc(1,sizeof(*item));assert(item);item->device=d;SLIST_INSERT_HEAD(&b->device_list,item,next);
 atomic_init(&b->status,I2C_STATUS_START);
 assert(i2c_master_bus_rm_device(d)==ESP_ERR_INVALID_STATE);
 assert(SLIST_FIRST(&b->device_list)->device==d && release_calls==0);
 assert(i2c_del_master_bus(b)==ESP_ERR_INVALID_STATE && release_calls==0);
 atomic_store(&b->status,I2C_STATUS_START+1);
 assert(i2c_master_bus_rm_device(d)==ESP_OK && SLIST_EMPTY(&b->device_list));
 fail_pins=true;
 for(int i=0;i<3;i++)assert(i2c_del_master_bus(b)==ESP_ERR_INVALID_STATE && b->base && release_calls==0);
 fail_pins=false;assert(i2c_del_master_bus(b)==ESP_OK && release_calls==1);
 puts("PASS installed IDF: busy device removal retains device/list; nonempty bus refuses delete; pin-deinit failure retains bus; eventual cleanup succeeds");
}
"""
code='\n'.join(extract(n) for n in names);(D/'host.c').write_text(pre+code+post)
cmd=[os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie',str(D/'host.c'),'-o',str(D/'host')]
subprocess.run(cmd,check=True);subprocess.run([str(D/'host')],check=True)
(D/'provenance.json').write_text(json.dumps({'source':str(P),'sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'extracted_verbatim':names,'extracted_sha256':hashlib.sha256(code.encode()).hexdigest(),'classification':'installed SDK release logic with substituted hardware/RTOS primitives; no installed creation path or physical proof'},indent=2))
