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

// Request stop and join for up to three seconds. Timeout retains ownership.
// Safe to retry; no live resource owner is forcibly deleted.
void cym_ntp_server_stop(void);

// Cooperative join; timeout_ms=0 polls without blocking the UI.
// ESP_ERR_TIMEOUT retains fd/task/stack; start is rejected until reaped.
esp_err_t cym_ntp_server_stop_wait(uint32_t timeout_ms);

// Get a snapshot of server counters.
void cym_ntp_server_get_stats(cym_ntp_server_stats_t *out);
