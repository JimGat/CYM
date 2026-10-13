#pragma once
#include <stdint.h>
#include <stddef.h>
#define DIAG_RATE 22050u
#define DIAG_SAMPLES 33075u
#define DIAG_BLOCK 256u
#define DIAG_HOLD_ON_SECONDS 15u
#define DIAG_HOLD_OFF_SECONDS 5u
enum diag_op { DIAG_OFF, DIAG_DIRECTION, DIAG_SAMPLE, DIAG_ON, DIAG_INIT, DIAG_TONE, DIAG_CLEANUP, DIAG_HOLD_OFF, DIAG_HOLD_ON };
int64_t diag_window_remaining_us(int64_t start, int64_t now, int64_t duration);
void diag_pcm(int16_t *out, size_t count, unsigned offset);
int diag_run(int (*step)(void *, enum diag_op), void *ctx);
