#ifndef CYM_UI_DIAGNOSTICS_H
#define CYM_UI_DIAGNOSTICS_H
#include <stdint.h>
#include <string.h>
enum {CYM_UI_RENDER, CYM_UI_ROTATE, CYM_UI_SETTINGS, CYM_UI_HARDWARE,
      CYM_UI_SETTINGS_EVENT, CYM_UI_HARDWARE_EVENT, CYM_UI_KINDS};
typedef struct {uint32_t count,us,max_us;} cym_ui_span;
typedef struct {cym_ui_span window[CYM_UI_KINDS],total[CYM_UI_KINDS];} cym_ui_diag;
static inline uint32_t cym_ui_diag_elapsed(uint32_t start,uint32_t end){return end-start;}
static inline void cym_ui_diag_add(cym_ui_diag *d,unsigned kind,uint32_t elapsed){
 if(kind>=CYM_UI_KINDS)return;
 cym_ui_span *a=&d->window[kind],*b=&d->total[kind];
 a->count++;a->us+=elapsed;if(elapsed>a->max_us)a->max_us=elapsed;
 b->count++;b->us+=elapsed;if(elapsed>b->max_us)b->max_us=elapsed;
}
static inline void cym_ui_diag_reset_window(cym_ui_diag *d){memset(d->window,0,sizeof(d->window));}
/* Installed LVGL build-tree hooks; no log/I2C/allocation at a measured boundary. */
uint32_t cym_ui_diag_clock(void);
void cym_ui_diag_record(unsigned kind,uint32_t start);
#endif
