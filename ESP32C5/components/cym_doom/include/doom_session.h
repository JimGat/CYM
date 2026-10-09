/* Synchronous, single-worker private engine session; NOT a UI/task join API. */
#ifndef CYM_DOOM_SESSION_H
#define CYM_DOOM_SESSION_H
#include <stddef.h>
#include <stdint.h>
typedef void (*doom_frame_fn)(const uint8_t *,void *);
void doom_session_set_frame(doom_frame_fn,void *);
int doom_session_start(const char *);
int doom_session_tick(void);
int doom_session_stop(void);
void doom_session_request_stop(void);
const char *doom_session_error(void);
size_t doom_session_owned(void);
size_t doom_session_state_bytes(void);
void doom_session_set_keys(unsigned);
uint16_t doom_session_color565(uint8_t);
#endif
