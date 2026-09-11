/*
 * pcapng.h — Minimal streaming PCAPNG writer (no ESP-IDF dependencies)
 *
 * Writes a valid PCAPNG file (Section Header Block + Interface Description
 * Block + Enhanced Packet Blocks) suitable for opening in Wireshark.
 *
 * Thread-safety: not internally synchronised — caller must serialise writes
 * (e.g. hold sd_spi_mutex before pcapng_write_frame / pcapng_fflush).
 */

#pragma once
#include <stdint.h>
#include <stdio.h>

/* PCAPNG link-type constants (IANA DLT values) */
#define PCAPNG_LINKTYPE_IEEE802_15_4_NOFCS  230u   /* 802.15.4 MAC, no FCS */
#define PCAPNG_LINKTYPE_BLUETOOTH_LE_LL     251u   /* BLE LL PDU */

typedef struct {
    FILE    *f;         /* open FILE* for writing */
    uint32_t n_pkts;    /* packets written so far */
} pcapng_writer_t;

/*
 * pcapng_open — create file at path, write SHB + IDB.
 * Returns NULL on failure.
 */
pcapng_writer_t *pcapng_open(const char *path, uint16_t link_type);

/*
 * pcapng_write_frame — append one Enhanced Packet Block.
 * data / len: raw packet bytes (link-type framing, no PCAPNG wrapper).
 * ts_us: capture timestamp in microseconds (epoch or monotonic).
 */
void pcapng_write_frame(pcapng_writer_t *w, const void *data,
                        uint32_t len, uint64_t ts_us);

/*
 * pcapng_fflush — flush stdio write buffers to the FAT layer.
 * Call periodically so data is not lost on power loss.
 */
void pcapng_fflush(pcapng_writer_t *w);

/*
 * pcapng_close — flush and close the file, free the writer struct.
 */
void pcapng_close(pcapng_writer_t *w);
