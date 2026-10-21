
#define RTC_NOINIT_ATTR
#define BT_STAGE_ENABLED() DBG
#define BT_STAGE_GENERATION() (1u)
#define BT_STAGE_LOCK() ((void)0)
#define BT_STAGE_UNLOCK() ((void)0)
#define BT_STAGE_CURRENT(g,q,s,r) ((void)0)
#define BT_STAGE_PREVIOUS(g,q,s,r) ((void)0)
#define BT_STAGE_BOOT_STATUS(s,r) ((void)0)
#include "ble_stage_diag.h"

#define _XOPEN_SOURCE 700
#include <ucontext.h>
#include <setjmp.h>
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
static bool s_bt_resource_capture;static uint32_t s_bt_resource_failures;
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int BaseType_t;typedef unsigned TickType_t;typedef void *TaskHandle_t;
#define configTICK_RATE_HZ HZ
#define pdPASS 1
#define pdFAIL 0
#define pdTRUE 1
#define pdFALSE 0
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define TAG "probe"
#define configASSERT(x) assert(x)
#define taskIS_SCHEDULER_SUSPENDED() 0
#define prvENTER_CRITICAL_OR_SUSPEND_ALL(x) ((void)0)
#define prvEXIT_CRITICAL_OR_RESUME_ALL(x) 0
#define traceTASK_DELAY() ((void)0)
#define mtCOVERAGE_TEST_MARKER() ((void)0)
static volatile bool bt_scan_active,bt_scan_worker_busy,bt_scan_create_pending;
static bool s_bt_scan_api_busy,nimble_cleanup_busy;
static TaskHandle_t s_bt_transition_owner;
static void *wardrive_task_handle;static bool wardrive_active,wardrive_task_done,wdp_ble_cleanup_pending;
static uint32_t s_bt_cham_token;static TaskHandle_t s_bt_scan_owner,bt_scan_task_handle;
static bool ble_scan_finished,ble_scan_needs_ui_update,bt_locator_needs_ui_update,bt_sas_needs_update,ble_obs_store_pending;
static char ble_scan_status_text[80];static int g_bt_scan_duration_s=1,bt_device_count,bt_airtag_count,bt_smarttag_count;
static ucontext_t creator,worker;static char worker_stack[65536];static jmp_buf boundary;
static bool alive,blocked,deferred,creator_returned;static unsigned zero_yields,blocks,starts,cancels,feeds;
static int create_rc=pdPASS,start_rc,stop_failures;static bool early_cancel;
static void bt_scan_task(void*);
static bool in_worker;
static void scheduler_yield(void){
 if(!in_worker){blocked=false;if(alive)swapcontext(&creator,&worker);return;}
 if(blocked){blocked=false;in_worker=false;swapcontext(&worker,&creator);in_worker=true;return;}
 // Worker priority 5 remains ready; creator 1 and idle 0 are not eligible.
 if(++zero_yields==10000)longjmp(boundary,1);
}
#define portYIELD_WITHIN_API() scheduler_yield()
static void prvAddCurrentTaskToDelayedList(TickType_t ticks,int indefinite){assert(ticks>0);blocks++;blocked=true;}
static void task_entry(void){in_worker=true;bt_scan_task(NULL);assert(!"task returned");}
static int xTaskCreate(void(*f)(void*),const char*n,int stack,void*a,int priority,TaskHandle_t*out){
 assert(f==bt_scan_task&&stack==4096&&priority==5);
 if(create_rc!=pdPASS)return create_rc;
 *out=(void*)2;alive=true;getcontext(&worker);worker.uc_stack.ss_sp=worker_stack;worker.uc_stack.ss_size=sizeof(worker_stack);worker.uc_link=&creator;makecontext(&worker,task_entry,0);
 if(!deferred)swapcontext(&creator,&worker); // FreeRTOS ready-list immediate higher-priority preemption boundary.
 return pdPASS;
}
static void vTaskDelete(void*p){assert(p==NULL);alive=false;in_worker=false;setcontext(&creator);abort();}
static int bt_start_scan(void){starts++;return start_rc;}
static bool bt_stop_scan(void){cancels++;if(stop_failures){stop_failures--;return false;}return true;}
typedef enum { BT_SCAN_RUNNING, BT_SCAN_SUCCESS, BT_SCAN_CANCELLED, BT_SCAN_ERROR } bt_scan_outcome_t;
static bt_scan_outcome_t bt_scan_outcome = BT_SCAN_SUCCESS;

    #define pdMS_TO_TICKS( xTimeInMs )    ( ( TickType_t ) ( ( ( TickType_t ) ( xTimeInMs ) * ( TickType_t ) configTICK_RATE_HZ ) / ( TickType_t ) 1000U ) )
void vTaskDelay( const TickType_t xTicksToDelay )
    {
        BaseType_t xAlreadyYielded = pdFALSE;

        /* A delay time of zero just forces a reschedule. */
        if( xTicksToDelay > ( TickType_t ) 0U )
        {
            configASSERT( taskIS_SCHEDULER_SUSPENDED() == pdFALSE );
            prvENTER_CRITICAL_OR_SUSPEND_ALL( &xKernelLock );
            {
                traceTASK_DELAY();

                /* A task that is removed from the event list while the
                 * scheduler is suspended will not get placed in the ready
                 * list or removed from the blocked list until the scheduler
                 * is resumed.
                 *
                 * This task cannot be in an event list as it is the currently
                 * executing task. */
                prvAddCurrentTaskToDelayedList( xTicksToDelay, pdFALSE );
            }
            xAlreadyYielded = prvEXIT_CRITICAL_OR_RESUME_ALL( &xKernelLock );
        }
        else
        {
            mtCOVERAGE_TEST_MARKER();
        }

        /* Force a reschedule if xTaskResumeAll has not already done so, we may
         * have put ourselves to sleep. */
        if( xAlreadyYielded == pdFALSE )
        {
            portYIELD_WITHIN_API();
        }
        else
        {
            mtCOVERAGE_TEST_MARKER();
        }
    }
static BaseType_t bt_scan_worker_start(void)
{
    if (__atomic_test_and_set(&s_bt_scan_api_busy, __ATOMIC_ACQ_REL)) return pdFAIL;
    if (__atomic_load_n(&s_bt_transition_owner, __ATOMIC_ACQUIRE) ||
        wardrive_active || wardrive_task_handle || wdp_ble_cleanup_pending ||
        __atomic_load_n(&s_bt_cham_token, __ATOMIC_ACQUIRE) || s_bt_scan_owner ||
        __atomic_load_n(&nimble_cleanup_busy, __ATOMIC_ACQUIRE) ||
        __atomic_test_and_set(&bt_scan_worker_busy, __ATOMIC_ACQ_REL)) {
        __atomic_clear(&s_bt_scan_api_busy, __ATOMIC_RELEASE);
        return pdFAIL;
    }
    __atomic_store_n(&bt_scan_create_pending, true, __ATOMIC_RELEASE);
    __atomic_clear(&s_bt_scan_api_busy, __ATOMIC_RELEASE);
    __atomic_store_n(&bt_scan_active, true, __ATOMIC_RELEASE);
    ble_scan_finished = false;
    __atomic_store_n(&bt_scan_outcome, BT_SCAN_RUNNING, __ATOMIC_RELEASE);
    snprintf(ble_scan_status_text, sizeof(ble_scan_status_text), "Scanning...");
    // Keep dynamic RTOS storage internal and the existing 4096-byte stack.
    bt_stage(BT_ST_SCAN_CREATE,0);
    BaseType_t ret = xTaskCreate(bt_scan_task, "bt_scan_task", 4096, NULL, 5, &bt_scan_task_handle);
    bt_stage(BT_ST_SCAN_CREATE_RETURN,ret);
    if (ret != pdPASS) {
        bt_scan_task_handle = NULL;
        __atomic_store_n(&bt_scan_active, false, __ATOMIC_RELEASE);
        snprintf(ble_scan_status_text, sizeof(ble_scan_status_text), "Scan task unavailable; retry");
        __atomic_store_n(&bt_scan_outcome, BT_SCAN_ERROR, __ATOMIC_RELEASE);
        ble_scan_finished = true;
        ble_scan_needs_ui_update = bt_locator_needs_ui_update = bt_sas_needs_update = true;
    }
    __atomic_store_n(&bt_scan_create_pending, false, __ATOMIC_RELEASE);
    if (ret != pdPASS) __atomic_store_n(&bt_scan_worker_busy, false, __ATOMIC_RELEASE);
    return ret;
}
static void bt_scan_task(void *pvParameters)
{
    (void)pvParameters;
    bt_stage(BT_ST_WORKER_ENTER,__atomic_load_n(&bt_scan_create_pending,__ATOMIC_ACQUIRE));
    // Do not clear the handle before its creator publishes it.
    // One RTOS tick, not 1ms: at 100Hz a zero-tick yield starves the creator.
    while (__atomic_load_n(&bt_scan_create_pending, __ATOMIC_ACQUIRE))
        vTaskDelay(1);
    bt_stage(BT_ST_WORKER_PUBLISHED,0);
    bool started = __atomic_load_n(&bt_scan_active, __ATOMIC_ACQUIRE);
    __atomic_store_n(&s_bt_resource_failures, 0, __ATOMIC_RELAXED);
    __atomic_store_n(&s_bt_resource_capture, started, __ATOMIC_RELEASE);
    int rc = started ? bt_start_scan() : 0;
    int bt_scan_iters = (int)g_bt_scan_duration_s * 10;
    if (rc == 0) {
        for (int i = 0; i < bt_scan_iters && __atomic_load_n(&bt_scan_active, __ATOMIC_ACQUIRE); i++) {
            vTaskDelay(pdMS_TO_TICKS(100));
            if (__atomic_load_n(&s_bt_resource_failures, __ATOMIC_RELAXED)) break;
            if (i % 5 == 0) {
                snprintf(ble_scan_status_text, sizeof(ble_scan_status_text),
                         "Scanning... %d (%ds)", bt_device_count, (bt_scan_iters - i) / 10);
                ble_scan_needs_ui_update = bt_locator_needs_ui_update = bt_sas_needs_update = true;
            }
        }
        bool completed = started && __atomic_load_n(&bt_scan_active, __ATOMIC_ACQUIRE);
        // Cancel failure cannot authorize reuse; retain owner and retry yielding.
        while (started && !bt_stop_scan()) vTaskDelay(pdMS_TO_TICKS(100));
        snprintf(ble_scan_status_text, sizeof(ble_scan_status_text),
                 "%d devices (%d AT, %d ST)", bt_device_count, bt_airtag_count, bt_smarttag_count);
        if (!completed)
            snprintf(ble_scan_status_text, sizeof(ble_scan_status_text), "Scan cancelled; retry");
        bool exhausted = __atomic_load_n(&s_bt_resource_failures, __ATOMIC_RELAXED) != 0;
        if (exhausted)
            snprintf(ble_scan_status_text, sizeof(ble_scan_status_text), "Scan incomplete: memory pressure; retry");
        __atomic_store_n(&bt_scan_outcome, exhausted ? BT_SCAN_ERROR :
                         completed ? BT_SCAN_SUCCESS : BT_SCAN_CANCELLED, __ATOMIC_RELEASE);
        ble_obs_store_pending = true;
    } else {
        ESP_LOGE(TAG, "BLE scan start failed: %d", rc);
        snprintf(ble_scan_status_text, sizeof(ble_scan_status_text), "Scan start failed (%d); retry", rc);
        __atomic_store_n(&bt_scan_outcome, BT_SCAN_ERROR, __ATOMIC_RELEASE);
    }
    __atomic_store_n(&s_bt_resource_capture, false, __ATOMIC_RELEASE);
    __atomic_store_n(&bt_scan_active, false, __ATOMIC_RELEASE);
    ble_scan_finished = true;
    ble_scan_needs_ui_update = bt_locator_needs_ui_update = bt_sas_needs_update = true;
    bt_scan_task_handle = NULL;
    // No shared state or host API access beyond reservation release.
    __atomic_store_n(&bt_scan_worker_busy, false, __ATOMIC_RELEASE);
    vTaskDelete(NULL);
}
#define MALLOC_CAP_SPIRAM (1<<10)
#define MALLOC_CAP_8BIT (1<<2)
#define MALLOC_CAP_DMA (1<<3)
static bool s_bt_alloc_capture,s_bt_alloc_name_busy;
static char s_bt_alloc_function[32];
static uint32_t s_bt_alloc_failures,s_bt_alloc_dma_failures,s_bt_alloc_last_size,s_bt_alloc_last_caps;
static void bt_alloc_failed(size_t size, uint32_t caps, const char *function_name)
{
    if (__atomic_load_n(&s_bt_resource_capture, __ATOMIC_RELAXED))
        __atomic_fetch_add(&s_bt_resource_failures, 1, __ATOMIC_RELAXED);
    if (!__atomic_load_n(&s_bt_alloc_capture, __ATOMIC_RELAXED)) return;
    // Best-effort bounded first function name in this diagnostic window. Never
    // allocate/log or wait in the heap hook. Name is the public allocator boundary.
    if (!__atomic_test_and_set(&s_bt_alloc_name_busy, __ATOMIC_ACQUIRE)) {
        if (!s_bt_alloc_function[0] && function_name) {
            unsigned i = 0;
            for (; i + 1 < sizeof(s_bt_alloc_function) && function_name[i]; ++i)
                s_bt_alloc_function[i] = function_name[i];
            s_bt_alloc_function[i] = 0;
        }
        __atomic_clear(&s_bt_alloc_name_busy, __ATOMIC_RELEASE);
    }
    __atomic_fetch_add(&s_bt_alloc_failures, 1, __ATOMIC_RELAXED);
    if (caps & MALLOC_CAP_DMA)
        __atomic_fetch_add(&s_bt_alloc_dma_failures, 1, __ATOMIC_RELAXED);
    __atomic_store_n(&s_bt_alloc_last_size, (uint32_t)size, __ATOMIC_RELAXED);
    __atomic_store_n(&s_bt_alloc_last_caps, caps, __ATOMIC_RELAXED);
}
static void *heap_caps_malloc(size_t n,uint32_t c){if(c&MALLOC_CAP_SPIRAM){bt_alloc_failed(n,c,"heap_caps_malloc");return NULL;}return malloc(n);}
static void *heap_caps_realloc(void*p,size_t n,uint32_t c){if(c&MALLOC_CAP_SPIRAM){bt_alloc_failed(n,c,"heap_caps_realloc");return NULL;}return realloc(p,n);}
static void heap_caps_free(void*p){free(p);}
void* lvgl_malloc(size_t size)
{
    if (size == 0) return NULL;
    void *ptr = heap_caps_malloc(size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (ptr == NULL) {
        ptr = heap_caps_malloc(size, MALLOC_CAP_8BIT);
        if (ptr == NULL)
            ESP_LOGE(TAG, "OOM: failed to allocate %zu bytes", size);
    }
    return ptr;
}
void lvgl_free(void* ptr)
{
    if (ptr == NULL) return;
    heap_caps_free(ptr);
}
void* lvgl_realloc(void* ptr, size_t new_size)
{
    if (new_size == 0) { lvgl_free(ptr); return NULL; }
    if (ptr == NULL) return lvgl_malloc(new_size);
    void *np = heap_caps_realloc(ptr, new_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (np == NULL) np = heap_caps_realloc(ptr, new_size, MALLOC_CAP_8BIT);
    return np;
}
int main(int argc,char**argv){
 assert(argc==2);deferred=true;g_bt_scan_duration_s=10;s_bt_alloc_capture=DBG;
 bool inject=!strcmp(argv[1],"malloc")||!strcmp(argv[1],"realloc")||!strcmp(argv[1],"cancel");
 bool user_cancel=!strcmp(argv[1],"cancel");
 bool fail_start=!strcmp(argv[1],"start-fail");
 if(fail_start)start_rc=7;
 if(!strcmp(argv[1],"create-fail")){create_rc=pdFAIL;assert(bt_scan_worker_start()==pdFAIL);assert(!alive&&!bt_scan_worker_busy&&!bt_scan_create_pending&&!bt_scan_task_handle&&bt_scan_outcome==BT_SCAN_ERROR);return 0;}
 if(!strcmp(argv[1],"early-cancel")){assert(bt_scan_worker_start()==pdPASS);bt_scan_active=false;swapcontext(&creator,&worker);assert(!alive&&starts==0&&cancels==0&&bt_scan_outcome==BT_SCAN_CANCELLED);return 0;}
 if(!strcmp(argv[1],"cancel-retry"))stop_failures=3;
 assert(bt_scan_worker_start()==pdPASS);swapcontext(&creator,&worker);
 if(fail_start){assert(!alive&&bt_scan_outcome==BT_SCAN_ERROR&&cancels==0);puts("PASS start-error preserved");return 0;}
 assert(alive&&s_bt_resource_capture);
 unsigned polls=1;
 if(inject){void*p=lvgl_malloc(10240);assert(p);if(!strcmp(argv[1],"realloc")){p=lvgl_realloc(p,10240);assert(p);}lvgl_free(p);}
 if(user_cancel)bt_scan_active=false;
 while(alive&&polls<110){swapcontext(&creator,&worker);if(alive)polls++;}
 assert(!alive&&cancels==(!strcmp(argv[1],"cancel-retry")?4:1));
 assert(bt_scan_outcome==((inject&&!CLASSIC)?BT_SCAN_ERROR:user_cancel?BT_SCAN_CANCELLED:BT_SCAN_SUCCESS));
 assert(polls==((user_cancel||(inject&&!CLASSIC))?1:(!strcmp(argv[1],"cancel-retry")?103:100)));
 assert(s_bt_alloc_failures==(DBG&&inject?(!strcmp(argv[1],"realloc")?2:1):0));
 assert(!s_bt_resource_capture&&!bt_scan_worker_busy&&!bt_scan_task_handle);
 printf("PASS case=%s debug=%d successful_fallback=%d polls=%u modeled_ms=%u resource_failures=%u diagnostics=%u status=%s\n",argv[1],DBG,inject,polls,polls*100,s_bt_resource_failures,s_bt_alloc_failures,ble_scan_status_text);
}
