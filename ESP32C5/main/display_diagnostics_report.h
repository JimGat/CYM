#ifndef CYM_DISPLAY_DIAGNOSTICS_REPORT_H
#define CYM_DISPLAY_DIAGNOSTICS_REPORT_H
#include "display_diagnostics.h"
/* Task-only reporting after LVGL/shared bus release. Monotonic millisecond
 * interval uses 64-bit task-local clock, not the wrapping ISR microsecond word. */
static void cym_display_diag_report(void)
{
    static uint64_t last_ms;
    static cym_display_diag last[2];
    uint64_t now=(uint64_t)esp_timer_get_time()/1000;
    /* First window starts at boot, matching all early transport counters. */
    if(now-last_ms<5000)return;
    for(unsigned mode=0;mode<2;mode++){
        cym_display_diag *d=&s_display_diag[mode];
        if(d->callbacks==last[mode].callbacks && d->handlers==last[mode].handlers)continue;
        ESP_LOGI("display", "DISPLAY_DIAG mode=%s interval_ms=%llu callbacks=%lu accepted=%lu rejected=%lu planned=%lu accepted_draws=%lu draw_errors=%lu completed=%lu sem_completions=%lu admit_attempts=%lu admit_rejects=%lu admission_us=%lu copy_us=%lu draw_us=%lu wait_us=%lu draw_to_isr_us=%lu resume_us=%lu early=%lu uncorrelated=%lu callback_us=%lu handlers=%lu handler_us=%lu residual_us=%lu admission_max_us=%lu copy_max_us=%lu draw_max_us=%lu wait_max_us=%lu draw_to_isr_max_us=%lu resume_max_us=%lu callback_max_us=%lu handler_max_us=%lu g0=%lux%lu/%luB/%lu g1=%lux%lu/%luB/%lu g2=%lux%lu/%luB/%lu g3=%lux%lu/%luB/%lu isr_events_total=%lu",
            mode?"isolated":"normal",(unsigned long long)(now-last_ms),
            (unsigned long)(d->callbacks-last[mode].callbacks),
            (unsigned long)(d->accepted-last[mode].accepted),
            (unsigned long)(d->rejected-last[mode].rejected),
            (unsigned long)(d->planned-last[mode].planned),
            (unsigned long)(d->accepted_draws-last[mode].accepted_draws),
            (unsigned long)(d->draw_errors-last[mode].draw_errors),
            (unsigned long)(d->completed-last[mode].completed),
            (unsigned long)(d->sem_completions-last[mode].sem_completions),
            (unsigned long)(d->admit_attempts-last[mode].admit_attempts),
            (unsigned long)(d->admit_rejects-last[mode].admit_rejects),
            (unsigned long)(d->admission_us-last[mode].admission_us),
            (unsigned long)(d->copy_us-last[mode].copy_us),
            (unsigned long)(d->draw_us-last[mode].draw_us),
            (unsigned long)(d->wait_us-last[mode].wait_us),
            (unsigned long)(d->draw_to_isr_us-last[mode].draw_to_isr_us),
            (unsigned long)(d->resume_us-last[mode].resume_us),
            (unsigned long)(d->early-last[mode].early),
            (unsigned long)(d->uncorrelated-last[mode].uncorrelated),
            (unsigned long)(d->callback_us-last[mode].callback_us),
            (unsigned long)(d->handlers-last[mode].handlers),
            (unsigned long)(d->handler_us-last[mode].handler_us),
            (unsigned long)(d->residual_us-last[mode].residual_us),
            (unsigned long)d->admission_max_us, (unsigned long)d->copy_max_us, (unsigned long)d->draw_max_us, (unsigned long)d->wait_max_us, (unsigned long)d->draw_to_isr_max_us, (unsigned long)d->resume_max_us, (unsigned long)d->callback_max_us, (unsigned long)d->handler_max_us,
            (unsigned long)d->geometry[0].width, (unsigned long)d->geometry[0].height, (unsigned long)d->geometry[0].bytes, (unsigned long)d->geometry[0].stripes, (unsigned long)d->geometry[1].width, (unsigned long)d->geometry[1].height, (unsigned long)d->geometry[1].bytes, (unsigned long)d->geometry[1].stripes, (unsigned long)d->geometry[2].width, (unsigned long)d->geometry[2].height, (unsigned long)d->geometry[2].bytes, (unsigned long)d->geometry[2].stripes, (unsigned long)d->geometry[3].width, (unsigned long)d->geometry[3].height, (unsigned long)d->geometry[3].bytes, (unsigned long)d->geometry[3].stripes, (unsigned long)__atomic_load_n(&s_display_channel.events,__ATOMIC_RELAXED));
        last[mode]=*d;
    }
    last_ms=now;
}
#endif
