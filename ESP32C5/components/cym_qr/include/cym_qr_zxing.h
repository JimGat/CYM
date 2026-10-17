#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Reusable grayscale QR decoder. Input stays immutable until return; output
 * is caller-owned raw bytes, not NUL terminated. No ownership transfer.
 * Caller serializes each handle including destroy; global operations are
 * non-reentrant and return BUSY. No in-flight cancellation or hard time bound:
 * cancel BETWEEN calls, never free running work. Process tables persist until
 * process exit. All C++ exceptions are translated at this C boundary. */
typedef struct cym_zx cym_zx_t;
typedef enum { CYM_ZX_OK=0, CYM_ZX_NOT_FOUND=1, CYM_ZX_ARGUMENT=-1,
 CYM_ZX_OUTPUT_SMALL=-2, CYM_ZX_NO_MEMORY=-3, CYM_ZX_EXCEPTION=-4, CYM_ZX_BUSY=-5 } cym_zx_status_t;
typedef struct {
 uint32_t abi_version; /* exactly 1 */
 int max_width,max_height; /* 1..1024 */
 uint32_t try_harder,try_rotate,try_invert,try_downscale; /* exactly 0/1 */
} cym_zx_config_t;
typedef struct { cym_zx_status_t status; size_t length; uint32_t valid,candidates; } cym_zx_result_t;
/* Copies config, initializes tables/runtime before camera pressure. *out=NULL
 * on failure; partial initialized process tables may be retained after OOM. */
cym_zx_status_t cym_zx_create(const cym_zx_config_t *config,cym_zx_t **out);
/* NULL is a no-op; success invalidates handle. Never destroy in-flight work. */
cym_zx_status_t cym_zx_destroy(cym_zx_t *decoder);
/* bytes covers (height-1)*stride+width, stride<=INT_MAX. result reset/required.
 * Output unchanged on failure, never truncated; OUTPUT_SMALL gives required
 * length. Other failures length=0. Empty QR is OK/valid/length=0.
 * Nearest valid QR to center wins. candidates counts returned symbols, not
 * quirc finder candidates. No fallback, interpretation or hardware coupling. */
cym_zx_status_t cym_zx_decode(cym_zx_t *,const uint8_t *,size_t bytes,
 int width,int height,size_t stride,uint8_t *output,size_t capacity,cym_zx_result_t *result);
const char *cym_zx_identity(void);
#ifdef __cplusplus
}
#endif
