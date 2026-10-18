#include "debug_settings.h"
#include "nvs.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <stdio.h>
#include "debug_console_stdio.h"
#include <string.h>
/* Single word publishes state and transition generation together. Setters
 * serialize flash writes; readers are bounded aligned atomic loads only. */
static uint32_t debug_state;
static SemaphoreHandle_t debug_lock;
bool cym_debug_enabled(void){return (__atomic_load_n(&debug_state,__ATOMIC_ACQUIRE)&1u)!=0;}
uint32_t cym_debug_generation(void){return __atomic_load_n(&debug_state,__ATOMIC_ACQUIRE);}
static void publish(bool enabled){uint32_t old=__atomic_load_n(&debug_state,__ATOMIC_RELAXED);__atomic_store_n(&debug_state,((old+2u)&~1u)|(enabled?1u:0u),__ATOMIC_RELEASE);}
esp_err_t cym_debug_load(void)
{
    /* Startup only, before console/optional diagnostics, no one-shot key edits. */
    publish(false);
    if(!debug_lock)debug_lock=xSemaphoreCreateMutex();
    if(!debug_lock){ESP_LOGE("debug","DEBUG_LOAD mutex allocation failed; OFF");return ESP_ERR_NO_MEM;}
    nvs_handle_t h;esp_err_t rc=nvs_open("settings",NVS_READONLY,&h);
    if(rc==ESP_ERR_NVS_NOT_FOUND)return ESP_OK;
    if(rc!=ESP_OK){ESP_LOGE("debug","DEBUG_LOAD open failed: %s; OFF",esp_err_to_name(rc));return rc;}
    uint8_t value=0;rc=nvs_get_u8(h,"debug_diag",&value);nvs_close(h);
    if(rc==ESP_ERR_NVS_NOT_FOUND)return ESP_OK;
    if(rc!=ESP_OK){ESP_LOGE("debug","DEBUG_LOAD read failed: %s; OFF",esp_err_to_name(rc));return rc;}
    if(value>1){ESP_LOGW("debug","DEBUG_LOAD invalid bool; OFF");return ESP_ERR_INVALID_ARG;}
    publish(value==1);return ESP_OK;
}
esp_err_t cym_debug_set(bool enabled)
{
    if(!debug_lock)return ESP_ERR_INVALID_STATE;
    if(xSemaphoreTake(debug_lock,pdMS_TO_TICKS(250))!=pdTRUE)return ESP_ERR_TIMEOUT;
    nvs_handle_t h;esp_err_t rc=nvs_open("settings",NVS_READWRITE,&h);
    if(rc==ESP_OK){rc=nvs_set_u8(h,"debug_diag",enabled?1:0);if(rc==ESP_OK)rc=nvs_commit(h);nvs_close(h);}
    /* Never claim or publish success on an open/write/commit failure. */
    if(rc==ESP_OK)publish(enabled);
    else ESP_LOGE("debug","DEBUG_SAVE failed: %s; runtime unchanged",esp_err_to_name(rc));
    xSemaphoreGive(debug_lock);return rc;
}
int cym_debug_command(int argc,char **argv)
{
    if(argc==1 || (argc==2 && (!strcmp(argv[1],"status") || !strcmp(argv[1],"query")))){
        fprintf(cym_console_output(),"Debug %s\n",cym_debug_enabled()?"ON":"OFF");return 0;
    }
    if(argc!=2 || (strcmp(argv[1],"on") && strcmp(argv[1],"off"))){fprintf(cym_console_output(),"Usage: debug [on|off|status|query]\n");return 1;}
    esp_err_t rc=cym_debug_set(!strcmp(argv[1],"on"));
    if(rc!=ESP_OK){fprintf(cym_console_output(),"Debug persistence failed: %s; unchanged %s\n",esp_err_to_name(rc),cym_debug_enabled()?"ON":"OFF");return 1;}
    fprintf(cym_console_output(),"Debug %s persisted; applied immediately\n",cym_debug_enabled()?"ON":"OFF");return 0;
}
