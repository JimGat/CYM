#pragma once
#include <stddef.h>
#include <stdint.h>
/* ASCII-only display; non-printable/non-ASCII bytes become \xHH. Returns required
 * length excluding NUL. Truncation is explicit to caller; no payload is executed. */
size_t cym_qr_escape(const uint8_t *data, size_t len, char *out, size_t cap);
/* Caller owns mounted-card lifetime/storage lock. root MUST already be mounted.
 * Returns 0 only after all writes and close succeed; otherwise an errno value.
 * Creates lab and lab/QR independently; never overwrites files. utc_unix < 2020
 * means invalid clock. Filename output is empty on failure. No diagnostic output. */
int cym_qr_record(const char *root, const uint8_t *data, size_t len,
                  const char *version, int64_t utc_unix, uint64_t uptime_ms,
                  char *filename, size_t cap);

/* Explicit consent only. Exact native decoder gray pixels, row padding omitted.
 * metadata is a bounded single-line non-secret numeric diagnostic string.
 * Caller serializes mounted SD; no automatic capture or upload. */
int cym_qr_debug_frame(const char *root,const uint8_t *gray,int width,int height,
                       size_t stride,const char *metadata,char *filename,size_t cap);
