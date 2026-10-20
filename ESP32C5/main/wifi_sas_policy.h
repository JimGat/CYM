#pragma once
#include "sdkconfig.h"
#include <stdbool.h>
#include <stdint.h>
/* Completed passes only. Errors, cancellation and the existing 45s ceiling
 * can still end early. C5 normally completes two; a growing second pass earns
 * one more. Classic/S3 retain two stable passes and the original eight cap. */
static inline bool cym_wifi_sas_continue(int completed, int stable, uint32_t elapsed_ms)
{
    if (elapsed_ms >= 45000u) return false;
#if CONFIG_IDF_TARGET_ESP32C5
    return completed < 2 || (completed < 3 && stable == 0);
#else
    return stable < 2 && completed < 8;
#endif
}
