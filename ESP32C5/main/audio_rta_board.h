#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"
typedef struct audio_rta_board audio_rta_board_t;
size_t audio_rta_board_bytes(void);
esp_err_t audio_rta_board_open(audio_rta_board_t *b,void *shared_bus,int gain);
/* A DMA queue discontinuity is independent of the SDK return code. Never
 * reinterpret a disabled/busy channel as recoverable PCM loss. On discontinuity
 * the caller discards the batch and requires new contiguous analysis windows. */
esp_err_t audio_rta_board_read(audio_rta_board_t *b,int16_t *pcm,size_t capacity,size_t *count,bool *discontinuity);
esp_err_t audio_rta_board_gain(audio_rta_board_t *b,int gain);
/* Failure retains handles for detached owner retry, never frees live DMA. */
esp_err_t audio_rta_board_close(audio_rta_board_t *b);
