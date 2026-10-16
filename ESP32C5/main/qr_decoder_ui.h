#pragma once
#include "lvgl.h"
#include "esp_err.h"
#include <stddef.h>
#include <stdint.h>
typedef int (*qr_ui_save_fn)(const uint8_t *,size_t,char *,size_t);
/* Called only in LVGL context after page creation/stop-hook registration. */
void qr_decoder_ui_open(lv_obj_t *page,void *borrowed_bus,qr_ui_save_fn save);
void qr_decoder_ui_stop(void);
