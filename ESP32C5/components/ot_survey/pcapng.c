/*
 * pcapng.c — Minimal streaming PCAPNG writer
 * No ESP-IDF dependencies; uses only stdio / stdlib / string.
 */

#include "pcapng.h"
#include <stdlib.h>
#include <string.h>

/* ── PCAPNG block helpers ─────────────────────────────────────────────────── */

/* Round len up to the next multiple of 4. */
static inline uint32_t pad4(uint32_t len)
{
    return (len + 3u) & ~3u;
}

static void write_shb(FILE *f)
{
    const uint32_t block_type   = 0x0A0D0D0Au;
    const uint32_t block_len    = 28u;
    const uint32_t byte_order   = 0x1A2B3C4Du;
    const uint16_t major        = 1u;
    const uint16_t minor        = 0u;
    const int64_t  section_len  = -1;   /* -1 = unknown */

    fwrite(&block_type,  4, 1, f);
    fwrite(&block_len,   4, 1, f);
    fwrite(&byte_order,  4, 1, f);
    fwrite(&major,       2, 1, f);
    fwrite(&minor,       2, 1, f);
    fwrite(&section_len, 8, 1, f);
    fwrite(&block_len,   4, 1, f);   /* trailing block length */
}

static void write_idb(FILE *f, uint16_t link_type)
{
    const uint32_t block_type  = 0x00000001u;
    const uint32_t block_len   = 20u;
    const uint16_t reserved    = 0u;
    const uint32_t snap_len    = 65535u;

    fwrite(&block_type, 4, 1, f);
    fwrite(&block_len,  4, 1, f);
    fwrite(&link_type,  2, 1, f);
    fwrite(&reserved,   2, 1, f);
    fwrite(&snap_len,   4, 1, f);
    fwrite(&block_len,  4, 1, f);   /* trailing block length */
}

/* ── Public API ───────────────────────────────────────────────────────────── */

pcapng_writer_t *pcapng_open(const char *path, uint16_t link_type)
{
    FILE *f = fopen(path, "wb");
    if (!f) return NULL;

    write_shb(f);
    write_idb(f, link_type);

    if (ferror(f)) {
        fclose(f);
        return NULL;
    }

    pcapng_writer_t *w = malloc(sizeof(pcapng_writer_t));
    if (!w) { fclose(f); return NULL; }

    w->f      = f;
    w->n_pkts = 0;
    return w;
}

void pcapng_write_frame(pcapng_writer_t *w, const void *data,
                        uint32_t len, uint64_t ts_us)
{
    if (!w || !w->f || !data || len == 0) return;

    const uint32_t block_type = 0x00000006u;
    const uint32_t iface_id   = 0u;
    const uint32_t ts_high    = (uint32_t)(ts_us >> 32);
    const uint32_t ts_low     = (uint32_t)(ts_us & 0xFFFFFFFFu);
    const uint32_t cap_len    = len;
    const uint32_t orig_len   = len;
    const uint32_t padded     = pad4(len);

    /* EPB total = 4 (type) + 4 (len) + 4 (iface) + 8 (ts) + 4 + 4 (cap/orig) +
     *             padded(data) + 4 (options+opts_len=0) + 4 (trailing len) = 32 + padded */
    const uint32_t block_len  = 32u + padded;

    fwrite(&block_type, 4, 1, w->f);
    fwrite(&block_len,  4, 1, w->f);
    fwrite(&iface_id,   4, 1, w->f);
    fwrite(&ts_high,    4, 1, w->f);
    fwrite(&ts_low,     4, 1, w->f);
    fwrite(&cap_len,    4, 1, w->f);
    fwrite(&orig_len,   4, 1, w->f);
    fwrite(data,        1, len, w->f);

    /* Pad to 4-byte boundary */
    if (padded > len) {
        const uint32_t pad = 0u;
        fwrite(&pad, 1, padded - len, w->f);
    }

    fwrite(&block_len, 4, 1, w->f);  /* trailing block length */
    w->n_pkts++;
}

void pcapng_fflush(pcapng_writer_t *w)
{
    if (w && w->f) fflush(w->f);
}

void pcapng_close(pcapng_writer_t *w)
{
    if (!w) return;
    if (w->f) {
        fflush(w->f);
        fclose(w->f);
        w->f = NULL;
    }
    free(w);
}
