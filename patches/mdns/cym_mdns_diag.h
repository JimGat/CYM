/* Build-local allocation boundaries. The application hook gates heap queries/logging. */
#pragma once
#include <stddef.h>
#include "esp_err.h"
extern void cym_mdns_alloc_boundary(const char *stage, const char *phase,
                                    size_t bytes, esp_err_t error) __attribute__((weak));
#define CYM_MDNS_BOUNDARY(stage, phase, bytes, error) do { \
    if (cym_mdns_alloc_boundary) cym_mdns_alloc_boundary(stage, phase, bytes, error); \
} while (0)
