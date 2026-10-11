/* Pure bounded DMX SFX mixer; borrowed sample pointers belong to the engine owner. */
#ifndef DOOM_MIXER_H
#define DOOM_MIXER_H
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#define DOOM_MIX_CHANNELS 8
typedef struct {const uint8_t *data;size_t count;uint32_t rate;} doom_sample;
typedef struct {doom_sample sample;uint64_t phase;unsigned volume;} doom_mix_channel;
typedef struct {doom_mix_channel channels[DOOM_MIX_CHANNELS];} doom_mixer;
bool doom_sample_parse(doom_sample *,const uint8_t *,size_t);
bool doom_mixer_start(doom_mixer *,int,const doom_sample *,int);
void doom_mixer_stop(doom_mixer *,int);
void doom_mixer_volume(doom_mixer *,int,int);
bool doom_mixer_playing(const doom_mixer *,int);
void doom_mixer_render(doom_mixer *,int16_t *,size_t,uint32_t);
#endif
