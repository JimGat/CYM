/* Classic no-PSRAM application log transport. Other boards retain the legacy
 * sink below. No console/ROM/bootloader/panic routing is changed. */
#include "sdkconfig.h"
#include "classic_usb_debug.h"
#if CONFIG_BOARD_CYD2USB && !CONFIG_BOARD_HACKERBOX_CYD && !CONFIG_BOARD_HAS_PSRAM && !CONFIG_SPIRAM
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#define RECORD_BYTES 1024u
#define QUEUE_BYTES 3072u
/* Allocated only while ON. A complete newline-delimited record is admitted
 * atomically; incomplete/oversize/busy records never leak into the wire queue.
 * Formatting and assembly are separate so multipart IDF vprintf calls work. */
typedef struct {
    char queue[QUEUE_BYTES], record[RECORD_BYTES], format[RECORD_BYTES];
    size_t head, queued, length;
    bool discarding;
    TaskHandle_t record_owner;
} log_buffer_t;
static log_buffer_t *buffer;
static StaticSemaphore_t mutex_storage;
static SemaphoreHandle_t mutex;
static esp_timer_handle_t timer;
static bool enabled, own_uart, hook_installed;
static unsigned poisoned;
static vprintf_like_t previous_sink;
static cym_classic_usb_uart_stats_t counts;
#define COUNT(field) ((void)__atomic_add_fetch(&counts.field, 1, __ATOMIC_RELAXED))
void cym_classic_usb_uart_stats(cym_classic_usb_uart_stats_t *out)
{
    if (!out) return;
    out->accepted_records = __atomic_load_n(&counts.accepted_records, __ATOMIC_RELAXED);
    out->dropped_records = __atomic_load_n(&counts.dropped_records, __ATOMIC_RELAXED);
    out->busy_calls = __atomic_load_n(&counts.busy_calls, __ATOMIC_RELAXED);
    out->retry_writes = __atomic_load_n(&counts.retry_writes, __ATOMIC_RELAXED);
}
/* Existing esp_timer service, not a dedicated task/stack. One nonblocking FIFO
 * attempt per 5ms; zero/error/partial writes retain the exact unsent tail. */
static void drain(void *arg)
{
    (void)arg;
    if (!mutex || xSemaphoreTake(mutex, 0) != pdTRUE) return;
    if (__atomic_load_n(&enabled, __ATOMIC_ACQUIRE) && buffer && buffer->queued) {
        size_t n = QUEUE_BYTES - buffer->head;
        if (n > buffer->queued) n = buffer->queued;
        int sent = uart_tx_chars(UART_NUM_0, buffer->queue + buffer->head, n);
        if (sent > 0 && (size_t)sent <= n) {
            buffer->head = (buffer->head + sent) % QUEUE_BYTES;
            buffer->queued -= sent;
        }
        if (sent < (int)n) COUNT(retry_writes);
    }
    xSemaphoreGive(mutex);
}
static void finish_record(void)
{
    log_buffer_t *b = buffer;
    if (!b->discarding) {
        if (b->length && b->record[b->length - 1] == '\r') b->length--;
        if (b->length + 2 <= QUEUE_BYTES - b->queued) {
            b->record[b->length++] = '\r'; b->record[b->length++] = '\n';
            size_t tail = (b->head + b->queued) % QUEUE_BYTES;
            for (size_t i = 0; i < b->length; ++i) {
                b->queue[tail] = b->record[i]; tail = (tail + 1) % QUEUE_BYTES;
            }
            b->queued += b->length;
            COUNT(accepted_records);
        } else COUNT(dropped_records);
    }
    b->length = 0; b->discarding = false;
}
static int classic_log_vprintf(const char *format, va_list args)
{
    if (!__atomic_load_n(&enabled, __ATOMIC_ACQUIRE)) return 0;
    if (!mutex || xSemaphoreTake(mutex, 0) != pdTRUE) {
        /* A concurrent/reentrant fragment could be part of our pending line.
         * Conservatively discard through the next observed newline, never splice. */
        __atomic_store_n(&poisoned, 1, __ATOMIC_RELEASE);
        COUNT(busy_calls); return 0;
    }
    int n = 0;
    if (__atomic_load_n(&enabled, __ATOMIC_ACQUIRE) && buffer) {
        log_buffer_t *b = buffer;
        TaskHandle_t owner = xTaskGetCurrentTaskHandle();
        /* IDF normally serializes prefix/body/suffix. Also defend against raw
         * callers interleaving multipart records across tasks without that lock. */
        if ((b->length || b->discarding) && b->record_owner != owner) {
            b->length = 0; b->discarding = true; COUNT(dropped_records);
        }
        b->record_owner = owner;
        if (__atomic_exchange_n(&poisoned, 0, __ATOMIC_ACQ_REL)) {
            b->length = 0; b->discarding = true; COUNT(dropped_records);
        }
        n = vsnprintf(b->format, sizeof(b->format), format, args);
        if (n < 0 || n >= (int)sizeof(b->format)) {
            b->length = 0; b->discarding = true; COUNT(dropped_records);
            n = 0; /* Cannot locate a newline beyond the formatting capacity. */
        } else {
            for (int i = 0; i < n; ++i) {
                char c = b->format[i];
                if (c == '\n') finish_record();
                else if (!b->discarding) {
                    if (b->length < RECORD_BYTES - 2) b->record[b->length++] = c;
                    else { b->length = 0; b->discarding = true; COUNT(dropped_records); }
                }
            }
        }
    }
    xSemaphoreGive(mutex);
    return n;
}
esp_err_t cym_classic_usb_uart_stop(void)
{
    __atomic_store_n(&enabled, false, __ATOMIC_RELEASE);
    if (!mutex) return ESP_OK;
    if (xSemaphoreTake(mutex, pdMS_TO_TICKS(100)) != pdTRUE) return ESP_ERR_TIMEOUT;
    if (hook_installed) { esp_log_set_vprintf(previous_sink); hook_installed = false; }
    if (timer) {
        (void)esp_timer_stop(timer);
        esp_err_t rc = esp_timer_delete(timer);
        if (rc != ESP_OK) { xSemaphoreGive(mutex); return rc; }
        timer = NULL;
    }
    /* OFF explicitly discards pending software bytes. It cannot retract bytes
     * already in the UART FIFO. Detach TX before deleting its owned driver. */
    esp_err_t rc = gpio_reset_pin(GPIO_NUM_1);
    esp_err_t input = gpio_set_direction(GPIO_NUM_1, GPIO_MODE_INPUT);
    if (rc == ESP_OK) rc = input;
    if (own_uart) {
        esp_err_t deleted = uart_driver_delete(UART_NUM_0);
        if (deleted == ESP_OK) own_uart = false;
        if (rc == ESP_OK) rc = deleted;
    }
    free(buffer); buffer = NULL;
    xSemaphoreGive(mutex);
    return rc;
}
esp_err_t cym_classic_usb_uart_start(void)
{
    if (!cym_classic_usb_gps_blocked()) return ESP_ERR_INVALID_STATE;
    if (!mutex) mutex = xSemaphoreCreateMutexStatic(&mutex_storage);
    if (!mutex) return ESP_ERR_NO_MEM;
    if (own_uart || buffer || uart_is_driver_installed(UART_NUM_0)) return ESP_ERR_INVALID_STATE;
    buffer = calloc(1, sizeof(*buffer));
    if (!buffer) return ESP_ERR_NO_MEM;
    __atomic_store_n(&poisoned, 0, __ATOMIC_RELEASE);
    esp_timer_create_args_t args = { .callback = drain, .name = "classic_usb" };
    esp_err_t rc = esp_timer_create(&args, &timer);
    if (rc == ESP_OK) rc = esp_timer_start_periodic(timer, 5000);
    if (rc == ESP_OK) rc = uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0);
    if (rc == ESP_OK) {
        own_uart = true;
        uart_config_t config = { .baud_rate=115200, .data_bits=UART_DATA_8_BITS,
            .parity=UART_PARITY_DISABLE, .stop_bits=UART_STOP_BITS_1,
            .flow_ctrl=UART_HW_FLOWCTRL_DISABLE, .source_clk=UART_SCLK_DEFAULT };
        rc = uart_param_config(UART_NUM_0, &config);
        if (rc == ESP_OK) rc = uart_set_pin(UART_NUM_0, GPIO_NUM_1, UART_PIN_NO_CHANGE,
                                           UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    }
    if (rc != ESP_OK) { (void)cym_classic_usb_uart_stop(); return rc; }
    __atomic_store_n(&enabled, true, __ATOMIC_RELEASE);
    previous_sink = esp_log_set_vprintf(classic_log_vprintf); hook_installed = true;
    ESP_LOGI("classic_usb", "Classic USB Debug ON; 115200 8N1; GPS unavailable; logs only\n");
    return ESP_OK;
}
#elif CONFIG_BOARD_CYD2USB
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <stdio.h>
#include <stdarg.h>
static StaticSemaphore_t sink_mutex_storage;
static SemaphoreHandle_t sink_mutex;
static bool own_uart, sink_enabled, hook_installed;
static vprintf_like_t previous_sink;
/* No heap per log, no wait for FIFO space. Concurrent/reentrant/burst output is
 * dropped rather than stalling UI/radio tasks. Each call emits at most 127 bytes.
 * This is task-context application logging, NOT panic/ROM/early-boot capture. */
static int classic_log_vprintf(const char *format, va_list args)
{
    if (!sink_mutex || xSemaphoreTake(sink_mutex, 0) != pdTRUE) return 0;
    int written = 0;
    if (__atomic_load_n(&sink_enabled, __ATOMIC_ACQUIRE)) {
        char line[128];
        int n = vsnprintf(line, sizeof(line), format, args);
        if (n > 0) {
            if (n >= (int)sizeof(line)) n = sizeof(line) - 1;
            written = uart_tx_chars(UART_NUM_0, line, n);
            if (written < 0) written = 0;
        }
    }
    xSemaphoreGive(sink_mutex);
    return written;
}
esp_err_t cym_classic_usb_uart_stop(void)
{
    /* Disarm new output even if an in-flight callback prevents bounded teardown.
     * Pin release still requires successful serialization; UI must not reboot on failure. */
    __atomic_store_n(&sink_enabled, false, __ATOMIC_RELEASE);
    /* Serialize with callbacks already in flight. Never reboot after timeout. */
    if (!sink_mutex) return ESP_OK;
    if (xSemaphoreTake(sink_mutex, pdMS_TO_TICKS(100)) != pdTRUE) return ESP_ERR_TIMEOUT;
    if (hook_installed) { esp_log_set_vprintf(previous_sink); hook_installed = false; }
    /* Detach TX BEFORE driver removal; NO_CHANGE is not pin disconnection. */
    esp_err_t rc = gpio_reset_pin(GPIO_NUM_1);
    esp_err_t input_rc = gpio_set_direction(GPIO_NUM_1, GPIO_MODE_INPUT);
    if (rc == ESP_OK) rc = input_rc;
    if (own_uart) {
        esp_err_t deleted = uart_driver_delete(UART_NUM_0);
        if (deleted == ESP_OK) own_uart = false;
        if (rc == ESP_OK) rc = deleted;
    }
    xSemaphoreGive(sink_mutex);
    return rc;
}
esp_err_t cym_classic_usb_uart_start(void)
{
    if (!cym_classic_usb_gps_blocked()) return ESP_ERR_INVALID_STATE;
    if (!sink_mutex) sink_mutex = xSemaphoreCreateMutexStatic(&sink_mutex_storage);
    if (!sink_mutex) return ESP_ERR_NO_MEM;
    if (uart_is_driver_installed(UART_NUM_0)) return ESP_ERR_INVALID_STATE;
    uart_config_t config = { .baud_rate=115200, .data_bits=UART_DATA_8_BITS,
        .parity=UART_PARITY_DISABLE, .stop_bits=UART_STOP_BITS_1,
        .flow_ctrl=UART_HW_FLOWCTRL_DISABLE, .source_clk=UART_SCLK_DEFAULT };
    /* Driver install does not select pins. Attach GPIO1 only after all fallible
     * allocations/configuration and GPS quiescence have succeeded. RX unused. */
    esp_err_t rc = uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0);
    if (rc != ESP_OK) return rc;
    own_uart = true;
    rc = uart_param_config(UART_NUM_0, &config);
    if (rc == ESP_OK) rc = uart_set_pin(UART_NUM_0, GPIO_NUM_1, UART_PIN_NO_CHANGE,
                                       UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (rc != ESP_OK) { (void)cym_classic_usb_uart_stop(); return rc; }
    __atomic_store_n(&sink_enabled, true, __ATOMIC_RELEASE);
    previous_sink = esp_log_set_vprintf(classic_log_vprintf);
    hook_installed = true;
    ESP_LOGI("classic_usb", "Classic USB Debug ON; 115200 8N1; GPS unavailable; logs only");
    return ESP_OK;
}

void cym_classic_usb_uart_stats(cym_classic_usb_uart_stats_t *out)
{ if (out) *out = (cym_classic_usb_uart_stats_t){0}; }
#else
esp_err_t cym_classic_usb_uart_start(void) { return ESP_ERR_NOT_SUPPORTED; }
esp_err_t cym_classic_usb_uart_stop(void) { return ESP_ERR_NOT_SUPPORTED; }
void cym_classic_usb_uart_stats(cym_classic_usb_uart_stats_t *out)
{ if (out) *out = (cym_classic_usb_uart_stats_t){0}; }
#endif
