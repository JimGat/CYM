/* Mixer/WAD stay on engine; finite copied PCM sink is synchronously joined. */
#ifndef DOOM_AUDIO_H
#define DOOM_AUDIO_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
void *cym_game_audio_bus(void);
bool cym_game_audio_amp(bool);
#define DOOM_AUDIO_BLOCK 256u
bool doom_audio_begin(void);
unsigned doom_audio_demand(void);
bool doom_audio_healthy(void);
bool doom_audio_write(const int16_t *,size_t);
int doom_audio_end(void);
#endif
