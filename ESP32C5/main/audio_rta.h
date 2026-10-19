#pragma once
#include "audio_rta_dsp.h"
#include "esp_err.h"
typedef enum {RTA_CLOSED,RTA_STARTING,RTA_RUNNING,RTA_FROZEN,RTA_STOPPING,RTA_ERROR} audio_rta_state_t;
typedef enum {RTA_STORE_OK,RTA_STORE_OPEN,RTA_STORE_READ,RTA_STORE_INVALID,RTA_STORE_SET,RTA_STORE_COMMIT} audio_rta_store_stage_t;
typedef struct {
 audio_rta_spectrum_t spectrum;
 uint32_t generation,sequence,overruns;
 int64_t timestamp_us;
 audio_rta_state_t state;
 int gain_db,error;
 int requested_gain_db,persisted_gain_db,gain_store_error;
 audio_rta_store_stage_t gain_store_stage;
 size_t internal_delta,psram_bytes;
 /* Lifetime session counters never reset at a continuity break. Elapsed work
  * includes read blocking, preemption and cooperative scheduling, not CPU time. */
 uint64_t input_samples,read_calls,read_us,process_us,analysis_frames;
 uint32_t history_resets,max_read_us,max_process_us,max_work_us;
 uint32_t work_slices,analysis_restarts,max_slice_us;
 unsigned work_phase;
 bool stale; /* copied RUNNING data older than 500 ms; Frozen is intentional */
} audio_rta_snapshot_t;
esp_err_t audio_rta_start(void *shared_bus,uint32_t *generation);
bool audio_rta_snapshot(uint32_t generation,audio_rta_snapshot_t *copy);
void audio_rta_controls(uint32_t generation,bool freeze,bool slow,int gain,bool reset);
void audio_rta_stop(uint32_t generation);
/* Owned session/device buffers are released. FreeRTOS may reclaim its dynamic
 * worker stack/TCB on the next idle pass; this is not a kernel-task join. */
bool audio_rta_closed(void);
