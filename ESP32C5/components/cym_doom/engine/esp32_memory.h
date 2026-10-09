#pragma once

#ifdef ARDUINO
#include <esp_heap_caps.h>

#define DOOM_ALLOC(type, count) \
    ((type*)heap_caps_malloc(sizeof(type) * (count), MALLOC_CAP_SPIRAM))

#else

#define DOOM_ALLOC(type, count) \
    ((type*)malloc(sizeof(type) * (count)))

#endif