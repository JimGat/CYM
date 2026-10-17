#pragma once
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
/* Main/LVGL is the sole queue creator/consumer/retirer. Log producers take a
 * short reference across formatting and send, never hold a spinlock over I/O.
 * Keep payload INTERNAL: no new cache-disabled/ISR PSRAM assumption. */
static portMUX_TYPE cym_log_mux=portMUX_INITIALIZER_UNLOCKED;
static unsigned cym_log_readers;
static inline void cym_log_enter(void)
{ portENTER_CRITICAL(&cym_log_mux);++cym_log_readers;portEXIT_CRITICAL(&cym_log_mux); }
static inline void cym_log_leave(void)
{ portENTER_CRITICAL(&cym_log_mux);--cym_log_readers;portEXIT_CRITICAL(&cym_log_mux); }
static inline bool cym_log_retire(QueueHandle_t *queue,bool enabled)
{
    QueueHandle_t retired=NULL;
    portENTER_CRITICAL(&cym_log_mux);
    bool quiescent=!enabled && cym_log_readers==0;
    if (quiescent) { retired=*queue;*queue=NULL; }
    portEXIT_CRITICAL(&cym_log_mux);
    if(retired)vQueueDelete(retired);
    return quiescent;
}
