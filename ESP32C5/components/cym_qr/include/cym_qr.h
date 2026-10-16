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

#define CYM_QR_ERROR_COUNT 8
typedef struct {
    uint32_t candidates,normal_attempts,mirror_attempts,valid,payload_length;
    uint32_t errors[CYM_QR_ERROR_COUNT]; /* includes success at index 0 */
} cym_qr_stats_t;
/* valid distinguishes successful empty payload from no candidate/failed decode.
 * stats describes this call only. No private payload bytes in diagnostics. */
int cym_qr_decode_gray_ex(cym_qr_t *,const uint8_t *,size_t,uint8_t *,size_t,cym_qr_stats_t *);
const char *cym_qr_error_name(unsigned error);
