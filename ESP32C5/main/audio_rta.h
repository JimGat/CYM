#pragma once
#include "audio_rta_dsp.h"
#include "esp_err.h"
typedef enum {RTA_CLOSED,RTA_STARTING,RTA_RUNNING,RTA_FROZEN,RTA_STOPPING,RTA_ERROR} audio_rta_state_t;
typedef struct {
 audio_rta_spectrum_t spectrum;
 uint32_t generation,sequence,overruns;
 int64_t timestamp_us;
 audio_rta_state_t state;
 int gain_db,error;
 size_t internal_delta,psram_bytes;
} audio_rta_snapshot_t;
esp_err_t audio_rta_start(void *shared_bus,uint32_t *generation);
bool audio_rta_snapshot(uint32_t generation,audio_rta_snapshot_t *copy);
void audio_rta_controls(uint32_t generation,bool freeze,bool slow,int gain,bool reset);
void audio_rta_stop(uint32_t generation);
/* Owned session/device buffers are released. FreeRTOS may reclaim its dynamic
 * worker stack/TCB on the next idle pass; this is not a kernel-task join. */
bool audio_rta_closed(void);
