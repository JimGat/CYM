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
#include "linenoise/linenoise.h"
#if CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG_ENABLED
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
static FILE *debug_usb_in,*debug_usb_out;
static void debug_usb_worker(void *unused)
{
    (void)unused;
    /* IDF libc compatibility stdio is task-local, as in the installed REPL.
     * Other tasks' stdout/log routes and all UART pin configuration stay intact. */
    stdin=debug_usb_in;stdout=debug_usb_out;stderr=debug_usb_out;
    setvbuf(stdin,NULL,_IONBF,0);setvbuf(stdout,NULL,_IONBF,0);
    printf("Debug USB console ready: debug [on|off|status]\n");
    for(;;){
        char *line=linenoise("debug> ");
        if(!line){vTaskDelay(pdMS_TO_TICKS(20));continue;}
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
    ESP_LOGW("debug","DEBUG_CONSOLE unavailable: board console disabled; Hardware setting remains available");
    return ESP_ERR_NOT_SUPPORTED;
#elif CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG_ENABLED
    /* IDF convenience esp_console_new_repl_usb_serial_jtag is unavailable
     * when USB is secondary. Use installed linenoise + esp_console parser,
     * with explicit /dev/usbserjtag instead of changing primary Kconfig. */
    static bool started;
    if(started)return ESP_OK;
    bool own_driver=!usb_serial_jtag_is_driver_installed();
    esp_err_t rc=ESP_OK;
    if(own_driver){usb_serial_jtag_driver_config_t hw=USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();rc=usb_serial_jtag_driver_install(&hw);}
    if(rc!=ESP_OK){ESP_LOGE("debug","DEBUG_CONSOLE USB driver failed: %s",esp_err_to_name(rc));return rc;}
    debug_usb_in=fopen("/dev/usbserjtag","r");debug_usb_out=fopen("/dev/usbserjtag","w");
    if(!debug_usb_in||!debug_usb_out){rc=ESP_ERR_NO_MEM;goto io_failure;}
    esp_console_config_t cfg=ESP_CONSOLE_CONFIG_DEFAULT();cfg.max_cmdline_length=100;
    rc=esp_console_init(&cfg);
    if(rc!=ESP_OK)goto io_failure;
    const esp_console_cmd_t cmd={.command="debug",.help="Persist diagnostics: debug [on|off|status|query]",.hint=NULL,.func=cym_debug_command};
    rc=esp_console_cmd_register(&cmd);
    if(rc!=ESP_OK)goto parser_failure;
    linenoiseSetDumbMode(1);linenoiseSetMaxLineLen(100);
    usb_serial_jtag_vfs_set_rx_line_endings(ESP_LINE_ENDINGS_CR);
    usb_serial_jtag_vfs_use_driver();
    /* Only a debug parser worker: no radio, storage scans or LVGL access. */
    if(xTaskCreate(debug_usb_worker,"debug_usb",4096,NULL,1,NULL)!=pdPASS){rc=ESP_ERR_NO_MEM;usb_serial_jtag_vfs_use_nonblocking();goto parser_failure;}
    started=true;return ESP_OK;
parser_failure:
    (void)esp_console_deinit();
io_failure:
    if(debug_usb_in)fclose(debug_usb_in);
    if(debug_usb_out)fclose(debug_usb_out);
    debug_usb_in=debug_usb_out=NULL;
    if(own_driver)(void)usb_serial_jtag_driver_uninstall();
    ESP_LOGE("debug","DEBUG_CONSOLE init failed: %s",esp_err_to_name(rc));return rc;
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
    ESP_LOGI("MEM","DEBUG_MEMORY internal_free=%u internal_largest=%u psram_free=%u psram_largest=%u owner_stack_hwm=%u",
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),(unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL),
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),(unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM),
        (unsigned)uxTaskGetStackHighWaterMark(NULL));
}
