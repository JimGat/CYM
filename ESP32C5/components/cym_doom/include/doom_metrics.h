#pragma once
#include <stdint.h>
#include <stdbool.h>
/* Small lock-free 32-bit monotonic aggregates; no sample/name/location data.
 * Per-field snapshots may straddle a tick: diagnostics, not exact benchmarks.
 * Main prints differences once per 5s; maxima are since launch. */
enum { DM_IO_VALIDATION,DM_IO_INIT,DM_IO_RUNNING,DM_IO_CLEANUP,DM_IO_PHASES };
enum { DM_IO_OPEN,DM_IO_CLOSE,DM_IO_READ,DM_IO_SEEK,DM_IO_TELL,DM_IO_STAT };
typedef struct {
 uint32_t opens,closes,reads,seeks,tells,stats,bytes,failures;
 uint32_t admission_us,admission_max_us,hold_us,hold_max_us;
} doom_io_metrics_t;
typedef struct {
 doom_io_metrics_t io[DM_IO_PHASES];
 uint32_t io_phase;
 uint32_t ticks,tick_us,sleep_us,sd_reads,sd_us,frame_us,panel_flushes,panel_us;
 uint32_t audio_writes,audio_us,audio_waits,audio_faults;
 uint32_t audio_samples,audio_nonzero,audio_starved,audio_overruns,sfx_starts,sfx_rejected;
 uint32_t input_ms,input_events,input_age_sum,input_age_max;
} doom_metrics_t;
extern doom_metrics_t doom_metrics;
#define DM_ADD(field,n) __atomic_fetch_add(&doom_metrics.field,(uint32_t)(n),__ATOMIC_RELAXED)
#define DM_GET(field) __atomic_load_n(&doom_metrics.field,__ATOMIC_RELAXED)
static inline void dm_input_max(uint32_t age){uint32_t old=DM_GET(input_age_max);while(age>old&&!__atomic_compare_exchange_n(&doom_metrics.input_age_max,&old,age,0,__ATOMIC_RELAXED,__ATOMIC_RELAXED)){} }

#define DM_IO_GET(p,field) __atomic_load_n(&doom_metrics.io[p].field,__ATOMIC_RELAXED)
static inline void dm_io_max(uint32_t *p,uint32_t n){uint32_t old=__atomic_load_n(p,__ATOMIC_RELAXED);while(n>old&&!__atomic_compare_exchange_n(p,&old,n,0,__ATOMIC_RELAXED,__ATOMIC_RELAXED)){} }
static inline void dm_io_record(unsigned phase,unsigned op,uint32_t wait,uint32_t hold,uint32_t bytes,bool failed){
 doom_io_metrics_t *d=&doom_metrics.io[phase];
 uint32_t *count=op==DM_IO_OPEN?&d->opens:op==DM_IO_CLOSE?&d->closes:op==DM_IO_READ?&d->reads:op==DM_IO_SEEK?&d->seeks:op==DM_IO_TELL?&d->tells:&d->stats;
 __atomic_fetch_add(count,1,__ATOMIC_RELAXED);
 __atomic_fetch_add(&d->bytes,bytes,__ATOMIC_RELAXED);__atomic_fetch_add(&d->failures,failed?1:0,__ATOMIC_RELAXED);
 __atomic_fetch_add(&d->admission_us,wait,__ATOMIC_RELAXED);__atomic_fetch_add(&d->hold_us,hold,__ATOMIC_RELAXED);
 dm_io_max(&d->admission_max_us,wait);dm_io_max(&d->hold_max_us,hold);
}
