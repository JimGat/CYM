#pragma once
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Scoped requested bytes only; exclude stdlib/exception/TLS internals.
 * foreign_frees counts compatible pointers allocated outside scoped hooks.
 * Entry tracking assumes serialized adapter calls, never a global override. */
typedef struct {size_t live,peak,calls,failures,foreign_frees;} cym_zx_alloc_stats_t;
cym_zx_alloc_stats_t cym_zx_alloc_stats(void);
#ifndef ESP_PLATFORM
void cym_zx_test_fail_after(long allocations,int unexpected_exception);
#endif
#ifdef __cplusplus
}
#endif
