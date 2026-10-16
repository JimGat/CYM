#pragma once
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
typedef struct cym_camera cym_camera_t;
typedef enum { CYM_CAMERA_RGB565_LE } cym_camera_format_t;
typedef struct { const uint8_t *data; unsigned width,height; size_t stride; cym_camera_format_t format; } cym_camera_frame_t;
/* Single worker owns this handle and all hardware operations. bus is borrowed,
 * never deleted. acquire <=500 ms; release before close; failed close retains
 * the entire handle so DMA/ISR resources cannot outlive their buffers. */
esp_err_t cym_camera_open(cym_camera_t **out, void *borrowed_bus);
esp_err_t cym_camera_acquire(cym_camera_t *c,cym_camera_frame_t *frame,unsigned timeout_ms);
void cym_camera_release(cym_camera_t *c);
esp_err_t cym_camera_close(cym_camera_t **c);
int cym_camera_unpack_bf3901(const uint8_t *packet,size_t len,uint8_t *rgb,size_t cap);
