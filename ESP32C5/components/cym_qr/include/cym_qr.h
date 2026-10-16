#pragma once
#include <stddef.h>
#include <stdint.h>
typedef struct cym_qr cym_qr_t;
#define CYM_QR_MAX_PAYLOAD 8896
cym_qr_t *cym_qr_create(int width, int height);
void cym_qr_destroy(cym_qr_t *q);
/* Single caller. Returns byte length, 0 for no valid code, -1 for bad args.
 * Tries mirrored codes and chooses the valid code nearest image center. */
int cym_qr_decode_gray(cym_qr_t *q, const uint8_t *gray, size_t stride, uint8_t *out, size_t cap);
/* RGB565 little-endian input to gray, independently of display byte swapping. */
int cym_qr_rgb565_gray(const uint8_t *rgb, size_t stride, uint8_t *gray, int width, int height);
