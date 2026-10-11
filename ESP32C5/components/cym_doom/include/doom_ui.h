#ifndef CYM_DOOM_UI_H
#define CYM_DOOM_UI_H
#include "lvgl.h"
#include <stdbool.h>
void doom_ui_configure(bool (*)(void),void (*)(void),bool (*)(void),void (*)(void));
void doom_ui_tile_click(void);
void doom_ui_screen_stop(void);
bool doom_ui_active(void);
void doom_ui_request_exit(void);
#endif
