/* Worker never calls LVGL, never obtains an LVGL/display/SD lock for capture
 * or decoding. UI polls one latest preview and a single locked result. */
#include "qr_decoder_ui.h"
#include "cym_camera.h"
#include "cym_qr.h"
#include "qr_record.h"
#include "qr_preview.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_memory_utils.h"
#include "debug_settings.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <stdatomic.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/* Suspension-based stack reclaim is audited only for single-core C5. */
#if !CONFIG_IDF_TARGET_ESP32C5 || !CONFIG_FREERTOS_UNICORE || !CONFIG_FREERTOS_TASK_CREATE_ALLOW_EXT_MEM
#error "QR external-stack lifecycle requires the audited single-core C5 configuration"
#endif
#define QR_STACK_BYTES 24576
#define QR_STACK_CAPS (MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)
#define QR_TCB_CAPS (MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)
#define PREVIEW_W 120
#define PREVIEW_H 160
#define DISPLAY_CAP (CYM_QR_MAX_PAYLOAD*4+1)
typedef enum { QR_STARTING,QR_SCANNING,QR_SAVING,QR_RESULT,QR_ERROR } qr_phase_t;
typedef struct {
    atomic_bool cancel,done;
    atomic_uint capture_generation;
    atomic_int capture; /* 0 idle, 1 requested, 2 writing, 3 completion */
    char capture_status[128],activity[192];
    qr_ui_options_t options;
    int preview_w,preview_h;
    uint32_t frames,timeouts,errors,processed,normal,mirror,candidates,decode_errors[CYM_QR_ERROR_COUNT];
    unsigned min_gray,max_gray,mean_gray,dark,light;
    int width,height,format,last_error;
    size_t stride;
    int64_t report_at,started,decode_us,max_decode_us;
    bool result_shown,text_shown;

    TaskHandle_t task;
    StackType_t *stack;
    StaticTask_t *tcb;
    atomic_int phase;
    SemaphoreHandle_t preview_lock;
    void *bus;
    qr_ui_save_fn save;
    uint8_t *gray,*payload;
    uint16_t *latest,*display;
    char *text;
    char status[128];
    bool fresh;
    cym_camera_t *camera;
    cym_qr_t *decoder;
    lv_img_dsc_t image;
} qr_session_t;
static qr_session_t *session;
static lv_obj_t *status_label,*result_label,*preview,*retry_button;
static lv_timer_t *poll_timer;
static lv_obj_t *capture_button,*capture_label,*activity_label;
static qr_ui_options_t style;
static void theme_button(lv_obj_t *button)
{
    lv_obj_set_style_bg_color(button,style.card,0);
    lv_obj_set_style_bg_color(button,style.pressed,LV_STATE_PRESSED);
    lv_obj_set_style_text_color(button,style.text,0);
    lv_obj_set_style_text_color(button,style.muted,LV_STATE_DISABLED);
    lv_obj_set_style_bg_color(button,style.card,LV_STATE_DISABLED);
    lv_obj_set_style_border_color(button,style.accent,0);
    lv_obj_set_style_border_width(button,1,0);
    lv_obj_set_style_radius(button,6,0);
    lv_obj_set_style_pad_all(button,6,0);
}
/* Finite transition markers; no payload or frame bytes ever enter logs. */
static void transition(const char *stage,int value)
{if(cym_debug_enabled())ESP_LOGI("qr","stage=%s value=%d",stage,value);}
static void report(qr_session_t *s,bool final)
{
    if(!cym_debug_enabled())return;
    int64_t now=esp_timer_get_time();if(!final&&now-s->report_at<5000000)return;s->report_at=now;
    ESP_LOGI("qr","frames=%u timeouts=%u errors=%u last_error=%d size=%dx%d stride=%u format=%d rotation=%u gray_min=%u max=%u mean=%u dark=%u light=%u processed=%u elapsed_ms=%u decode_millifps=%u decode_us=%llu max_decode_us=%u candidates=%u normal=%u mirror=%u",
        (unsigned)s->frames,(unsigned)s->timeouts,(unsigned)s->errors,s->last_error,s->width,s->height,(unsigned)s->stride,s->format,s->options.rotation*90,
        s->min_gray,s->max_gray,s->mean_gray,s->dark,s->light,(unsigned)s->processed,(unsigned)((now-s->started)/1000),(unsigned)(s->processed*1000000000ULL/(now>s->started?now-s->started:1)),(unsigned long long)s->decode_us,(unsigned)s->max_decode_us,
        (unsigned)s->candidates,(unsigned)s->normal,(unsigned)s->mirror);
    ESP_LOGI("qr","SUCCESS=%u INVALID_GRID_SIZE=%u INVALID_VERSION=%u FORMAT_ECC=%u DATA_ECC=%u UNKNOWN_DATA_TYPE=%u DATA_OVERFLOW=%u DATA_UNDERFLOW=%u",
        (unsigned)s->decode_errors[0],(unsigned)s->decode_errors[1],(unsigned)s->decode_errors[2],(unsigned)s->decode_errors[3],(unsigned)s->decode_errors[4],(unsigned)s->decode_errors[5],(unsigned)s->decode_errors[6],(unsigned)s->decode_errors[7]);
    if(xSemaphoreTake(s->preview_lock,0)==pdTRUE){
        snprintf(s->activity,sizeof(s->activity),"Debug: frames %u / decoded frames %u / candidates %u",(unsigned)s->frames,(unsigned)s->processed,(unsigned)s->candidates);
        xSemaphoreGive(s->preview_lock);
    }
}
static void gray_stats(qr_session_t *s)
{
    unsigned sum=0;s->min_gray=255;s->max_gray=s->dark=s->light=0;
    for(unsigned i=0;i<240*320;i++){
        unsigned v=s->gray[i];sum+=v;
        if(v<s->min_gray)s->min_gray=v;
        if(v>s->max_gray)s->max_gray=v;
        s->dark+=v<64;s->light+=v>191;
    }
    s->mean_gray=sum/(240*320);
}
/* Worker-only snapshot and card callback. UI never copies pixels or waits for
 * SD. One pending request; toggling debug off or Back cancels before write. */
static void capture_frame(qr_session_t *s,const cym_qr_stats_t *stats)
{
    if(!cym_debug_enabled()||atomic_load(&s->cancel)||atomic_load(&s->capture_generation)!=cym_debug_generation()){atomic_store(&s->capture,0);return;}
    int expected=1;if(!atomic_compare_exchange_strong(&s->capture,&expected,2))return;
    uint8_t *snapshot=heap_caps_malloc(240*320,QR_STACK_CAPS);
    int e=ENOMEM;char name[40]={0},meta[640];
    if(snapshot){
        memcpy(snapshot,s->gray,240*320);
        snprintf(meta,sizeof(meta),"width=240 height=320 stride=240 source_stride=%u format=RGB565_LE rotation=%u decoder_rotation=0 min=%u max=%u mean=%u dark=%u light=%u frames=%u processed=%u candidates=%u normal=%u mirror=%u errors=%u,%u,%u,%u,%u,%u,%u,%u",
            (unsigned)s->stride,s->options.rotation*90,s->min_gray,s->max_gray,s->mean_gray,s->dark,s->light,(unsigned)s->frames,(unsigned)s->processed,(unsigned)stats->candidates,(unsigned)stats->normal_attempts,(unsigned)stats->mirror_attempts,
            (unsigned)stats->errors[0],(unsigned)stats->errors[1],(unsigned)stats->errors[2],(unsigned)stats->errors[3],(unsigned)stats->errors[4],(unsigned)stats->errors[5],(unsigned)stats->errors[6],(unsigned)stats->errors[7]);
        if(!cym_debug_enabled()||atomic_load(&s->cancel)||atomic_load(&s->capture_generation)!=cym_debug_generation())e=ECANCELED;
        else e=s->options.save_frame?s->options.save_frame(snapshot,240,320,240,meta,name,sizeof(name)):ENOSYS;
        memset(snapshot,0,240*320);free(snapshot);
    }
    if(!e)snprintf(s->capture_status,sizeof(s->capture_status),"Saved debug/%s",name);
    else snprintf(s->capture_status,sizeof(s->capture_status),"Frame not saved: %s. Retry.",strerror(e));
    transition("debug_frame_complete",e);atomic_store(&s->capture,3);
}

/* Startup/failure-only logs use the existing debug gate and primary USB
 * console. Never print payloads or enable debug implicitly. */
static void qr_diag(const char *stage,int error,unsigned caps,size_t bytes)
{
    if(!cym_debug_enabled())return;
    ESP_LOGI("qr_start", "stage=%s error=%d caps=0x%x bytes=%u internal_free=%u internal_largest=%u DMA_free=%u DMA_largest=%u psram_free=%u psram_largest=%u",
        stage,error,caps,(unsigned)bytes,
        (unsigned)heap_caps_get_free_size(QR_TCB_CAPS),
        (unsigned)heap_caps_get_largest_free_block(QR_TCB_CAPS),
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA),
        (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA),
        (unsigned)heap_caps_get_free_size(QR_STACK_CAPS),
        (unsigned)heap_caps_get_largest_free_block(QR_STACK_CAPS));
}
/* done is not a join. Only the UI owner reaps; nobody resumes this private
 * worker. On single-core C5, eSuspended proves the switch off its stack has
 * completed. Static-task vTaskDelete performs synchronous kernel/TLS cleanup
 * before caller-owned stack/TCB release: no idle/free race or cleanup task. */
static bool reap(qr_session_t *s)
{
    if(!atomic_load(&s->done))return false;
    if(s->task){
        if(eTaskGetState(s->task)!=eSuspended)return false;
        vTaskDelete(s->task);
        s->task=NULL;
        free(s->stack);s->stack=NULL;
        free(s->tcb);s->tcb=NULL;
    }
    return true;
}
static void worker(void *arg)
{
    qr_session_t *s=arg;
    s->started=s->report_at=esp_timer_get_time();
    if(cym_debug_enabled())ESP_LOGI("qr_start","stage=worker_enter stack_psram=%d stack_bytes=%u stack_hwm=%u",
        esp_ptr_external_ram(s->stack),QR_STACK_BYTES,(unsigned)uxTaskGetStackHighWaterMark(NULL));
    /* No flash/NVS/OTA APIs on this external stack. Camera/I2C/PARLIO and
     * FAT/SD save keep caches enabled; ISR/control/DMA descriptors stay internal. */
    esp_err_t error=atomic_load(&s->cancel)?ESP_OK:cym_camera_open(&s->camera,s->bus);
    qr_diag("camera_open",error,0,0);
    if(atomic_load(&s->cancel))goto finish;
    if(error)goto finish;
    s->decoder=cym_qr_create(240,320);
    if(!s->decoder){error=ESP_ERR_NO_MEM;qr_diag("decoder_create",error,QR_STACK_CAPS,0);goto finish;}
    atomic_store(&s->phase,QR_SCANNING);
    unsigned failures=0;
    while(!atomic_load(&s->cancel)){
        cym_camera_frame_t frame;
        error=cym_camera_acquire(s->camera,&frame,250);
        if(error){
            s->last_error=error;if(error==ESP_ERR_TIMEOUT)s->timeouts++;else s->errors++;
            report(s,false);
            if(++failures>=12)break;
            vTaskDelay(pdMS_TO_TICKS(50));continue;
        }
        failures=0;s->frames++;
        s->width=frame.width;s->height=frame.height;s->stride=frame.stride;s->format=frame.format;
        /* Reject unexpected buffers before conversion/remap; no overflow or
         * silent wrong stride. Backend contract is native 240x320 RGB565 LE. */
        if(frame.width!=240||frame.height!=320||frame.stride<480||frame.format!=CYM_CAMERA_RGB565_LE){
            cym_camera_release(s->camera);error=ESP_ERR_INVALID_RESPONSE;s->errors++;break;
        }
        cym_qr_rgb565_gray(frame.data,frame.stride,s->gray,frame.width,frame.height);
        if(xSemaphoreTake(s->preview_lock,0)==pdTRUE){
            qr_preview_rgb565(frame.data,frame.stride,frame.width,frame.height,s->options.rotation,
                              s->latest,s->preview_w,s->preview_h);
            s->fresh=true;xSemaphoreGive(s->preview_lock);
        }
        cym_camera_release(s->camera);
        if(atomic_load(&s->cancel))break;
        cym_qr_stats_t stats;
        int64_t before=esp_timer_get_time();
        int n=cym_qr_decode_gray_ex(s->decoder,s->gray,240,s->payload,CYM_QR_MAX_PAYLOAD,&stats);
        int64_t elapsed=esp_timer_get_time()-before;s->decode_us+=elapsed;
        if(elapsed>s->max_decode_us)s->max_decode_us=elapsed;
        s->processed++;s->candidates+=stats.candidates;s->normal+=stats.normal_attempts;s->mirror+=stats.mirror_attempts;
        for(unsigned i=0;i<CYM_QR_ERROR_COUNT;i++)s->decode_errors[i]+=stats.errors[i];
        if(cym_debug_enabled())gray_stats(s);
        capture_frame(s,&stats);report(s,false);
        if(n>=0&&stats.valid){
            /* Immutable escaped text is published BEFORE potentially slow close
             * or SD. UI may read it, but must never reclaim a live worker. */
            cym_qr_escape(s->payload,(size_t)n,s->text,DISPLAY_CAP);
            atomic_store(&s->phase,QR_SAVING);transition("decoded_payload_length",n);
            transition("camera_close_begin",0);
            int close_error=cym_camera_close(&s->camera);
            transition("camera_close_end",close_error);
            char name[40]={0};transition("record_save_begin",0);
            int save_error=atomic_load(&s->cancel)?ECANCELED:s->save(s->payload,(size_t)n,name,sizeof(name));
            transition("record_save_end",save_error);
            if(!save_error)snprintf(s->status,sizeof(s->status),"QR Code - %d bytes\nSaved %s%s",n,name,close_error?"\nCamera stop incomplete; restart blocked":"");
            else snprintf(s->status,sizeof(s->status),"QR Code - %d bytes\nNot saved: %s%s",n,strerror(save_error),close_error?"\nCamera stop incomplete; restart blocked":"");
            atomic_store(&s->phase,QR_RESULT);transition("result_published",save_error);
            error=ESP_OK;break;
        }
        /* No queued backlog; one image per bounded acquisition/decode cycle. */
        vTaskDelay(pdMS_TO_TICKS(100));
    }
finish:
    report(s,true);
    if(s->camera){esp_err_t e=cym_camera_close(&s->camera);if(e&&atomic_load(&s->phase)!=QR_RESULT)error=e;}
    if(s->decoder){cym_qr_destroy(s->decoder);s->decoder=NULL;}
    if(error){snprintf(s->status,sizeof(s->status),"Camera unavailable (%s). Retry or Back.",esp_err_to_name(error));atomic_store(&s->phase,QR_ERROR);}
    /* Retained camera blocks reentry. Publish after all context work; the UI
     * must still observe actual suspension before reclaiming task storage. */
    memset(s->payload,0,CYM_QR_MAX_PAYLOAD);
    if(atomic_load(&s->cancel))memset(s->text,0,DISPLAY_CAP);
    qr_diag(s->camera?"camera_retained":"worker_complete",error,0,0);
    if(cym_debug_enabled())ESP_LOGI("qr_start","stage=worker_park stack_hwm=%u",(unsigned)uxTaskGetStackHighWaterMark(NULL));
    atomic_store(&s->done,true);
    /* No access to s after publication, including in this suspend loop. */
    for(;;)vTaskSuspend(NULL);
}
static void dispose(qr_session_t *s)
{
    if(!s)return;
    if(s->camera||s->task)return; /* retain ISR/DMA or live stack ownership */
    if(s->preview_lock)vSemaphoreDelete(s->preview_lock);
    if(s->payload)memset(s->payload,0,CYM_QR_MAX_PAYLOAD);
    if(s->text)memset(s->text,0,DISPLAY_CAP);
    free(s->gray);free(s->payload);free(s->latest);free(s->display);free(s->text);free(s);
}
static void poll(lv_timer_t *timer)
{
    (void)timer;qr_session_t *s=session;
    if(!s||!status_label)return;
    int phase=atomic_load(&s->phase);
    if(capture_button){
        bool enabled=cym_debug_enabled()&&phase==QR_SCANNING;
        if(enabled){lv_obj_clear_flag(capture_button,LV_OBJ_FLAG_HIDDEN);lv_obj_clear_flag(capture_label,LV_OBJ_FLAG_HIDDEN);lv_obj_clear_flag(activity_label,LV_OBJ_FLAG_HIDDEN);}
        else {lv_obj_add_flag(capture_button,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(capture_label,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(activity_label,LV_OBJ_FLAG_HIDDEN);int expected=1;atomic_compare_exchange_strong(&s->capture,&expected,0);}
        int capture=atomic_load(&s->capture);
        if(capture==1||capture==2){lv_obj_add_state(capture_button,LV_STATE_DISABLED);lv_label_set_text(capture_label,"Saving one camera image... Back cancels pending work");}
        else {lv_obj_clear_state(capture_button,LV_STATE_DISABLED);
            if(capture==3){lv_label_set_text(capture_label,s->capture_status);atomic_store(&s->capture,0);}}
    }
    if(phase==QR_SCANNING){
        lv_label_set_text(status_label,"Point camera at QR code\nKeep code inside the frame");
        if(xSemaphoreTake(s->preview_lock,0)==pdTRUE){
            if(s->fresh){memcpy(s->display,s->latest,PREVIEW_W*PREVIEW_H*2);s->fresh=false;lv_obj_invalidate(preview);}
            if(cym_debug_enabled()&&activity_label)lv_label_set_text(activity_label,s->activity);
            xSemaphoreGive(s->preview_lock);
        }
    }else if(phase==QR_SAVING){
        lv_obj_add_flag(preview,LV_OBJ_FLAG_HIDDEN);
        if(!s->text_shown){lv_label_set_text_static(result_label,s->text);lv_obj_clear_flag(result_label,LV_OBJ_FLAG_HIDDEN);s->text_shown=true;transition("decoded_displayed_saving",0);}
        lv_label_set_text(status_label,"QR decoded - Saving record / stopping camera...");
    }else if((phase==QR_RESULT||phase==QR_ERROR)&&reap(s)){
        if(!s->result_shown){
            lv_label_set_text(status_label,s->status);
            lv_obj_add_flag(preview,LV_OBJ_FLAG_HIDDEN);
            if(phase==QR_RESULT&&!s->text_shown){lv_label_set_text_static(result_label,s->text);lv_obj_clear_flag(result_label,LV_OBJ_FLAG_HIDDEN);s->text_shown=true;}
            lv_obj_clear_flag(retry_button,LV_OBJ_FLAG_HIDDEN);
            transition(phase==QR_RESULT?"result_displayed":"error_displayed",phase);s->result_shown=true;
        }
    }
}
void qr_decoder_ui_stop(void)
{
    if(poll_timer){lv_timer_del(poll_timer);poll_timer=NULL;}
    if(result_label)lv_label_set_text_static(result_label,"");
    if(preview)lv_img_set_src(preview,NULL);
    if(session)lv_img_cache_invalidate_src(&session->image);
    status_label=result_label=preview=retry_button=NULL;
    capture_button=capture_label=activity_label=NULL;
    transition("ui_stop",0);
    qr_session_t *s=session;if(!s)return;
    atomic_store(&s->cancel,true);
    /* Worker has no LVGL dependency. Never wait for an LVGL callback/lock.
     * Slow init/storage timeout retains context; the next open may reap it. */
    for(unsigned i=0;i<300&&!reap(s);i++)vTaskDelay(pdMS_TO_TICKS(10));
    if(reap(s)&&!s->camera){session=NULL;dispose(s);}
}
static void start(void)
{
    qr_session_t *s=session;
    if(s->task&&!reap(s))return;
    atomic_store(&s->phase,QR_STARTING);atomic_store(&s->done,false);atomic_store(&s->cancel,false);
    s->result_shown=s->text_shown=false;atomic_store(&s->capture,0);
    s->frames=s->timeouts=s->errors=s->processed=s->normal=s->mirror=s->candidates=0;
    memset(s->decode_errors,0,sizeof(s->decode_errors));
    s->min_gray=s->max_gray=s->mean_gray=s->dark=s->light=0;
    s->width=s->height=s->format=s->last_error=0;s->stride=0;
    s->decode_us=s->max_decode_us=0;s->activity[0]=0;
    lv_label_set_text(capture_label,"Saves camera image; may contain private QR content. Press only to consent.");
    s->text[0]=0;memset(s->payload,0,CYM_QR_MAX_PAYLOAD);
    lv_label_set_text_static(result_label,"");lv_obj_add_flag(result_label,LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(preview,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(retry_button,LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(status_label,"Starting camera...");
    /* Keep quirc's sizeable RS workspace budget; do not shrink to fit a 2KB
     * internal largest block. Only the small kernel TCB consumes internal RAM. */
    qr_diag("stack_alloc",0,QR_STACK_CAPS,QR_STACK_BYTES);
    s->stack=heap_caps_malloc(QR_STACK_BYTES,QR_STACK_CAPS);
    if(!s->stack){qr_diag("stack_alloc",ESP_ERR_NO_MEM,QR_STACK_CAPS,QR_STACK_BYTES);goto failed;}
    s->tcb=heap_caps_malloc(sizeof(*s->tcb),QR_TCB_CAPS);
    if(!s->tcb){qr_diag("tcb_alloc",ESP_ERR_NO_MEM,QR_TCB_CAPS,sizeof(*s->tcb));goto failed;}
    s->task=xTaskCreateStatic(worker,"qr_scan",QR_STACK_BYTES,s,2,s->stack,s->tcb);
    if(!s->task){qr_diag("task_create",ESP_ERR_NO_MEM,QR_STACK_CAPS,QR_STACK_BYTES);goto failed;}
    return;
failed:
    free(s->stack);s->stack=NULL;free(s->tcb);s->tcb=NULL;
    strcpy(s->status,"Not enough worker memory. Retry or Back.");
    atomic_store(&s->phase,QR_ERROR);atomic_store(&s->done,true);
}
static void retry(lv_event_t *event)
{
    (void)event;
    if(!session||!reap(session))return;
    if(session->camera){lv_label_set_text(status_label,"Camera stop incomplete. Restart blocked; reboot required.");return;}
    start();
}
static void request_capture(lv_event_t *event)
{
    (void)event;
    if(!session||!cym_debug_enabled()||atomic_load(&session->phase)!=QR_SCANNING)return;
    if(atomic_load(&session->capture)!=0)return;
    atomic_store(&session->capture_generation,cym_debug_generation());
    int expected=0;atomic_compare_exchange_strong(&session->capture,&expected,1);
}
void qr_decoder_ui_open(lv_obj_t *page,void *bus,qr_ui_save_fn save,const qr_ui_options_t *options)
{
    if(!options)return;
    style=*options;
    lv_obj_set_style_text_color(page,style.text,0);lv_obj_set_style_text_font(page,style.font,0);
    if(session&&reap(session)&&!session->camera){dispose(session);session=NULL;}
    if(session){lv_obj_t *label=lv_label_create(page);lv_label_set_text(label,atomic_load(&session->done)&&session->camera?"Camera stop incomplete. Restart blocked; reboot required.":"Previous camera is stopping. Back and retry later.");return;}
    qr_session_t *s=heap_caps_calloc(1,sizeof(*s),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(s){
        s->gray=heap_caps_malloc(240*320,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        s->payload=heap_caps_malloc(CYM_QR_MAX_PAYLOAD,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        s->latest=heap_caps_calloc(PREVIEW_W*PREVIEW_H,2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        s->display=heap_caps_calloc(PREVIEW_W*PREVIEW_H,2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        s->text=heap_caps_calloc(1,DISPLAY_CAP,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        s->preview_lock=xSemaphoreCreateMutex();
    }
    if(!s||!s->gray||!s->payload||!s->latest||!s->display||!s->text||!s->preview_lock){
        dispose(s);lv_obj_t *label=lv_label_create(page);lv_label_set_text(label,"Insufficient PSRAM. Back to exit.");return;
    }
    s->bus=bus;s->save=save;s->options=*options;s->options.rotation&=3;session=s;
    qr_preview_size(PREVIEW_W,PREVIEW_H,s->options.rotation,&s->preview_w,&s->preview_h);
    lv_obj_t *body=lv_obj_create(page);
    lv_obj_set_style_bg_color(body,style.panel,0);lv_obj_set_style_border_color(body,style.border,0);
    lv_obj_set_style_text_color(body,style.text,0);lv_obj_set_style_text_font(body,style.font,0);
    lv_obj_set_style_pad_all(body,6,0);lv_obj_set_style_pad_gap(body,6,0);
    lv_obj_set_style_bg_color(body,style.accent,LV_PART_SCROLLBAR);
    lv_obj_set_width(body,lv_pct(100));lv_obj_set_height(body,lv_disp_get_ver_res(NULL)-40);
    lv_obj_align(body,LV_ALIGN_BOTTOM_MID,0,0);lv_obj_set_flex_flow(body,LV_FLEX_FLOW_COLUMN);
    lv_obj_set_scroll_dir(body,LV_DIR_VER);lv_obj_set_scrollbar_mode(body,LV_SCROLLBAR_MODE_AUTO);
    status_label=lv_label_create(body);lv_obj_set_width(status_label,lv_pct(100));lv_label_set_long_mode(status_label,LV_LABEL_LONG_WRAP);
    lv_label_set_recolor(status_label,false);
    s->image.header.cf=LV_IMG_CF_TRUE_COLOR;s->image.header.w=s->preview_w;s->image.header.h=s->preview_h;
    s->image.data_size=PREVIEW_W*PREVIEW_H*2;s->image.data=(const uint8_t *)s->display;
    preview=lv_img_create(body);lv_img_set_src(preview,&s->image);
    lv_obj_set_style_border_width(preview,2,0);lv_obj_set_style_border_color(preview,style.accent,0);
    /* Actions precede unbounded result text, keeping Scan Again visible. The
     * body scrolls below the existing global Back/Home title bar. ASCII only. */
    retry_button=lv_btn_create(body);theme_button(retry_button);lv_obj_add_event_cb(retry_button,retry,LV_EVENT_CLICKED,NULL);
    lv_obj_t *caption=lv_label_create(retry_button);lv_label_set_text(caption,"Scan Again / Retry");
    capture_button=lv_btn_create(body);theme_button(capture_button);lv_obj_add_event_cb(capture_button,request_capture,LV_EVENT_CLICKED,NULL);
    caption=lv_label_create(capture_button);lv_label_set_text(caption,"Save Debug Frame");
    capture_label=lv_label_create(body);lv_obj_set_width(capture_label,lv_pct(100));lv_label_set_long_mode(capture_label,LV_LABEL_LONG_WRAP);
    lv_label_set_text(capture_label,"Saves camera image; may contain private QR content. Press only to consent.");
    lv_obj_set_style_text_color(capture_label,style.muted,0);
    activity_label=lv_label_create(body);lv_obj_set_width(activity_label,lv_pct(100));lv_label_set_long_mode(activity_label,LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_color(activity_label,style.muted,0);
    if(!cym_debug_enabled()){lv_obj_add_flag(capture_button,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(capture_label,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(activity_label,LV_OBJ_FLAG_HIDDEN);}
    result_label=lv_label_create(body);lv_obj_set_width(result_label,lv_pct(100));lv_label_set_long_mode(result_label,LV_LABEL_LONG_WRAP);
    lv_label_set_recolor(result_label,false);
    poll_timer=lv_timer_create(poll,100,NULL);
    if(!poll_timer){strcpy(s->status,"UI timer unavailable. Back to exit.");lv_label_set_text(status_label,s->status);atomic_store(&s->done,true);return;}
    start();
}
