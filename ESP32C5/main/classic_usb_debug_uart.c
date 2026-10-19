/* Explicit runtime UART0 log sink for Classic bridge USB. CONFIG_CONSOLE_NONE
 * remains untouched; no stdio redirection, command interpreter or worker task. */
#include "sdkconfig.h"
#include "classic_usb_debug.h"
#if CONFIG_BOARD_CYD2USB
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
#else
esp_err_t cym_classic_usb_uart_start(void) { return ESP_ERR_NOT_SUPPORTED; }
esp_err_t cym_classic_usb_uart_stop(void) { return ESP_ERR_NOT_SUPPORTED; }
#endif
