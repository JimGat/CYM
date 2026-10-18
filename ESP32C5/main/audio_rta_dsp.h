/* Caller-owned, host-testable uncalibrated PCM power analyzer. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#define AUDIO_RTA_BANDS 24
#define AUDIO_RTA_FLOOR (-120.0f)
typedef struct {
 float band[24], peak[24];
 uint32_t valid, age[24]; /* ages in 48 kHz input samples */
 float rms, sample_peak;
 uint32_t clips;
 uint64_t samples;
} audio_rta_spectrum_t;
size_t audio_rta_dsp_bytes(void);
void audio_rta_dsp_init(void *memory);
void audio_rta_dsp_push(void *memory,const int16_t *pcm,size_t count);
void audio_rta_dsp_snapshot(void *memory,audio_rta_spectrum_t *out);
void audio_rta_dsp_slow(void *memory,bool slow);
void audio_rta_dsp_reset_peaks(void *memory);
double audio_rta_dsp_edge(unsigned edge);
double audio_rta_dsp_filter(double frequency);
