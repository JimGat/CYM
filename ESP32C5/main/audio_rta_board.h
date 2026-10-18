#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"
typedef struct audio_rta_board audio_rta_board_t;
size_t audio_rta_board_bytes(void);
esp_err_t audio_rta_board_open(audio_rta_board_t *b,void *shared_bus,int gain);
esp_err_t audio_rta_board_read(audio_rta_board_t *b,int16_t *pcm,size_t capacity,size_t *count);
esp_err_t audio_rta_board_gain(audio_rta_board_t *b,int gain);
/* Failure retains handles for detached owner retry, never frees live DMA. */
esp_err_t audio_rta_board_close(audio_rta_board_t *b);
