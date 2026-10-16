#pragma once
#include "cym_camera.h"
esp_err_t camera_backend_open(void **out,void *borrowed_bus);
esp_err_t camera_backend_acquire(void *ctx,cym_camera_frame_t *frame,unsigned timeout_ms);
void camera_backend_release(void *ctx);
esp_err_t camera_backend_close(void *ctx);
