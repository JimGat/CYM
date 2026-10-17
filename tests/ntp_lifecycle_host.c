/* Entire production translation unit runs against deterministic IDF/socket fakes. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include <setjmp.h>
#include <sys/time.h>
#include <arpa/inet.h>
#include <unistd.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NO_MEM 0x101
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_TIMEOUT 0x107
#define pdPASS 1
#define pdMS_TO_TICKS(n) (n)
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_SPIRAM 2
#define MALLOC_CAP_8BIT 4
#define CONFIG_SPIRAM_ALLOW_STACK_EXTERNAL_MEMORY 1
static unsigned log_count;
static bool debug_enabled;
static void host_log(const char *tag,const char *fmt,...) { (void)tag;(void)fmt;log_count++; }
#define ESP_LOGI(...) host_log(__VA_ARGS__)
#define ESP_LOGW(...) host_log(__VA_ARGS__)
#define ESP_LOGE(...) host_log(__VA_ARGS__)
#define portMUX_TYPE int
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
typedef int BaseType_t;
typedef unsigned UBaseType_t;
typedef struct { int state; void (*fn)(void *); void *arg; } task_t;
typedef task_t *TaskHandle_t;
enum { eRunning, eSuspended };
static task_t task;
static int psram=1, fail_socket, fail_bind, fail_option, fail_alloc;
static int opened, closed, deleted, delays, exit_after=1, caps, depth;
static int packets, replies, quality, malformed, send_fail, reenter, reenter_ok;
static uint8_t response[48];
static jmp_buf suspended;
static int64_t esp_timer_get_time(void) { return 1000000; }
static size_t heap_caps_get_total_size(unsigned c) { return c & MALLOC_CAP_SPIRAM ? psram*8192 : 8192; }
static size_t heap_caps_get_free_size(unsigned c) { (void)c; return 1024; }
static size_t heap_caps_get_largest_free_block(unsigned c) { (void)c; return 512; }
static bool cym_debug_enabled(void) { return debug_enabled; }
static const char *esp_err_to_name(int e) { (void)e; return "mock"; }
static int fake_socket(int a,int b,int c) { (void)a;(void)b;(void)c; if(fail_socket)return -1; opened++;return 10+opened; }
static int fake_bind(int s,const struct sockaddr *a,socklen_t n) { (void)s;(void)a;(void)n;return fail_bind?-1:0; }
static int fake_setsockopt(int s,int l,int o,const void *v,socklen_t n) { (void)s;(void)l;(void)o;(void)v;(void)n;return fail_option?-1:0; }
static int fake_close(int s) { assert(s==10+opened);closed++;assert(closed<=opened);return 0; }
static int fake_shutdown(int s,int h) { (void)s;(void)h;assert(!"owner must not touch live socket");return 0; }
static int fake_recvfrom(int,void *,size_t,int,struct sockaddr *,socklen_t *);
static int fake_sendto(int s,const void *b,size_t n,int f,const struct sockaddr *a,socklen_t z) { (void)s;(void)f;(void)a;(void)z;assert(n==48);memcpy(response,b,48);replies++;return send_fail?-1:48; }
static BaseType_t xTaskCreateWithCaps(void (*f)(void *),const char *n,unsigned d,void *a,unsigned p,TaskHandle_t *h,unsigned c) { (void)n;(void)p;caps=c;depth=d;if(fail_alloc)return 0; task=(task_t){eRunning,f,a};*h=&task;return pdPASS; }
static BaseType_t xTaskCreate(void (*f)(void *),const char *n,unsigned d,void *a,unsigned p,TaskHandle_t *h) { return xTaskCreateWithCaps(f,n,d,a,p,h,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT); }
static int eTaskGetState(TaskHandle_t h) { assert(h); return h->state; }
static void vTaskSuspend(TaskHandle_t h) { assert(!h);task.state=eSuspended;longjmp(suspended,1); }
static void vTaskDeleteWithCaps(TaskHandle_t h) { assert(h==&task && h->state==eSuspended);deleted++; }
static void vTaskDelete(TaskHandle_t h) { (void)h;assert(!"no forced or self deletion"); }
static void vTaskDelay(unsigned n);
typedef enum { CYM_TIME_UNSYNCED, CYM_TIME_GPS_LOCKED, CYM_TIME_RTC_HOLDOVER, CYM_TIME_GPS_RTC_HOLDOVER, CYM_TIME_NETWORK_SYNC, CYM_TIME_NTP_HOLDOVER, CYM_TIME_RTOS_HOLDOVER } source_t;
typedef struct { source_t source; uint32_t uncertainty_us; uint64_t last_gps_sync_epoch; } cym_time_snapshot_t;
static bool cym_timekeeper_snapshot(cym_time_snapshot_t *s) { *s=(cym_time_snapshot_t){.source=quality,.uncertainty_us=500000,.last_gps_sync_epoch=1700000000};return true; }
#define socket fake_socket
#define bind fake_bind
#define setsockopt fake_setsockopt
#define close fake_close
#define shutdown fake_shutdown
#define recvfrom fake_recvfrom
#define sendto fake_sendto
__PRODUCTION__
static void run_task(void) { if(!setjmp(suspended))task.fn(task.arg); }
static void vTaskDelay(unsigned n) {
    (void)n;delays++;
    if(reenter) { reenter=0;reenter_ok=(cym_ntp_server_start()==ESP_ERR_INVALID_STATE); }
    if(exit_after && delays>=exit_after && task.state!=eSuspended)run_task();
}
static int fake_recvfrom(int s,void *b,size_t n,int f,struct sockaddr *a,socklen_t *z) {
    (void)s;(void)n;(void)f;(void)z;
    if(packets++) { s_running=false;errno=EAGAIN;return -1; }
    memset(b,0,48);((uint8_t *)b)[0]=malformed?0:((4<<3)|3);
    for(int i=40;i<48;i++)((uint8_t *)b)[i]=i;
    ((struct sockaddr_in *)a)->sin_addr.s_addr=htonl(0x01020304);return 48;
}
int main(int argc,char **argv) {
    assert(argc==2);const char *c=argv[1];
    if(!strcmp(c,"socket"))fail_socket=1;
    if(!strcmp(c,"bind"))fail_bind=1;
    if(!strcmp(c,"option"))fail_option=1;
    if(!strcmp(c,"allocation"))fail_alloc=1;
    if(!strcmp(c,"internal"))psram=0;
    if(!strcmp(c,"debug"))debug_enabled=true;
    esp_err_t r=cym_ntp_server_start();
    if(fail_socket||fail_bind||fail_option||fail_alloc) {
        assert(r!=ESP_OK);assert(opened==closed);assert(log_count);log_count=0;fail_socket=fail_bind=fail_option=fail_alloc=0;
        assert(cym_ntp_server_start()==ESP_OK);
    } else assert(r==ESP_OK);
    if(!fail_socket && !fail_bind && !fail_option && !fail_alloc)assert(debug_enabled?log_count>0:log_count==0);
    assert(depth>=4096);assert(caps==((psram?MALLOC_CAP_SPIRAM:MALLOC_CAP_INTERNAL)|MALLOC_CAP_8BIT));
    if(!strcmp(c,"timeout")) {
        exit_after=0;assert(cym_ntp_server_stop_wait(30)==ESP_ERR_TIMEOUT);
        assert(!closed && !deleted && s_task);assert(cym_ntp_server_start()==ESP_ERR_INVALID_STATE);
        exit_after=1;
    }
    if(!strcmp(c,"delayed"))exit_after=5;
    if(!strcmp(c,"serialize"))reenter=1;
    if(!strncmp(c,"packet",6)) {
        quality=atoi(c+6);run_task();assert(replies==1);
        assert((response[0]&7)==4 && ((response[0]>>3)&7)==4);
        assert(response[1]==(quality==0?16:(quality==1||quality==2?1:2)));
        for(int i=0;i<8;i++)assert(response[24+i]==40+i);
        assert((response[0]>>6)==(quality==0?3:0));
    }
    if(!strcmp(c,"malformed")||!strcmp(c,"sendfail")) {
        malformed=!strcmp(c,"malformed");send_fail=!strcmp(c,"sendfail");run_task();
        cym_ntp_server_stats_t s;cym_ntp_server_get_stats(&s);
        assert(malformed?s.malformed_requests==1:s.send_failures==1);
    }
    assert(cym_ntp_server_stop_wait(100)==ESP_OK);assert(closed==opened && deleted==1);
    if(!strcmp(c,"serialize"))assert(reenter_ok);
    if(!strcmp(c,"delayed"))assert(delays>=5);
    assert(cym_ntp_server_stop_wait(0)==ESP_OK);
    assert(cym_ntp_server_start()==ESP_OK);assert(cym_ntp_server_stop_wait(100)==ESP_OK);
    assert(closed==opened && deleted==2);puts(c);return 0;
}
