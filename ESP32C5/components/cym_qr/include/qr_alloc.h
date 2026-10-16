#pragma once
#include <stdlib.h>
#ifdef ESP_PLATFORM
#include "esp_heap_caps.h"
static inline void *qr_malloc(size_t n) { return heap_caps_malloc(n, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); }
static inline void *qr_calloc(size_t n, size_t s) { return heap_caps_calloc(n, s, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); }
#define malloc qr_malloc
#define calloc qr_calloc
/* heap_caps allocations may be released through free. No realloc in pinned quirc. */
#endif
