#ifndef CYM_UI_DIAGNOSTICS_H
#define CYM_UI_DIAGNOSTICS_H
#include <stdint.h>
#include <string.h>
enum {CYM_UI_RENDER, CYM_UI_ROTATE, CYM_UI_SETTINGS, CYM_UI_HARDWARE,
      CYM_UI_SETTINGS_EVENT, CYM_UI_HARDWARE_EVENT, CYM_UI_LAYOUT, CYM_UI_REFRESH, CYM_UI_SCREEN_POPUP, CYM_UI_KINDS};
typedef struct {uint32_t count,us,max_us;} cym_ui_span;
/* Counts and pixel areas are work units, NEVER microseconds/CPU utilization. */
enum {CYM_UI_INVALIDATE, CYM_UI_SAVED_AREA, CYM_UI_DIRTY_AREA,
      CYM_UI_RENDER_BAND, CYM_UI_COVER_VISIT, CYM_UI_DRAW_VISIT, CYM_UI_WORK_KINDS};
typedef struct {uint32_t count,units,max_units;} cym_ui_work;
typedef struct {cym_ui_span window[CYM_UI_KINDS],total[CYM_UI_KINDS];
 cym_ui_work work_window[CYM_UI_WORK_KINDS],work_total[CYM_UI_WORK_KINDS];} cym_ui_diag;
static inline void cym_ui_diag_work_add(cym_ui_diag *d,unsigned kind,uint32_t units){
 if(kind>=CYM_UI_WORK_KINDS)return;
 cym_ui_work *a=&d->work_window[kind],*b=&d->work_total[kind];
 a->count++;a->units+=units;if(units>a->max_units)a->max_units=units;
 b->count++;b->units+=units;if(units>b->max_units)b->max_units=units;
}
static inline uint32_t cym_ui_diag_elapsed(uint32_t start,uint32_t end){return end-start;}
static inline void cym_ui_diag_add(cym_ui_diag *d,unsigned kind,uint32_t elapsed){
 if(kind>=CYM_UI_KINDS)return;
 cym_ui_span *a=&d->window[kind],*b=&d->total[kind];
 a->count++;a->us+=elapsed;if(elapsed>a->max_us)a->max_us=elapsed;
 b->count++;b->us+=elapsed;if(elapsed>b->max_us)b->max_us=elapsed;
}
static inline void cym_ui_diag_reset_window(cym_ui_diag *d){memset(d->window,0,sizeof(d->window));memset(d->work_window,0,sizeof(d->work_window));}
/* Installed LVGL build-tree hooks; no log/I2C/allocation at a measured boundary. */
uint32_t cym_ui_diag_clock(void);
void cym_ui_diag_record(unsigned kind,uint32_t start);
void cym_ui_diag_work_record(unsigned kind,uint32_t units);
#endif
