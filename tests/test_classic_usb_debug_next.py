"""Production C regression tests for Classic bounded records and C5 policy."""
import os, subprocess, tempfile, unittest
from pathlib import Path
from test_classic_usb_debug import MAIN, ROOT, TRANSPORT_STUB
STUB = TRANSPORT_STUB + r"""
typedef void *TaskHandle_t;
TaskHandle_t xTaskGetCurrentTaskHandle(void);
typedef void *esp_timer_handle_t;
typedef struct {void (*callback)(void *); void *arg; const char *name;} esp_timer_create_args_t;
int esp_timer_create(const esp_timer_create_args_t *, esp_timer_handle_t *);
int esp_timer_start_periodic(esp_timer_handle_t,unsigned long long);
int esp_timer_stop(esp_timer_handle_t);
int esp_timer_delete(esp_timer_handle_t);
"""
HARNESS = r"""
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mock.h"
#include "classic_usb_debug.h"
static int installed,locked,drive,fault,quota=7,recursive;
static unsigned task_id=1;
TaskHandle_t xTaskGetCurrentTaskHandle(void){return (void *)(uintptr_t)task_id;}
static size_t used;
static char output[1048576];
static void (*tick)(void *);
void *test_calloc(size_t n,size_t s){if(fault==6)return NULL;void *p=malloc(n*s);if(p)memset(p,0,n*s);return p;}
static int old(const char *f,va_list a){(void)f;(void)a;return 0;}
static vprintf_like_t sink=old,late;
bool cym_classic_usb_gps_blocked(void){return true;}
SemaphoreHandle_t xSemaphoreCreateMutexStatic(StaticSemaphore_t *p){return fault==7?NULL:p;}
int xSemaphoreTake(SemaphoreHandle_t p,unsigned t){assert(p);(void)t;if(locked)return 0;locked=1;return 1;}
void xSemaphoreGive(SemaphoreHandle_t p){assert(p&&locked);locked=0;}
bool uart_is_driver_installed(int n){assert(!n);return installed;}
int uart_driver_install(int n,int rx,int tx,int q,void *h,int f){assert(!n&&rx==256&&!tx&&!q&&!h&&!f);if(fault==1)return -1;installed=1;return 0;}
int uart_driver_delete(int n){assert(!n&&!drive);if(fault==10)return -1;installed=0;return 0;}
int uart_param_config(int n,const uart_config_t *c){assert(!n&&c->baud_rate==115200);return fault==2?-1:0;}
int uart_set_pin(int n,int tx,int rx,int r,int c){assert(!n&&tx==1&&rx==-1&&r==-1&&c==-1);drive=1;return fault==3?-1:0;}
int gpio_reset_pin(int n){assert(n==1);drive=0;return fault==9?-1:0;}
int gpio_set_direction(int n,int m){assert(n==1&&m==1);return 0;}
void test_log(const char *f,...){va_list a;va_start(a,f);sink(f,a);va_end(a);}
int uart_tx_chars(int n,const char *p,uint32_t count){assert(!n&&locked&&drive);if(recursive){recursive=0;test_log("reentrant\n");}if(quota<0)return -1;int k=count<(unsigned)quota?(int)count:quota;memcpy(output+used,p,k);used+=k;return k;}
vprintf_like_t esp_log_set_vprintf(vprintf_like_t f){vprintf_like_t o=sink;sink=f;if(f!=old)late=f;return o;}
int esp_timer_create(const esp_timer_create_args_t *a,esp_timer_handle_t *h){if(fault==4)return -1;tick=a->callback;*h=(void *)1;return 0;}
int esp_timer_start_periodic(esp_timer_handle_t h,unsigned long long n){assert(h&&n);return fault==5?-1:0;}
int esp_timer_stop(esp_timer_handle_t h){assert(h);return 0;}
int esp_timer_delete(esp_timer_handle_t h){assert(h);if(fault==8)return -1;tick=NULL;return 0;}
static void drain(void){for(int i=0;i<2000;i++)if(tick)tick(NULL);}
static void late_log(const char *f,...){va_list a;va_start(a,f);late(f,a);va_end(a);}
int main(int argc,char **argv){
 (void)argc;fault=atoi(argv[1]);int rc=cym_classic_usb_uart_start();
 if(fault&&fault<=7){assert(rc!=0&&!installed&&!drive&&sink==old&&!tick);return 0;}
 drain();used=0;
 char longline[701];memset(longline,'X',700);longline[700]=0;
 test_log("%s\n",longline);assert(used==0);drain();assert(used==702&&!memcmp(output,longline,700)&&!memcmp(output+700,"\r\n",2));
 used=0;quota=0;test_log("prefix ");tick(NULL);assert(!used);test_log("body %d",42);test_log("\n");drain();assert(!used);quota=3;drain();assert(used==16&&!memcmp(output,"prefix body 42\r\n",16));
 used=0;test_log("a\r\n");test_log("b\n");quota=-1;drain();assert(!used);quota=1;drain();assert(used==6&&!memcmp(output,"a\r\nb\r\n",6));
 used=0;char huge[1600];memset(huge,'Z',sizeof(huge)-1);huge[1599]=0;test_log("%s",huge);test_log("tail\nOK\n");drain();assert(used==4&&!memcmp(output,"OK\r\n",4));
 used=0;quota=0;for(int i=0;i<100;i++)test_log("%s\n",longline);quota=127;drain();assert(used>0&&used%702==0);for(size_t i=700;i<used;i+=702)assert(!memcmp(output+i,"\r\n",2));
 cym_classic_usb_uart_stats_t stats;cym_classic_usb_uart_stats(&stats);assert(stats.dropped_records>0&&stats.accepted_records>0);
 used=0;test_log("task1 unfinished");task_id=2;test_log("task2 tail\n");drain();assert(!used);task_id=1;test_log("OK\n");drain();assert(used==4&&!memcmp(output,"OK\r\n",4));
 used=0;test_log("unfinished");locked=1;test_log("busy\n");locked=0;test_log("discard\nSAFE\n");drain();assert(used==6&&!memcmp(output,"SAFE\r\n",6));
 used=0;test_log("reentry safe\n");recursive=1;drain();assert(used==14&&!memcmp(output,"reentry safe\r\n",14));
 quota=0;test_log("queued\n");locked=1;assert(cym_classic_usb_uart_stop()==ESP_ERR_TIMEOUT);locked=0;size_t before=used;late_log("late\n");drain();assert(used==before);if(fault>=8){assert(cym_classic_usb_uart_stop()!=0);fault=0;}assert(cym_classic_usb_uart_stop()==0);assert(!tick&&!drive&&!installed&&sink==old);late_log("later\n");assert(used==before);
 puts("bounded production transport PASS");return 0;
}
"""
class NextTransport(unittest.TestCase):
 def test_production_records_and_cleanup(self):
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
   d=Path(tmp);(d/'sdkconfig.h').write_text('#define CONFIG_BOARD_CYD2USB 1\n');(d/'mock.h').write_text(STUB)
   for h in ['esp_err.h','esp_timer.h','driver/uart.h','driver/gpio.h','esp_log.h','freertos/FreeRTOS.h','freertos/semphr.h','freertos/task.h']:
    p=d/h;p.parent.mkdir(exist_ok=True,parents=True);p.write_text('#include "mock.h"\n')
   (d/'host.c').write_text(HARNESS)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-Dcalloc=test_calloc','-I'+str(d),'-I'+str(MAIN),str(d/'host.c'),str(MAIN/'classic_usb_debug_uart.c'),'-o',str(d/'host')],check=True)
   for fault in range(11):subprocess.run([str(d/'host'),str(fault)],check=True)

 def test_real_concurrent_producers_and_drain(self):
  code=HARNESS[:HARNESS.index('int main(int argc')]
  code='#include <pthread.h>\n'+code
  code=code.replace('static unsigned task_id=1;\nTaskHandle_t xTaskGetCurrentTaskHandle(void){return (void *)(uintptr_t)task_id;}', 'TaskHandle_t xTaskGetCurrentTaskHandle(void){return (void *)(uintptr_t)pthread_self();}')
  code=code.replace('static int installed,locked,drive,fault,quota=7,recursive;', 'static int installed,drive,fault,quota=7,recursive;\nstatic pthread_mutex_t guard=PTHREAD_MUTEX_INITIALIZER;')
  code=code.replace('if(locked)return 0;locked=1;return 1;', 'return pthread_mutex_trylock(&guard)==0;')
  code=code.replace('assert(p&&locked);locked=0;', 'assert(p);assert(!pthread_mutex_unlock(&guard));')
  code=code.replace('!n&&locked&&drive','!n&&drive')
  code+=r"""
static void *producer(void *arg){(void)arg;for(int i=0;i<5000;i++)test_log("THREAD complete record %d\n",i);return NULL;}
static void *consumer(void *arg){(void)arg;for(int i=0;i<15000;i++)tick(NULL);return NULL;}
int main(void){
 assert(!cym_classic_usb_uart_start());drain();used=0;
 pthread_t a,b,c;assert(!pthread_create(&a,NULL,producer,NULL));assert(!pthread_create(&b,NULL,producer,NULL));assert(!pthread_create(&c,NULL,consumer,NULL));
 pthread_join(a,NULL);pthread_join(b,NULL);pthread_join(c,NULL);drain();
 for(size_t i=0;i<used;){size_t start=i;while(i<used&&output[i]!='\n')i++;assert(i<used&&i>start&&output[i-1]=='\r');assert(i-start>=23&&!memcmp(output+start,"THREAD complete record ",23));i++;}
 cym_classic_usb_uart_stats_t st;cym_classic_usb_uart_stats(&st);assert(st.accepted_records>0);assert(!cym_classic_usb_uart_stop());late_log("late\n");puts("pthread producers/drain PASS");return 0;
}
"""
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
   d=Path(tmp);(d/'sdkconfig.h').write_text('#define CONFIG_BOARD_CYD2USB 1\n');(d/'mock.h').write_text(STUB)
   for h in ['esp_err.h','esp_timer.h','driver/uart.h','driver/gpio.h','esp_log.h','freertos/FreeRTOS.h','freertos/semphr.h','freertos/task.h']:
    p=d/h;p.parent.mkdir(exist_ok=True,parents=True);p.write_text('#include "mock.h"\n')
   (d/'host.c').write_text(code)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(MAIN),str(d/'host.c'),str(MAIN/'classic_usb_debug_uart.c'),'-o',str(d/'host')],check=True)
   subprocess.run([str(d/'host')],check=True)

 def test_c5_policy_production(self):
  s=(MAIN/'main.c').read_text();self.assertIn('cym_wifi_sas_continue(',s)
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
   d=Path(tmp);(d/'sdkconfig.h').write_text('')
   (d/'host.c').write_text(r"""
#include <assert.h>
#include "wifi_sas_policy.h"
int main(void){
#ifdef CONFIG_IDF_TARGET_ESP32C5
 assert(cym_wifi_sas_continue(1,0,0));assert(cym_wifi_sas_continue(1,1,0));
 assert(!cym_wifi_sas_continue(2,1,0));assert(cym_wifi_sas_continue(2,0,0));assert(!cym_wifi_sas_continue(3,0,0));
#else
 assert(cym_wifi_sas_continue(3,0,0));assert(cym_wifi_sas_continue(7,1,0));assert(!cym_wifi_sas_continue(8,0,0));assert(!cym_wifi_sas_continue(2,2,0));
#endif
 assert(!cym_wifi_sas_continue(1,0,45000));return 0;}
""")
   for flags in [[],['-DCONFIG_IDF_TARGET_ESP32C5=1']]:
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',*flags,'-I'+str(d),'-I'+str(MAIN),str(d/'host.c'),'-o',str(d/'host')],check=True);subprocess.run([str(d/'host')],check=True)

NVS_STUB = r"""#pragma once
#include "esp_err.h"
#include <stdint.h>
typedef int nvs_handle_t;
#define NVS_READWRITE 1
#define ESP_ERR_NVS_NOT_FOUND 0x1102
esp_err_t nvs_open(const char *,int,nvs_handle_t *);
esp_err_t nvs_get_u8(nvs_handle_t,const char *,uint8_t *);
esp_err_t nvs_set_u8(nvs_handle_t,const char *,uint8_t);
esp_err_t nvs_commit(nvs_handle_t);
void nvs_close(nvs_handle_t);
"""
PERSIST_HARNESS=r"""
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "classic_usb_debug.h"
#include "nvs.h"
static int fault,saved,pending,starts,stops,quiesces;
esp_err_t nvs_open(const char *s,int mode,nvs_handle_t *h){assert(!strcmp(s,"cym_usb")&&mode==1);*h=1;return fault==1?ESP_FAIL:ESP_OK;}
esp_err_t nvs_get_u8(nvs_handle_t h,const char *k,uint8_t *v){assert(h==1&&!strcmp(k,"enabled"));if(fault==2)return ESP_FAIL;if(saved<0)return ESP_ERR_NVS_NOT_FOUND;*v=saved;return ESP_OK;}
esp_err_t nvs_set_u8(nvs_handle_t h,const char *k,uint8_t v){assert(h==1&&!strcmp(k,"enabled"));if(fault==3)return ESP_FAIL;pending=v;return ESP_OK;}
esp_err_t nvs_commit(nvs_handle_t h){assert(h==1);if(fault==4)return ESP_FAIL;saved=pending;return ESP_OK;}
void nvs_close(nvs_handle_t h){assert(h==1);}
void cym_classic_usb_uart_stats(cym_classic_usb_uart_stats_t *s){*s=(cym_classic_usb_uart_stats_t){0};}
esp_err_t cym_classic_usb_uart_start(void){assert(cym_classic_usb_gps_blocked());starts++;return fault==5?ESP_FAIL:ESP_OK;}
esp_err_t cym_classic_usb_uart_stop(void){stops++;return fault==6?ESP_FAIL:ESP_OK;}
static esp_err_t quiet(void){assert(cym_classic_usb_gps_blocked());quiesces++;return fault==7?ESP_FAIL:ESP_OK;}
int main(int argc,char **argv){
 (void)argc;fault=atoi(argv[1]);saved=atoi(argv[2]);int boot=atoi(argv[3]);(void)boot;
#if CONFIG_BOARD_CYD2USB && !CONFIG_BOARD_HACKERBOX_CYD && !CONFIG_BOARD_HAS_PSRAM && !CONFIG_SPIRAM
 if(boot){
  int rc=cym_classic_usb_restore();
  if(fault||saved==9){assert(rc!=ESP_OK&&!cym_classic_usb_active()&&cym_classic_usb_gps_blocked());}
  else if(saved==1){assert(rc==ESP_OK&&starts==1&&cym_classic_usb_active()&&!quiesces);}
  else {assert(rc==ESP_OK&&!starts&&!cym_classic_usb_gps_blocked());}
 }else{
  assert(cym_classic_usb_enable(false,quiet)!=ESP_OK&&!starts&&!quiesces);
  int rc=cym_classic_usb_enable(true,quiet);assert(cym_classic_usb_gps_blocked());
  if(fault==1||fault==3||fault==4||fault==5||fault==7){assert(rc!=ESP_OK&&!cym_classic_usb_active());}
  else{assert(rc==ESP_OK&&saved==1&&cym_classic_usb_active());assert(cym_classic_usb_enable(true,quiet)==ESP_OK&&starts==1);}
 }
 for(int f=1;f<=4;f++){if(f==2)continue;fault=f;assert(cym_classic_usb_disable()!=ESP_OK&&!cym_classic_usb_active());}
 fault=0;assert(cym_classic_usb_disable()==ESP_OK&&saved==0&&!cym_classic_usb_active());
 /* Even OFF must clear stale persistent state; GPS remains blocked after attempt. */
 if(starts||quiesces)assert(cym_classic_usb_gps_blocked());
#else
 assert(cym_classic_usb_restore()==ESP_ERR_NOT_SUPPORTED&&!starts&&!cym_classic_usb_gps_blocked());
#endif
 puts("persistent ownership PASS");return 0;
}
"""
class NextPersistence(unittest.TestCase):
 def test_controller_nvs_and_reboot(self):
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
   d=Path(tmp);(d/'sdkconfig.h').write_text('');(d/'esp_err.h').write_text(TRANSPORT_STUB);(d/'nvs.h').write_text(NVS_STUB);(d/'host.c').write_text(PERSIST_HARNESS)
   for flags in [['-DCONFIG_BOARD_CYD2USB=1'],['-DCONFIG_BOARD_CYD2USB=1','-DCONFIG_BOARD_HACKERBOX_CYD=1'],['-DCONFIG_BOARD_CYD2USB=1','-DCONFIG_BOARD_HAS_PSRAM=1'],['-DCONFIG_BOARD_CYD2USB=1','-DCONFIG_SPIRAM=1'],[]]:
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=undefined',*flags,'-I'+str(d),'-I'+str(MAIN),str(d/'host.c'),str(MAIN/'classic_usb_debug.c'),'-o',str(d/'host')],check=True)
    cases=[(i,0,0) for i in range(8)]+[(0,i,1)for i in [-1,0,1,9]]+[(i,1,1)for i in [1,2,3,4,5]]
    for args in cases:subprocess.run([str(d/'host'),*map(str,args)],check=True,capture_output=True)
 def test_restore_precedes_gps(self):
  s=(MAIN/'main.c').read_text();app=s[s.index('void app_main(void)'):]
  self.assertLess(app.index('cym_classic_usb_restore()'),app.index('if (init_gps_uart()'))
  self.assertGreater(app.index('cym_classic_usb_restore()'),app.index('ESP_ERROR_CHECK(nvs_ret)'))
if __name__=='__main__':unittest.main()

