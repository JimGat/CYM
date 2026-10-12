#ifndef CYM_DOOM_UI_H
#define CYM_DOOM_UI_H
#include "lvgl.h"
#include <stdbool.h>
#include "doom_native.h"
void doom_ui_configure(bool (*)(void),void (*)(void),bool (*)(void),void (*)(void));
void doom_ui_configure_selector(void (*rotate)(bool),void (*back)(void),const char *(*reboot)(void));
void doom_ui_boot_start(void (*home)(void),bool sd_ready);
bool doom_ui_exclusive(void);
void doom_ui_tile_click(void);
void doom_ui_screen_stop(void);
bool doom_ui_active(void);
void doom_ui_request_exit(void);

/* Main-owner two-point logical snapshot; false leaves normal LVGL untouched. */
bool doom_ui_touch_snapshot(const int *,const int *,unsigned);

/* Debounced physical Fire, active only during isolated running gameplay. */
void doom_ui_boot_fire(bool);
/* Isolated main owner only. takeover is called AFTER handler/flush returned.
 * drained is a transport ownership proof, not a timer callback request. */
void doom_ui_native_configure(uint16_t *,size_t,doom_native_send,doom_native_poll);
bool doom_ui_native_takeover(bool drained);
bool doom_ui_native_active(void);
bool doom_ui_native_accepting(void);
void doom_ui_native_step(void);
#endif
