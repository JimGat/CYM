#!/usr/bin/env python3
"""Production HTTP/DNS start/stop and DNS task lifetime with SDK-boundary fault
injection. No live listener or RF; installed SDK error/HTTP enums are mandatory.
"""
from pathlib import Path
import os,re,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];S=(R/'ESP32C5/components/wifi_attacks/wifi_attacks.c').read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'ap-services';D.mkdir(parents=True,exist_ok=True)
IDF=Path(os.environ.get('IDF_PATH','/home/dev/esp/esp-idf'))
def fn(n):
 m=re.search(r'^static (?:void|esp_err_t) '+n+r'\([^;]*?\)\s*\{',S,re.M);assert m,n
 i=m.end();d=1
 while d:d+=(S[i]=='{')-(S[i]=='}');i+=1
 return S[m.start():i]
prod='\n'.join(fn(n)for n in ['stop_portal_services','dns_server_task','start_portal_services'])
pre=r"""
#include "esp_err.h"
#include "http_parser.h"
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <arpa/inet.h>
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define pdMS_TO_TICKS(x) (x)
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY 0xffffffffU
#define xTaskNotifyGive(x) ((void)0)
#define ulTaskNotifyTake(a,b) ((void)0)
typedef void* TaskHandle_t;
static void *portal_server;
static TaskHandle_t dns_server_task_handle;
static int dns_server_socket=-1,connectAttemptCount;
static bool dns_run,dns_exited=true,portal_active;
static int calls,fail_at,stop_fail,closed,delays,deleted;
static int boundary(void){return ++calls==fail_at?ESP_ERR_NO_MEM:ESP_OK;}
/* Mock only HTTP transport structures; method constants above come from SDK. */
typedef struct{int server_port,max_open_sockets,max_uri_handlers;bool lru_purge_enable;}httpd_config_t;
#define HTTPD_DEFAULT_CONFIG() ((httpd_config_t){0})
typedef struct {const char *uri;enum http_method method;void *handler,*user_ctx;}httpd_uri_t;
static int portal_root_handler,portal_handler,portal_submit_handler,get_handler,save_handler;
static int portal_generate_204_handler,portal_hotspot_detect_handler,captive_detection_handler,captive_api_handler,captive_portal_redirect_handler;
static int httpd_start(void **h,void *cfg){(void)cfg;int rc=boundary();if(!rc)*h=(void*)1;return rc;}
static int httpd_register_uri_handler(void*h,const httpd_uri_t*u){(void)h;(void)u;return boundary();}
static int httpd_stop(void*h){(void)h;return stop_fail?ESP_ERR_TIMEOUT:ESP_OK;}
static int mock_socket(int a,int b,int c){(void)a;(void)b;(void)c;return boundary()?-1:42;}
static int mock_bind(int fd,const struct sockaddr*a,socklen_t n){(void)fd;(void)a;(void)n;return boundary()?-1:0;}
static int mock_setsockopt(int fd,int a,int b,const void*c,socklen_t n){(void)fd;(void)a;(void)b;(void)c;(void)n;return boundary()?-1:0;}
static int mock_close(int fd){if(fd!=42)abort();closed++;return 0;}
static int mock_recvfrom(int fd,void*b,size_t l,int f,struct sockaddr*a,socklen_t*n){(void)fd;(void)b;(void)l;(void)f;(void)a;(void)n;errno=EIO;return -1;}
static int mock_sendto(int f,const void*b,size_t l,int flags,const struct sockaddr*a,socklen_t n){(void)f;(void)b;(void)l;(void)flags;(void)a;(void)n;abort();}
static int xTaskCreate(void(*fn)(void*),const char*n,int sz,void*a,int pri,TaskHandle_t*h){(void)fn;(void)n;(void)sz;(void)a;(void)pri;int rc=boundary();if(!rc)*h=(void*)2;return rc?0:pdPASS;}
static void vTaskDelay(int n){(void)n;delays++;}
static void vTaskDelete(void *h){(void)h;deleted++;}
#define socket mock_socket
#define bind mock_bind
#define setsockopt mock_setsockopt
#define close mock_close
#define recvfrom mock_recvfrom
#define sendto mock_sendto
"""
pre+='\n'.join(re.findall(r'^#define DNS_(?:PORT|MAX_PACKET_SIZE)\s+.*$',S+(R/'ESP32C5/components/wifi_cli/include/wifi_common.h').read_text(),re.M))+'\n'
# Handler addresses, not dummy function calls.
for n in ['portal_root_handler','portal_handler','portal_submit_handler','get_handler','save_handler','portal_generate_204_handler','portal_hotspot_detect_handler','captive_detection_handler','captive_api_handler','captive_portal_redirect_handler']:
 prod=prod.replace('.handler = '+n,'.handler = &'+n)

post=r"""
#define CHECK(x) do{if(!(x)){fprintf(stderr,"SEMANTIC_FAILURE line=%d: %s\n",__LINE__,#x);return 86;}}while(0)
static void reset(void){portal_server=NULL;dns_server_task_handle=NULL;dns_server_socket=-1;
 dns_run=false;dns_exited=true;portal_active=false;calls=fail_at=stop_fail=closed=delays=deleted=0;}
int main(void){
 reset();CHECK(start_portal_services()==ESP_OK);int boundaries=calls;
 CHECK(portal_active && portal_server && dns_server_task_handle && dns_server_socket==42);
 CHECK(start_portal_services()==ESP_ERR_INVALID_STATE); /* no duplicate resources */
 CHECK(stop_portal_services()==ESP_ERR_TIMEOUT);CHECK(delays==50);
 CHECK(!portal_active && portal_server && dns_server_task_handle && dns_server_socket==42 && closed==0);
 dns_server_task(NULL);CHECK(dns_exited && dns_server_socket==-1 && closed==1 && deleted==1);
 stop_fail=1;CHECK(stop_portal_services()==ESP_ERR_TIMEOUT);CHECK(portal_server && !dns_server_task_handle);
 stop_fail=0;CHECK(stop_portal_services()==ESP_OK);CHECK(!portal_server && closed==1);
 CHECK(stop_portal_services()==ESP_OK);CHECK(closed==1);
 for(int i=1;i<=boundaries;i++){
  reset();fail_at=i;CHECK(start_portal_services()!=ESP_OK);
  CHECK(!portal_active && !dns_server_task_handle && !portal_server && dns_server_socket==-1);
  CHECK(closed==(i>14)); /* HTTP start + 12 URIs + socket precede bound fd */
 }
 reset();fail_at=2;stop_fail=1;CHECK(start_portal_services()!=ESP_OK);
 CHECK(portal_server && !portal_active);stop_fail=0;CHECK(stop_portal_services()==ESP_OK);
 for(int i=0;i<50;i++){reset();CHECK(start_portal_services()==ESP_OK);dns_run=false;
 dns_server_task(NULL);CHECK(closed==1);CHECK(stop_portal_services()==ESP_OK);}
 printf("PASS services fault-boundaries=%d restart-cycles=50 timeout-retention/single-close\n",boundaries);return 0;
}
"""
variants=[('production',prod,False),('forget-http-on-error',prod.replace('if (rc != ESP_OK) return rc;','if (rc != ESP_OK) { portal_server = NULL; return rc; }',1),True),('forget-live-dns',prod.replace('if (dns_server_task_handle && !__atomic_load_n(&dns_exited, __ATOMIC_ACQUIRE)) return ESP_ERR_TIMEOUT;','/* mutant: no acknowledgement required */'),True),('ignore-handler-error',prod.replace('if (rc != ESP_OK) goto failed;','/* mutant: ignore URI failure */'),True)]
(D/'sdkconfig.h').write_text('/* Native extraction; no target config options. */\n')
expected={'forget-http-on-error':'portal_server && !dns_server_task_handle','forget-live-dns':'stop_portal_services()==ESP_ERR_TIMEOUT','ignore-handler-error':'start_portal_services()!=ESP_OK'}
results=[]
for name,body,mutant in variants:
 assert not mutant or body!=prod
 out=D/name;out.mkdir(exist_ok=True);(out/'host.c').write_text(pre+body+post)
 cmd=[os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fno-pie','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(D),'-I'+str(IDF/'components/esp_common/include'),'-I'+str(IDF/'components/http_parser'),str(out/'host.c'),'-o',str(out/'host')]
 b=subprocess.run(cmd,capture_output=True,text=True);(out/'compile.log').write_text(b.stdout+b.stderr);assert b.returncode==0,b.stderr
 b=subprocess.run([str(out/'host')],capture_output=True,text=True);(out/'run.log').write_text(b.stdout+b.stderr)
 ok=(b.returncode==86 and 'SEMANTIC_FAILURE' in b.stderr and expected[name] in b.stderr)if mutant else b.returncode==0 and 'PASS' in b.stdout
 results.append(dict(name=name,exit=b.returncode,mutant=mutant,ok=ok));print(results[-1],b.stdout,b.stderr[:500])
(D/'results.json').write_text(json.dumps(dict(results=results,source_sha256=hashlib.sha256(S.encode()).hexdigest()),indent=2))
assert all(x['ok']for x in results)
print('PASS semantic mutants',sum(x['mutant']for x in results))
