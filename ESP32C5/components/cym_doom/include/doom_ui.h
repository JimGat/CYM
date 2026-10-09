#ifndef CYM_DOOM_UI_H
#define CYM_DOOM_UI_H
#include "lvgl.h"
#include <stdbool.h>
void doom_ui_attach_footer(lv_obj_t *,bool (*)(void),void (*)(void));
void doom_ui_screen_stop(void);
bool doom_ui_active(void);
void doom_ui_request_exit(void);
#endif
