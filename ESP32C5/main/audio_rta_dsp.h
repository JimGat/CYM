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
 uint32_t frames; /* completed full OR low analyses since history reset */
} audio_rta_spectrum_t;
size_t audio_rta_dsp_bytes(void);
/* Prepare immutable tables once; optional checkpoints can block/cancel.
 * False means cancelled: this workspace must not be used until prepared. */
bool audio_rta_dsp_prepare(void *memory,bool (*checkpoint)(void *),void *arg);
void audio_rta_dsp_init(void *memory);
/* Reset stream history only; preserve prepared windows/twiddles. */
void audio_rta_dsp_reset(void *memory);
/* A false checkpoint cancels in bounded chunks/stages. Discard/reset the
 * partial workspace before reuse; no snapshot may be published on false. */
bool audio_rta_dsp_push_checked(void *memory,const int16_t *pcm,size_t count,bool (*checkpoint)(void *),void *arg);
void audio_rta_dsp_push(void *memory,const int16_t *pcm,size_t count);
void audio_rta_dsp_snapshot(void *memory,audio_rta_spectrum_t *out);
void audio_rta_dsp_slow(void *memory,bool slow);
void audio_rta_dsp_reset_peaks(void *memory);
double audio_rta_dsp_edge(unsigned edge);
double audio_rta_dsp_filter(double frequency);

/* Runtime single-owner path. Ingest never starts an FFT. Between bounded work
 * calls the owner drains input and handles controls/stop. Do not mix this path
 * with synchronous push on the same history. No partial analysis is published.
 * Status is telemetry only; phases 0..6: idle/copy/window/reverse/FFT/power/commit. */
bool audio_rta_dsp_ingest(void *memory,const int16_t *pcm,size_t count,bool (*checkpoint)(void *),void *arg);
bool audio_rta_dsp_work(void *memory);
void audio_rta_dsp_work_status(void *memory,unsigned *phase,uint32_t *slices,uint32_t *restarts);
