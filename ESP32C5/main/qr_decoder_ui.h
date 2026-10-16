#pragma once
#include "lvgl.h"
#include "esp_err.h"
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
typedef int (*qr_ui_save_fn)(const uint8_t *,size_t,char *,size_t);
/* Called again under the SD mutex, before the first filesystem operation. */
typedef bool (*qr_ui_capture_valid_fn)(void *);
typedef int (*qr_ui_frame_save_fn)(const uint8_t *,int,int,size_t,const char *,char *,size_t,qr_ui_capture_valid_fn,void *);
typedef struct {
    unsigned rotation; /* immutable per session; reopen after orientation change */
    lv_color_t panel,card,pressed,border,text,muted,accent;
    const lv_font_t *font;
    qr_ui_frame_save_fn save_frame;
} qr_ui_options_t;
/* Called only in LVGL context after page creation/stop-hook registration. */
void qr_decoder_ui_open(lv_obj_t *page,void *borrowed_bus,qr_ui_save_fn save,const qr_ui_options_t *options);
void qr_decoder_ui_stop(void);
