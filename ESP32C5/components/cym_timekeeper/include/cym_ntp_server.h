// CYM NTP Server — bounded UDP/123 responder.
// Reads immutable timekeeper snapshots for response generation.
// No LVGL dependency. Does not own GPS, RTC, mDNS, or Wi-Fi lifecycle.
#pragma once

#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    bool running;
    uint32_t valid_requests;
    uint32_t malformed_requests;
    uint32_t rate_limited_requests;
    uint32_t send_failures;
} cym_ntp_server_stats_t;

// Start the NTP server task (binds UDP/123). Idempotent — returns ESP_OK
// if already running. Returns bind/task errors on failure.
esp_err_t cym_ntp_server_start(void);

// Stop the NTP server. Closes the socket, waits bounded for task exit.
// Safe to call when already stopped.
void cym_ntp_server_stop(void);

// Get a snapshot of server counters.
void cym_ntp_server_get_stats(cym_ntp_server_stats_t *out);
