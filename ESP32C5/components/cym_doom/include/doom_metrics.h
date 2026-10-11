#pragma once
#include <stdint.h>
/* Small lock-free 32-bit monotonic aggregates; no sample/name/location data.
 * Per-field snapshots may straddle a tick: diagnostics, not exact benchmarks.
 * Main prints differences once per 5s; maxima are since launch. */
typedef struct {
 uint32_t ticks,tick_us,sleep_us,sd_reads,sd_us,frame_us,panel_flushes,panel_us;
 uint32_t audio_writes,audio_us,audio_waits,audio_faults;
 uint32_t input_ms,input_events,input_age_sum,input_age_max;
} doom_metrics_t;
extern doom_metrics_t doom_metrics;
#define DM_ADD(field,n) __atomic_fetch_add(&doom_metrics.field,(uint32_t)(n),__ATOMIC_RELAXED)
#define DM_GET(field) __atomic_load_n(&doom_metrics.field,__ATOMIC_RELAXED)
static inline void dm_input_max(uint32_t age){uint32_t old=DM_GET(input_age_max);while(age>old&&!__atomic_compare_exchange_n(&doom_metrics.input_age_max,&old,age,0,__ATOMIC_RELAXED,__ATOMIC_RELAXED)){} }
