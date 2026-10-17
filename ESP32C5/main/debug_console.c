/* Use the installed IDF REPL/parser path, not a second UART line parser.
 * Debug-only registration is safe in isolated mode: no radio/storage commands. */
#include "debug_settings.h"
#include "esp_console.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdio.h>
#include <errno.h>
#include "esp_attr.h"

static const char *console_status = "Not started";
const char *cym_debug_console_status(void)
{ return __atomic_load_n(&console_status, __ATOMIC_ACQUIRE); }
static void console_set_status(const char *status)
{ __atomic_store_n(&console_status, status, __ATOMIC_RELEASE); }
#include "linenoise/linenoise.h"
#if CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG_ENABLED
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
/* Reliability reservation, not RAM savings. NVS commands require internal stack. */
static DRAM_ATTR StackType_t debug_usb_stack[4096 / sizeof(StackType_t)];
static DRAM_ATTR StaticTask_t debug_usb_tcb;
static FILE *debug_usb_in,*debug_usb_out;
static bool console_start_busy;
static void console_failure(const char *stage, esp_err_t rc, int saved_errno)
{
    console_set_status(stage);
    ESP_LOGE("debug", "DEBUG_CONSOLE stage=%s rc=%s errno=%d worker_bytes=4096 worker_caps=INTERNAL|8BIT int_free=%u int_largest=%u dma_free=%u dma_largest=%u",
        stage, esp_err_to_name(rc), saved_errno,
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA|MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA|MALLOC_CAP_8BIT));
}
static void debug_usb_worker(void *unused)
{
    (void)unused;
    /* IDF libc compatibility stdio is task-local, as in the installed REPL.
     * Other tasks' stdout/log routes and all UART pin configuration stay intact. */
    stdin=debug_usb_in;stdout=debug_usb_out;stderr=debug_usb_out;
    setvbuf(stdin,NULL,_IONBF,0);setvbuf(stdout,NULL,_IONBF,0);
    console_set_status("Ready (USB)");
    printf("Debug USB console ready: debug [on|off|status]\n");
    bool input_failed=false;
    for(;;){
        errno=0;
        char *line=linenoise("debug> ");
        if(!line){
            if(!input_failed){console_failure("Input unavailable (line/stream)",ESP_FAIL,errno);input_failed=true;}
            vTaskDelay(pdMS_TO_TICKS(20));continue;
        }
        if(input_failed){console_set_status("Ready (USB)");input_failed=false;}
        int result=0;esp_err_t rc=esp_console_run(line,&result);
        if(rc==ESP_ERR_NOT_FOUND)printf("Unrecognized command\n");
        else if(rc!=ESP_OK&&rc!=ESP_ERR_INVALID_ARG)printf("Console error: %s\n",esp_err_to_name(rc));
        linenoiseFree(line);
    }
}
#endif
esp_err_t cym_debug_console_start(void)
{
#if CONFIG_ESP_CONSOLE_NONE
    console_set_status("Unavailable (board console disabled)");
    ESP_LOGW("debug","DEBUG_CONSOLE unavailable: board console disabled; Hardware setting remains available");
    return ESP_ERR_NOT_SUPPORTED;
#elif CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG_ENABLED
    /* IDF convenience esp_console_new_repl_usb_serial_jtag is unavailable
     * when USB is secondary. Use installed linenoise + esp_console parser,
     * with explicit /dev/usbserjtag instead of changing primary Kconfig. */
    static bool started;
    if(__atomic_test_and_set(&console_start_busy,__ATOMIC_ACQUIRE))return ESP_ERR_INVALID_STATE;
    if(started){__atomic_clear(&console_start_busy,__ATOMIC_RELEASE);return ESP_OK;}
    console_set_status("Starting");
    const char *stage="Driver failed";
    int saved_errno=0;
    bool own_driver=!usb_serial_jtag_is_driver_installed();
    esp_err_t rc=ESP_OK;
    if(own_driver){usb_serial_jtag_driver_config_t hw=USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();rc=usb_serial_jtag_driver_install(&hw);}
    if(rc!=ESP_OK)goto start_failure;
    stage="Input stream failed";errno=0;
    debug_usb_in=fopen("/dev/usbserjtag","r");
    if(!debug_usb_in){saved_errno=errno;rc=ESP_FAIL;goto io_failure;}
    stage="Output stream failed";errno=0;
    debug_usb_out=fopen("/dev/usbserjtag","w");
    if(!debug_usb_out){saved_errno=errno;rc=ESP_FAIL;goto io_failure;}
    stage="Parser failed";
    esp_console_config_t cfg=ESP_CONSOLE_CONFIG_DEFAULT();cfg.max_cmdline_length=100;
    rc=esp_console_init(&cfg);
    if(rc!=ESP_OK)goto io_failure;
    const esp_console_cmd_t cmd={.command="debug",.help="Persist diagnostics: debug [on|off|status|query]",.hint=NULL,.func=cym_debug_command};
    stage="Command registration failed";
    rc=esp_console_cmd_register(&cmd);
    if(rc!=ESP_OK)goto parser_failure;
    linenoiseSetDumbMode(1);linenoiseSetMaxLineLen(100);
    usb_serial_jtag_vfs_set_rx_line_endings(ESP_LINE_ENDINGS_CR);
    usb_serial_jtag_vfs_use_driver();
    /* Only a debug parser worker: no radio, storage scans or LVGL access. */
    stage="Worker creation failed";
    if(!xTaskCreateStatic(debug_usb_worker,"debug_usb",4096,NULL,1,debug_usb_stack,&debug_usb_tcb)){
        rc=ESP_ERR_NO_MEM;
        if(own_driver)usb_serial_jtag_vfs_use_nonblocking();
        goto parser_failure;
    }
    started=true;__atomic_clear(&console_start_busy,__ATOMIC_RELEASE);return ESP_OK;
parser_failure:
    (void)esp_console_deinit();
io_failure:
    if(debug_usb_in)fclose(debug_usb_in);
    if(debug_usb_out)fclose(debug_usb_out);
    debug_usb_in=debug_usb_out=NULL;
    if(own_driver)(void)usb_serial_jtag_driver_uninstall();
start_failure:
    console_failure(stage,rc,saved_errno);
    __atomic_clear(&console_start_busy,__ATOMIC_RELEASE);return rc;
#elif CONFIG_ESP_CONSOLE_UART_DEFAULT && CONFIG_ESP_CONSOLE_UART_NUM == 0
    /* USB bridge at UART0 only. Never a GPS/JST custom UART. */
    static esp_console_repl_t *repl;
    if(repl)return ESP_OK;
    esp_console_repl_config_t cfg=ESP_CONSOLE_REPL_CONFIG_DEFAULT();
    cfg.prompt="debug>";cfg.max_cmdline_length=100;cfg.task_priority=1;
    esp_console_dev_uart_config_t hw=ESP_CONSOLE_DEV_UART_CONFIG_DEFAULT();
    esp_err_t rc=esp_console_new_repl_uart(&hw,&cfg,&repl);
    if(rc!=ESP_OK){repl=NULL;return rc;}
    const esp_console_cmd_t cmd={.command="debug",.help="Persist diagnostics: debug [on|off|status|query]",.hint=NULL,.func=cym_debug_command};
    rc=esp_console_cmd_register(&cmd);
    if(rc==ESP_OK)rc=esp_console_start_repl(repl);
    if(rc!=ESP_OK){ESP_LOGE("debug","DEBUG_CONSOLE register/start failed: %s",esp_err_to_name(rc));repl->del(repl);repl=NULL;}
    return rc;
#else
    console_set_status("Unavailable (transport)");
    ESP_LOGW("debug","DEBUG_CONSOLE unavailable: unsupported non-primary console");
    return ESP_ERR_NOT_SUPPORTED;
#endif
}
void cym_debug_memory_report(void)
{
    static uint32_t generation;static uint64_t last_ms;
    uint32_t current=cym_debug_generation();
    if(current!=generation){generation=current;last_ms=(uint64_t)esp_timer_get_time()/1000;return;}
    if(!cym_debug_enabled())return;
    uint64_t now=(uint64_t)esp_timer_get_time()/1000;
    if(now-last_ms<5000)return;
    last_ms=now;
    /* Self-owned stack only: never enumerate or dereference retiring tasks. */
    ESP_LOGI("MEM","DEBUG_MEMORY internal_free=%u internal_largest=%u internal_min=%u dma_free=%u dma_largest=%u psram_free=%u psram_largest=%u owner_stack_hwm=%u",
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),(unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA|MALLOC_CAP_8BIT),(unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA|MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),(unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM),
        (unsigned)uxTaskGetStackHighWaterMark(NULL));
}
