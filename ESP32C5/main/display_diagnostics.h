/* Observations only. Main owns aggregates; ISR owns a bounded single-writer
 * stamp channel. All shared fields are lock-free 32-bit internal RAM words.
 * Clocks are injected as uint32 microseconds; unsigned subtraction wraps.
 * No diagnostic event grants DMA ownership or fabricates a semaphore ack. */
#ifndef CYM_DISPLAY_DIAGNOSTICS_H
#define CYM_DISPLAY_DIAGNOSTICS_H
#include <stdint.h>
#include <stdbool.h>
#ifdef ESP_PLATFORM
#include "esp_attr.h"
#define CYM_DIAG_RAM DRAM_ATTR
#define CYM_DIAG_ISR IRAM_ATTR
#else
#define CYM_DIAG_RAM
#define CYM_DIAG_ISR
#endif
/* IDF's S32C1I/PSRAM workaround disables hardware RMW globally. GCC then
 * answers false for always_lock_free even though aligned word loads/stores
 * remain inline l32i/s32i + memw. This channel uses only those loads/stores,
 * never fetch/CAS. Native production-flags probe/disassembly verifies them. */
#if defined(ESP_PLATFORM) && defined(CONFIG_STDATOMIC_S32C1I_SPIRAM_WORKAROUND)
_Static_assert(sizeof(uint32_t)==4 && _Alignof(uint32_t)>=4,
               "diagnostic loads/stores need aligned 32-bit words");
#else
_Static_assert(__atomic_always_lock_free(4, 0), "diagnostic words must be lock-free");
#endif
typedef struct { uint32_t width,height,bytes,stripes; } cym_diag_geometry;
typedef struct {
 uint32_t callbacks,accepted,rejected,planned,accepted_draws,draw_errors,completed,sem_completions;
 uint32_t admit_attempts,admit_rejects,admission_us,admission_max_us;
 uint32_t copy_us,copy_max_us,draw_us,draw_max_us,wait_us,wait_max_us;
 uint32_t draw_to_isr_us,draw_to_isr_max_us,resume_us,resume_max_us,early,uncorrelated;
 uint32_t callback_us,callback_max_us,handler_us,handler_max_us,handlers,residual_us;
 uint32_t callback_start,geometry_used;
 cym_diag_geometry geometry[4];
} cym_display_diag;
typedef struct { uint32_t pending,next,version,token,stamp,events; } cym_diag_channel;
static CYM_DIAG_RAM cym_display_diag s_display_diag[2];
static CYM_DIAG_RAM cym_diag_channel s_display_channel;
static inline void cym_diag_time(uint32_t *sum,uint32_t *max,uint32_t n){*sum+=n;if(n>*max)*max=n;}
static inline uint32_t cym_diag_stripes(uint32_t w,uint32_t h,uint32_t cap){
 if(!w||!h||w>cap/2)return 0;uint32_t rows=cap/(w*2);return (h+rows-1)/rows;
}
static inline void cym_diag_callback_begin(cym_display_diag *d,uint32_t w,uint32_t h,uint32_t cap,uint32_t now){
 d->callbacks++;d->callback_start=now;uint32_t stripes=cym_diag_stripes(w,h,cap);d->planned+=stripes;
 for(uint32_t i=0;i<d->geometry_used;i++)if(d->geometry[i].width==w&&d->geometry[i].height==h)return;
 if(d->geometry_used<4)d->geometry[d->geometry_used++]=(cym_diag_geometry){w,h,w*h*2,stripes};
}
static inline void cym_diag_callback_end(cym_display_diag *d,bool ok,uint32_t now){
 if(ok)d->accepted++;else d->rejected++;cym_diag_time(&d->callback_us,&d->callback_max_us,now-d->callback_start);
}
static inline void cym_diag_admission(cym_display_diag *d,uint32_t tries,uint32_t rejects,uint32_t us){
 d->admit_attempts+=tries;d->admit_rejects+=rejects;cym_diag_time(&d->admission_us,&d->admission_max_us,us);
}
static inline void cym_diag_copy(cym_display_diag *d,uint32_t us){cym_diag_time(&d->copy_us,&d->copy_max_us,us);}
static inline void cym_diag_draw(cym_display_diag *d,uint32_t us,bool ok){
 if(ok)d->accepted_draws++;else d->draw_errors++;cym_diag_time(&d->draw_us,&d->draw_max_us,us);
}
static inline uint32_t cym_diag_prepare(cym_diag_channel *c){
 if(!++c->next)++c->next;__atomic_store_n(&c->pending,c->next,__ATOMIC_RELEASE);return c->next;
}
/* Executed immediately before give-from-ISR. No loops, RMW, locks or logging.
 * SC word stores provide an auditable bounded seqlock; reader may decline an
 * interrupted sample instead of spinning or pairing a new token with old time. */
static inline void CYM_DIAG_ISR cym_diag_isr(cym_diag_channel *c,uint32_t now){
 uint32_t v=__atomic_load_n(&c->version,__ATOMIC_SEQ_CST);
 __atomic_store_n(&c->version,v+1,__ATOMIC_SEQ_CST);
 __atomic_store_n(&c->stamp,now,__ATOMIC_SEQ_CST);
 __atomic_store_n(&c->token,__atomic_load_n(&c->pending,__ATOMIC_ACQUIRE),__ATOMIC_SEQ_CST);
 __atomic_store_n(&c->events,__atomic_load_n(&c->events,__ATOMIC_RELAXED)+1,__ATOMIC_RELAXED);
 __atomic_store_n(&c->version,v+2,__ATOMIC_SEQ_CST);
}
static inline bool cym_diag_sample(cym_diag_channel *c,uint32_t *token,uint32_t *stamp){
 uint32_t a=__atomic_load_n(&c->version,__ATOMIC_SEQ_CST);
 *token=__atomic_load_n(&c->token,__ATOMIC_SEQ_CST);*stamp=__atomic_load_n(&c->stamp,__ATOMIC_SEQ_CST);
 uint32_t b=__atomic_load_n(&c->version,__ATOMIC_SEQ_CST);return !(a&1)&&a==b;
}
static inline void cym_diag_resume(cym_display_diag *d,cym_diag_channel *c,uint32_t token,uint32_t start,uint32_t returned,uint32_t resumed,uint32_t wait){
 d->sem_completions++;
 uint32_t seen,stamp;cym_diag_time(&d->wait_us,&d->wait_max_us,wait);
 if(!cym_diag_sample(c,&seen,&stamp)||seen!=token){d->uncorrelated++;return;}
 d->completed++;if((int32_t)(stamp-returned)<=0)d->early++;
 cym_diag_time(&d->draw_to_isr_us,&d->draw_to_isr_max_us,stamp-start);
 cym_diag_time(&d->resume_us,&d->resume_max_us,resumed-stamp);
 __atomic_store_n(&c->pending,0,__ATOMIC_RELEASE);
}
static inline void cym_diag_handler(cym_display_diag *d,uint32_t us,uint32_t callbacks){
 d->handlers++;cym_diag_time(&d->handler_us,&d->handler_max_us,us);d->residual_us+=us>=callbacks?us-callbacks:0;
}
#endif
