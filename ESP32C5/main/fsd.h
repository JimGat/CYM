/* Remote USB UI driver, based on co-developer @birolt29's patch #15.
 * Normal Development console builds include FSD; console-none has no state/cost. */
#ifndef CYM_FSD_H
#define CYM_FSD_H
#include "sdkconfig.h"
#if !CONFIG_ESP_CONSOLE_NONE
#include <stdbool.h>
#include <stddef.h>
enum { FSD_NAV, FSD_BACK, FSD_WHERE, FSD_TREE, FSD_SHOT, FSD_TAP,
       FSD_TAPID, FSD_TAPT, FSD_MOVE, FSD_SIZE, FSD_TEXT, FSD_ROTATE, FSD_SWIPE };
typedef struct cym_fsd_request {
    unsigned refs, done, cancelled;
    int op, id, a, b, status;
    char text[96], desc[256];
    char *data;
    size_t length;
    unsigned w, h;
} cym_fsd_request_t;
cym_fsd_request_t *cym_fsd_submit(int op,int id,int a,int b,const char *text);
void cym_fsd_release(cym_fsd_request_t *r);
/* UI-owner only. Read hardware first; blocked covers the existing input locks.
 * Inactive path is constant-time. A real finger cancels, never merges a gesture. */
bool cym_fsd_touch_inject(void *data, bool blocked, bool physical);
void cym_fsd_input_epoch(void); /* page reconstruction / rotation, no tree walk */
void cym_fsd_poll(void); /* main task, holding lvgl_mutex, outside LVGL callbacks */
void cym_fsd_register(void);
void cym_fsd_unregister(void);
#else
#define cym_fsd_poll() ((void)0)
#define cym_fsd_register() ((void)0)
#define cym_fsd_unregister() ((void)0)
#define cym_fsd_touch_inject(d,b,p) (false)
#define cym_fsd_input_epoch() ((void)0)
#endif
#endif
