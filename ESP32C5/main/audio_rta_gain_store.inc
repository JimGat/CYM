/* Worker-only NVS boundary: never called from an LVGL callback/critical section.
 * The private namespace/key preserves all unrelated settings. Missing/invalid
 * settings choose 24 dB; zero is a supported, persistable value, not a sentinel.
 * persisted changes only after commit. A failed operation is not auto-retried.
 */
#include "nvs.h"
static bool gain_valid(int gain){return gain>=0&&gain<=42&&gain%6==0;}
static int gain_load(int *persisted,int *error,audio_rta_store_stage_t *stage){
 nvs_handle_t h;int32_t value=24;*persisted=-1;*error=0;*stage=RTA_STORE_OK;
 int rc=nvs_open("audio_rta",NVS_READONLY,&h);
 if(rc==ESP_ERR_NVS_NOT_FOUND)return 24;
 if(rc){*error=rc;*stage=RTA_STORE_OPEN;return 24;}
 rc=nvs_get_i32(h,"gain_db",&value);nvs_close(h);
 if(rc==ESP_ERR_NVS_NOT_FOUND)return 24;
 if(rc){*error=rc;*stage=RTA_STORE_READ;return 24;}
 if(!gain_valid(value)){*error=ESP_ERR_INVALID_ARG;*stage=RTA_STORE_INVALID;return 24;}
 *persisted=value;return value;
}
static void gain_save(int gain,int *persisted,int *error,audio_rta_store_stage_t *stage){
 if(!gain_valid(gain)){*error=ESP_ERR_INVALID_ARG;*stage=RTA_STORE_INVALID;return;}
 if(gain==*persisted)return;
 nvs_handle_t h;*error=0;*stage=RTA_STORE_OK;
 int rc=nvs_open("audio_rta",NVS_READWRITE,&h);
 if(rc){*error=rc;*stage=RTA_STORE_OPEN;return;}
 rc=nvs_set_i32(h,"gain_db",gain);
 if(rc){*error=rc;*stage=RTA_STORE_SET;}
 else if((rc=nvs_commit(h))){*error=rc;*stage=RTA_STORE_COMMIT;}
 else *persisted=gain;
 nvs_close(h);
}
