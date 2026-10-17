#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "observer_memory.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/idf_additions.h"

/* The log producer is global vprintf: an already-entered producer can outlive
 * disable. Retain this bounded queue for the application's lifetime. Only its
 * payload uses external RAM; the caller's StaticQueue_t stays in internal BSS.
 * SDK xQueueCreateStatic borrows both buffers; reset never frees either one.
 * Called only by the UI owner, never from the log callback or an ISR. */
static inline esp_err_t observer_log_queue_init(QueueHandle_t *queue,
        uint8_t **storage, StaticQueue_t *control, unsigned item_bytes)
{
    if (*queue) { xQueueReset(*queue); return ESP_OK; }
    *storage = heap_caps_malloc(32u * item_bytes, observer_heap_caps() | MALLOC_CAP_8BIT);
    if (!*storage) return ESP_ERR_NO_MEM;
    *queue = xQueueCreateStatic(32, item_bytes, *storage, control);
    if (!*queue) {
        heap_caps_free(*storage); *storage = NULL;
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

/* Completed workers park themselves; a published flag/NULL handle is not proof
 * that their final instructions have left the stack. Delete ONLY after observed
 * suspension, then reclaim caller-owned static storage. Never delete live work. */
static inline bool observer_task_reap(TaskHandle_t *handle,
        StackType_t **stack, bool caps_task)
{
    if (*handle) {
        if (eTaskGetState(*handle) != eSuspended) return false;
        for (unsigned core = 0; core < configNUMBER_OF_CORES; ++core) {
            if (xTaskGetCurrentTaskHandleForCore(core) == *handle) return false;
        }
        if (caps_task) vTaskDeleteWithCaps(*handle);
        else vTaskDelete(*handle);
        *handle = NULL;
    }
    if (*stack) { heap_caps_free(*stack); *stack = NULL; }
    return true;
}

/* IDF 6.0.2 WithCaps puts the TCB in INTERNAL|8BIT and the unchanged byte-depth
 * stack in the requested memory. The matching delete is mandatory. These tasks
 * never disable flash cache; PSRAM builds enable TASK_CREATE_ALLOW_EXT_MEM. */
static inline esp_err_t observer_hopper_start(TaskHandle_t *handle,
        TaskFunction_t entry, unsigned stack_bytes)
{
    StackType_t *none = NULL;
    if (!observer_task_reap(handle, &none, true)) return ESP_ERR_INVALID_STATE;
    if (xTaskCreateWithCaps(entry, "sniffer_ch_hop", stack_bytes, NULL, 5,
            handle, observer_heap_caps() | MALLOC_CAP_8BIT) != pdPASS) {
        *handle = NULL;
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
