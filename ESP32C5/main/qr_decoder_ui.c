/* Worker never calls LVGL, never obtains an LVGL/display/SD lock for capture
 * or decoding. UI polls one latest preview and a single locked result. */
#include "qr_decoder_ui.h"
#include "cym_camera.h"
#include "cym_qr.h"
#include "qr_record.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <stdatomic.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define PREVIEW_W 120
#define PREVIEW_H 160
#define DISPLAY_CAP (CYM_QR_MAX_PAYLOAD*4+1)
typedef enum { QR_STARTING,QR_SCANNING,QR_RESULT,QR_ERROR } qr_phase_t;
typedef struct {
    atomic_bool cancel,done;
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
static void worker(void *arg)
{
    qr_session_t *s=arg;
    esp_err_t error=cym_camera_open(&s->camera,s->bus);
    if(error)goto finish;
    s->decoder=cym_qr_create(240,320);
    if(!s->decoder){error=ESP_ERR_NO_MEM;goto finish;}
    atomic_store(&s->phase,QR_SCANNING);
    unsigned failures=0;
    while(!atomic_load(&s->cancel)){
        cym_camera_frame_t frame;
        error=cym_camera_acquire(s->camera,&frame,250);
        if(error){
            if(++failures>=12)break;
            vTaskDelay(pdMS_TO_TICKS(50));continue;
        }
        failures=0;
        cym_qr_rgb565_gray(frame.data,frame.stride,s->gray,frame.width,frame.height);
        if(xSemaphoreTake(s->preview_lock,0)==pdTRUE){
            for(int y=0;y<PREVIEW_H;y++)for(int x=0;x<PREVIEW_W;x++){
                const uint8_t *p=frame.data+(y*2)*frame.stride+x*4;
                /* CYM LVGL is 16-bit byte-swapped; decoder uses original LE. */
                s->latest[y*PREVIEW_W+x]=((uint16_t)p[0]<<8)|p[1];
            }
            s->fresh=true;xSemaphoreGive(s->preview_lock);
        }
        cym_camera_release(s->camera);
        if(atomic_load(&s->cancel))break;
        int n=cym_qr_decode_gray(s->decoder,s->gray,240,s->payload,CYM_QR_MAX_PAYLOAD);
        if(n>0){
            /* Quiesce DMA/sensor before logging or allowing result reading. */
            error=cym_camera_close(&s->camera);if(error)break;
            cym_qr_escape(s->payload,n,s->text,DISPLAY_CAP);
            char name[40]={0};
            int save_error=atomic_load(&s->cancel)?ECANCELED:s->save(s->payload,n,name,sizeof(name));
            if(!save_error)snprintf(s->status,sizeof(s->status),"QR Code - %d bytes\nSaved %s",n,name);
            else snprintf(s->status,sizeof(s->status),"QR Code - %d bytes\nNot saved: %s",n,strerror(save_error));
            atomic_store(&s->phase,QR_RESULT);
            error=ESP_OK;break;
        }
        /* No queued backlog; one image per bounded acquisition/decode cycle. */
        vTaskDelay(pdMS_TO_TICKS(100));
    }
finish:
    if(s->camera){esp_err_t e=cym_camera_close(&s->camera);if(e)error=e;}
    if(s->decoder){cym_qr_destroy(s->decoder);s->decoder=NULL;}
    if(error){snprintf(s->status,sizeof(s->status),"Camera unavailable (%s). Retry or Back.",esp_err_to_name(error));atomic_store(&s->phase,QR_ERROR);}
    /* Final access to context. The task self-deletes, never forcibly deleted
     * by the UI. Retained camera on failed quiescence blocks subsequent starts. */
    memset(s->payload,0,CYM_QR_MAX_PAYLOAD);
    if(atomic_load(&s->cancel))memset(s->text,0,DISPLAY_CAP);
    atomic_store(&s->done,true);
    vTaskDelete(NULL);
}
static void dispose(qr_session_t *s)
{
    if(!s)return;
    if(s->camera)return; /* failed quiescence: retain ownership, never free */
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
    if(phase==QR_SCANNING){
        lv_label_set_text(status_label,"Point camera at QR code\nKeep code inside the frame");
        if(xSemaphoreTake(s->preview_lock,0)==pdTRUE){
            if(s->fresh){memcpy(s->display,s->latest,PREVIEW_W*PREVIEW_H*2);s->fresh=false;lv_obj_invalidate(preview);}
            xSemaphoreGive(s->preview_lock);
        }
    }else if((phase==QR_RESULT||phase==QR_ERROR)&&atomic_load(&s->done)){
        lv_label_set_text(status_label,s->status);
        lv_obj_add_flag(preview,LV_OBJ_FLAG_HIDDEN);
        if(phase==QR_RESULT){lv_label_set_text_static(result_label,s->text);lv_obj_clear_flag(result_label,LV_OBJ_FLAG_HIDDEN);}
        lv_obj_clear_flag(retry_button,LV_OBJ_FLAG_HIDDEN);
    }
}
void qr_decoder_ui_stop(void)
{
    if(poll_timer){lv_timer_del(poll_timer);poll_timer=NULL;}
    if(result_label)lv_label_set_text_static(result_label,"");
    if(preview)lv_img_set_src(preview,NULL);
    if(session)lv_img_cache_invalidate_src(&session->image);
    status_label=result_label=preview=retry_button=NULL;
    qr_session_t *s=session;if(!s)return;
    atomic_store(&s->cancel,true);
    /* Worker has no LVGL dependency. Never wait for an LVGL callback/lock.
     * Slow init/storage timeout retains context; the next open may reap it. */
    for(unsigned i=0;i<300&&!atomic_load(&s->done);i++)vTaskDelay(pdMS_TO_TICKS(10));
    if(atomic_load(&s->done)&&!s->camera){session=NULL;dispose(s);}
}
static void start(void)
{
    qr_session_t *s=session;
    atomic_store(&s->phase,QR_STARTING);atomic_store(&s->done,false);atomic_store(&s->cancel,false);
    s->text[0]=0;memset(s->payload,0,CYM_QR_MAX_PAYLOAD);
    lv_label_set_text_static(result_label,"");lv_obj_add_flag(result_label,LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(preview,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(retry_button,LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(status_label,"Starting camera...");
    /* quirc decode has sizeable automatic RS workspace: dedicated internal stack,
     * all image/decoder/context bulk allocations are explicit PSRAM. */
    if(xTaskCreate(worker,"qr_scan",24576,s,2,NULL)!=pdPASS){
        strcpy(s->status,"Not enough worker memory. Retry or Back.");atomic_store(&s->phase,QR_ERROR);atomic_store(&s->done,true);
    }
}
static void retry(lv_event_t *event)
{
    (void)event;
    if(!session||!atomic_load(&session->done))return;
    if(session->camera){lv_label_set_text(status_label,"Camera stop incomplete. Restart blocked; reboot required.");return;}
    start();
}
void qr_decoder_ui_open(lv_obj_t *page,void *bus,qr_ui_save_fn save)
{
    if(session&&atomic_load(&session->done)&&!session->camera){dispose(session);session=NULL;}
    if(session){lv_obj_t *label=lv_label_create(page);lv_label_set_text(label,"Previous camera is stopping. Back and retry later.");return;}
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
    s->bus=bus;s->save=save;session=s;
    lv_obj_t *body=lv_obj_create(page);
    lv_obj_set_width(body,lv_pct(100));lv_obj_set_height(body,lv_disp_get_ver_res(NULL)-40);
    lv_obj_align(body,LV_ALIGN_BOTTOM_MID,0,0);lv_obj_set_flex_flow(body,LV_FLEX_FLOW_COLUMN);
    lv_obj_set_scroll_dir(body,LV_DIR_VER);lv_obj_set_scrollbar_mode(body,LV_SCROLLBAR_MODE_AUTO);
    status_label=lv_label_create(body);lv_obj_set_width(status_label,lv_pct(100));lv_label_set_long_mode(status_label,LV_LABEL_LONG_WRAP);
    lv_label_set_recolor(status_label,false);
    s->image.header.cf=LV_IMG_CF_TRUE_COLOR;s->image.header.w=PREVIEW_W;s->image.header.h=PREVIEW_H;
    s->image.data_size=PREVIEW_W*PREVIEW_H*2;s->image.data=(const uint8_t *)s->display;
    preview=lv_img_create(body);lv_img_set_src(preview,&s->image);
    lv_obj_set_style_border_width(preview,2,0);lv_obj_set_style_border_color(preview,lv_color_hex(0x00ff80),0);
    result_label=lv_label_create(body);lv_obj_set_width(result_label,lv_pct(100));lv_label_set_long_mode(result_label,LV_LABEL_LONG_WRAP);
    lv_label_set_recolor(result_label,false);
    retry_button=lv_btn_create(body);lv_obj_add_event_cb(retry_button,retry,LV_EVENT_CLICKED,NULL);
    lv_obj_t *caption=lv_label_create(retry_button);lv_label_set_text(caption,"Scan Again / Retry");
    poll_timer=lv_timer_create(poll,100,NULL);
    if(!poll_timer){strcpy(s->status,"UI timer unavailable. Back to exit.");lv_label_set_text(status_label,s->status);atomic_store(&s->done,true);return;}
    start();
}
