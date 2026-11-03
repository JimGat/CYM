// Narrow HAT control/replay owner. Included once in canonical main.c.
#include "hat_tx.h"
static TaskHandle_t s_hat_worker;
static bool s_hat_retry;
static void hat_cancel_producers(void);
static esp_err_t hat_rf433_diag_stop_checked(void);
static portMUX_TYPE s_hat_job_mux=portMUX_INITIALIZER_UNLOCKED;
typedef struct { hat_tx_ticket_t ticket; void *signal; uint32_t epoch; int result; bool done; } hat_job_t;
static hat_job_t *s_hat_job;
static uint32_t s_hat_ui_epoch=1;
static lv_obj_t *s_hat_job_status, *s_hat_control_label,*s_hat_page_title;
static void (*s_hat_job_completed)(bool);
static lv_timer_t *s_hat_ui_timer;
static lv_obj_t *s_hat_watch[HAT_TX_COUNT];
static void hat_watch(hat_tx_id_t id,lv_obj_t *label){s_hat_watch[id]=label;}
static void hat_ui_poll(lv_timer_t *timer);
static void screenshot_btn_event_cb(lv_event_t *event);

static void hat_stop_owners(void)
{
    bool retry=__atomic_exchange_n(&s_hat_retry,false,__ATOMIC_ACQ_REL);
    for (int id=0;id<HAT_TX_COUNT;id++) {
        hat_tx_ticket_t t;
        if (hat_tx_snapshot().state[id]==HAT_TX_ERROR && !retry) continue;
        if (!hat_tx_claim_stop((hat_tx_id_t)id,&t)) continue;
        esp_err_t e=ESP_FAIL;
        switch(id) {
            case HAT_TX_CC1101:e=cc1101_tx_stop_checked();break;
            case HAT_TX_NRF24:e=nrf24_tx_stop_checked();break;
            case HAT_TX_IR:e=ir_hat_tx_stop_checked();break;
            case HAT_TX_RF433:e=rf433_hat_tx_stop_checked();if(e==ESP_OK)e=hat_rf433_diag_stop_checked();break;
        }
        hat_tx_finish(t,e==ESP_OK);
    }
}
static void hat_worker(void *arg)
{
    (void)arg;
    for (;;) {
        ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
        portENTER_CRITICAL(&s_hat_job_mux);hat_job_t *j=s_hat_job;if(j && j->done)j=NULL;portEXIT_CRITICAL(&s_hat_job_mux);
        if (j && !j->done) {
            bool ok=false,stopped=true;
            if (j->ticket.id==HAT_TX_IR) {
                ok=ir_hat_replay_owned(j->signal,j->ticket)==IR_HAT_OK;
                stopped=ir_hat_tx_stop_checked()==ESP_OK;
            } else {
                ok=rf433_hat_replay_owned(j->signal,3,j->ticket)==RF433_HAT_OK;
                stopped=rf433_hat_tx_stop_checked()==ESP_OK;
            }
            hat_tx_leave(j->ticket);hat_tx_finish(j->ticket,stopped);
            // The input is a COPY. RMT payload is separately retained by the driver.
            free(j->signal);j->signal=NULL;j->result=ok&&stopped?0:-1;
            __atomic_store_n(&j->done,true,__ATOMIC_RELEASE);
        }
        hat_stop_owners();
    }
}
static bool hat_runtime_ready(void)
{
    if (!s_hat_worker) {
        // ESP-IDF task depths are bytes; xTaskCreate's stack and TCB are internal.
        // Refuse before touching hardware if an internal stack cannot be reserved.
        if (heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)<16384 ||
            heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)<6144) return false;
        if (xTaskCreate(hat_worker,"hat_tx",4096,NULL,2,&s_hat_worker)!=pdPASS) return false;
    }
    if (!s_hat_ui_timer) s_hat_ui_timer=lv_timer_create(hat_ui_poll,50,NULL);
    return s_hat_ui_timer!=NULL;
}
static void hat_wake(void) {if(s_hat_worker)xTaskNotifyGive(s_hat_worker);}
static void hat_cancel_all(void)
{
    for(int i=0;i<HAT_TX_COUNT;i++)hat_tx_cancel((hat_tx_id_t)i);
    hat_cancel_producers();hat_wake();
}
static void hat_ui_depart(void)
{
    for(int i=0;i<HAT_TX_COUNT;i++)s_hat_watch[i]=NULL;
    s_hat_ui_epoch++;s_hat_job_status=NULL;s_hat_job_completed=NULL;s_hat_control_label=NULL;s_hat_page_title=NULL;
    hat_cancel_all();
}
static bool hat_submit(hat_tx_id_t id,const void *sig,size_t bytes,lv_obj_t *status,void (*done)(bool))
{
    if (!hat_runtime_ready()) {if(status)lv_label_set_text(status,"HAT TX: no internal memory");return false;}
    if (s_hat_job) {if(status)lv_label_set_text(status,"HAT TX busy; retry");return false;}
    hat_job_t *j=heap_caps_calloc(1,sizeof(*j),MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    if(!j)return false;
    j->signal=malloc(bytes);
    if(!j->signal){free(j);return false;}
    memcpy(j->signal,sig,bytes);
    if(!hat_tx_begin(id,&j->ticket)){free(j->signal);free(j);if(status)lv_label_set_text(status,"HAT TX blocked/busy");return false;}
    if(!hat_tx_enter(j->ticket)){hat_tx_finish(j->ticket,true);free(j->signal);free(j);return false;}
    j->epoch=s_hat_ui_epoch;s_hat_job_status=status;s_hat_job_completed=done;
    portENTER_CRITICAL(&s_hat_job_mux);s_hat_job=j;portEXIT_CRITICAL(&s_hat_job_mux);
    if(status)lv_label_set_text(status,"Transmitting...");hat_wake();return true;
}
static void hat_ui_poll(lv_timer_t *timer)
{
    (void)timer;
    hat_job_t *j=s_hat_job;
    if(j && __atomic_load_n(&j->done,__ATOMIC_ACQUIRE)) {
        if(j->epoch==s_hat_ui_epoch) {
            if(s_hat_job_status)lv_label_set_text(s_hat_job_status,j->result==0?"Sent":"HAT TX failed/cancelled; check state");
            if(s_hat_job_completed)s_hat_job_completed(j->result==0);
        }
        s_hat_job_status=NULL;s_hat_job_completed=NULL;
        portENTER_CRITICAL(&s_hat_job_mux);s_hat_job=NULL;portEXIT_CRITICAL(&s_hat_job_mux);free(j);
    }
    hat_tx_snapshot_t s=hat_tx_snapshot();bool pending=false,error=false,active=false;
    for(int i=0;i<HAT_TX_COUNT;i++) {pending|=s.state[i]==HAT_TX_QUIESCING;error|=s.state[i]==HAT_TX_ERROR;active|=s.state[i]==HAT_TX_ACTIVE;}
    for(int i=0;i<HAT_TX_COUNT;i++)if(s_hat_watch[i])lv_label_set_text(s_hat_watch[i],s.state[i]==HAT_TX_ERROR?"HAT TX ERROR: resources retained":s.state[i]==HAT_TX_QUIESCING?"HAT TX stopping...":s.state[i]==HAT_TX_ACTIVE?"HAT TX active":s.inhibit?"HAT TX stopped (inhibited)":"Stopped; explicit start allowed");
    if(s_hat_control_label)lv_label_set_text(s_hat_control_label,error?"HAT TX\nERROR":pending?"HAT TX\nSTOPPING":s.inhibit?"HAT TX\nSTOPPED":active?"HAT TX\nACTIVE":"HAT TX\nALLOWED");
}
static void hat_control_clicked(lv_event_t *event)
{
    (void)event;
    if(!hat_runtime_ready())return;
    hat_tx_snapshot_t s=hat_tx_snapshot();bool held=false;
    for(int i=0;i<HAT_TX_COUNT;i++)held|=s.state[i]==HAT_TX_QUIESCING || s.state[i]==HAT_TX_ERROR;
    // Held/error click retries checked stop; never clears retained ownership.
    if(held)__atomic_store_n(&s_hat_retry,true,__ATOMIC_RELEASE);
    else {hat_tx_inhibit(!s.inhibit);if(!s.inhibit)hat_cancel_producers();}
    hat_wake();hat_ui_poll(NULL);
}
static void hat_control_deleted(lv_event_t *e)
{
    if(lv_event_get_target(e)==s_hat_control_label)s_hat_control_label=NULL;
}
static void hat_control_attach(lv_obj_t *title)
{
    if(s_hat_control_label==title)return;
    s_hat_control_label=title;
    lv_obj_add_flag(title,LV_OBJ_FLAG_CLICKABLE);
    // Dynamic remote titles may already carry the ordinary screenshot callback.
    lv_obj_remove_event_cb(title,screenshot_btn_event_cb);
    lv_obj_add_event_cb(title,hat_control_clicked,LV_EVENT_SHORT_CLICKED,NULL);
    lv_obj_add_event_cb(title,screenshot_btn_event_cb,LV_EVENT_LONG_PRESSED,NULL);
    lv_obj_add_event_cb(title,hat_control_deleted,LV_EVENT_DELETE,NULL);
    lv_obj_set_style_text_font(title,&lv_font_montserrat_12,0);
    lv_obj_set_style_text_letter_space(title,-1,0);
    hat_ui_poll(NULL);
}
