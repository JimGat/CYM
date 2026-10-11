/* Audio is synchronous on the engine worker: no task borrows WAD pointers. */
#ifndef DOOM_AUDIO_H
#define DOOM_AUDIO_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
void *cym_game_audio_bus(void);
bool cym_game_audio_amp(bool);
bool doom_audio_begin(void);
bool doom_audio_write(const int16_t *,size_t);
int doom_audio_end(void);
#endif
