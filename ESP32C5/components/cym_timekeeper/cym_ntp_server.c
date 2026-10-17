// CYM NTP Server — UDP/123 responder with rate limiting.
// Reads cym_timekeeper snapshots; produces RFC 5905-compatible responses.
// Supports NTP v3/v4 client mode validation, originate echo, quality mapping.

#include "cym_ntp_server.h"
#include "cym_timekeeper.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include <string.h>
#include <stdatomic.h>
#include "esp_heap_caps.h"
#include "freertos/idf_additions.h"

// Application debug gate; no UI/flash operations on this worker.
extern bool cym_debug_enabled(void);

static const char *TAG = "ntp_server";

// ── NTP protocol constants ──────────────────────────────────────────────────

// NTP epoch offset: seconds between 1900-01-01 and 1970-01-01
#define NTP_EPOCH_OFFSET 2208988800UL

// NTP packet is exactly 48 bytes
#define NTP_PACKET_SIZE  48

// NTP modes
#define NTP_MODE_CLIENT  3
#define NTP_MODE_SERVER  4

// Leap indicator values
#define NTP_LI_NONE      0   // no warning
#define NTP_LI_ALARM     3   // clock not synchronized (alarm)

// Stratum values
#define NTP_STRATUM_PRIMARY    1   // local primary reference (GPS/RTC)
#define NTP_STRATUM_SECONDARY  2   // disciplined from an upstream NTP pool
#define NTP_STRATUM_UNSYNC    16   // unsynchronized

// Precision: log2 of clock precision in seconds
// ESP32 system clock ~1us precision = log2(1e-6) ≈ -20
#define NTP_PRECISION    (-20)

// Reference IDs (4-byte ASCII, zero-padded)
#define REFID_GPS  0x47505300  // "GPS\0" in network byte order
#define REFID_RTC  0x52544300  // "RTC\0"
#define REFID_SNTP 0x534E5450  // "SNTP"
#define REFID_INIT 0x494E4954  // "INIT"

// NTP UDP port
#define NTP_PORT 123

// ── Rate limiting ───────────────────────────────────────────────────────────

// Global token bucket: 8 requests/second, burst 32
#define GLOBAL_RATE_TOKENS_PER_SEC  8
#define GLOBAL_RATE_BURST           32

// Per-source rate limit: 2 requests/second, burst 4
#define PER_SOURCE_RATE_PER_SEC     2
#define PER_SOURCE_BURST            4

// Per-source LRU table size
#define SOURCE_TABLE_SIZE           8

typedef struct {
    uint32_t addr;        // IPv4 address
    int32_t  tokens;      // token count (fixed-point x1000)
    int64_t  last_us;     // last refill timestamp
} source_bucket_t;

static int32_t s_global_tokens = GLOBAL_RATE_BURST * 1000;
static int64_t s_global_last_us = 0;
static source_bucket_t s_source_table[SOURCE_TABLE_SIZE];

static bool rate_check_global(int64_t now_us)
{
    if (s_global_last_us == 0) {
        s_global_last_us = now_us;
        s_global_tokens = GLOBAL_RATE_BURST * 1000;
    }
    int64_t elapsed_us = now_us - s_global_last_us;
    s_global_last_us = now_us;
    // Refill tokens
    int32_t refill = (int32_t)(elapsed_us * GLOBAL_RATE_TOKENS_PER_SEC / 1000);
    s_global_tokens += refill;
    if (s_global_tokens > GLOBAL_RATE_BURST * 1000)
        s_global_tokens = GLOBAL_RATE_BURST * 1000;
    if (s_global_tokens >= 1000) {
        s_global_tokens -= 1000;
        return true;
    }
    return false;
}

static bool rate_check_source(uint32_t addr, int64_t now_us)
{
    // Find or evict LRU entry
    int idx = -1;
    int oldest_idx = 0;
    int64_t oldest_time = INT64_MAX;
    for (int i = 0; i < SOURCE_TABLE_SIZE; i++) {
        if (s_source_table[i].addr == addr) {
            idx = i;
            break;
        }
        if (s_source_table[i].last_us < oldest_time) {
            oldest_time = s_source_table[i].last_us;
            oldest_idx = i;
        }
    }
    if (idx < 0) {
        // New source — evict oldest
        idx = oldest_idx;
        s_source_table[idx].addr = addr;
        s_source_table[idx].tokens = PER_SOURCE_BURST * 1000;
        s_source_table[idx].last_us = now_us;
    }

    source_bucket_t *b = &s_source_table[idx];
    int64_t elapsed_us = now_us - b->last_us;
    b->last_us = now_us;
    int32_t refill = (int32_t)(elapsed_us * PER_SOURCE_RATE_PER_SEC / 1000);
    b->tokens += refill;
    if (b->tokens > PER_SOURCE_BURST * 1000)
        b->tokens = PER_SOURCE_BURST * 1000;
    if (b->tokens >= 1000) {
        b->tokens -= 1000;
        return true;
    }
    return false;
}

// ── NTP timestamp helpers ───────────────────────────────────────────────────

static void timeval_to_ntp(const struct timeval *tv, uint32_t *secs, uint32_t *frac)
{
    *secs = htonl((uint32_t)(tv->tv_sec + NTP_EPOCH_OFFSET));
    // Convert microseconds to NTP fraction: frac = usec * 2^32 / 1e6
    uint64_t f = ((uint64_t)tv->tv_usec << 32) / 1000000ULL;
    *frac = htonl((uint32_t)f);
}

// Convert uncertainty_us to NTP 16.16 fixed-point root dispersion
static uint32_t uncertainty_to_dispersion(uint32_t uncertainty_us)
{
    // Root dispersion is seconds in 16.16 format
    // uncertainty_us / 1e6 = seconds; then * 65536 = 16.16
    uint32_t disp = (uint32_t)((uint64_t)uncertainty_us * 65536ULL / 1000000ULL);
    return htonl(disp);
}

// ── Server task ─────────────────────────────────────────────────────────────

// Admission protects the owner handle/fd across start and bounded join. A timed
// out join retains both; start cannot reuse a live worker's descriptor.
static atomic_bool s_running = false;
static bool s_lifecycle_busy;
static portMUX_TYPE s_lifecycle_mux = portMUX_INITIALIZER_UNLOCKED;
static bool ntp_owner_enter(void)
{
    portENTER_CRITICAL(&s_lifecycle_mux);
    bool acquired = !s_lifecycle_busy;
    if (acquired) s_lifecycle_busy = true;
    portEXIT_CRITICAL(&s_lifecycle_mux);
    return acquired;
}
static esp_err_t ntp_owner_leave(esp_err_t rc)
{
    portENTER_CRITICAL(&s_lifecycle_mux);
    s_lifecycle_busy = false;
    portEXIT_CRITICAL(&s_lifecycle_mux);
    return rc;
}

// Keep the 4096-byte application budget plus the GCC TLS area reserved by IDF.
static size_t ntp_stack_tls_bytes(void)
{
#ifdef CYM_NTP_HOST_TEST
    return 0;
#else
    extern char _thread_local_data_start, _thread_local_data_end;
    extern char _thread_local_bss_start, _thread_local_bss_end;
    size_t bytes = (uintptr_t)&_thread_local_data_end - (uintptr_t)&_thread_local_data_start
                 + (uintptr_t)&_thread_local_bss_end - (uintptr_t)&_thread_local_bss_start;
    return (bytes + 15U) & ~(size_t)15U;
#endif
}

static void ntp_boundary(const char *boundary, esp_err_t rc, unsigned caps, size_t stack)
{
    if (rc == ESP_OK && !cym_debug_enabled()) return;
    size_t free_bytes = heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    size_t largest = heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (rc != ESP_OK) {
        ESP_LOGE(TAG, "%s rc=%s (%d) stack=%s/%u internal free=%u largest=%u",
                 boundary, esp_err_to_name(rc), (int)rc,
                 (caps & MALLOC_CAP_SPIRAM) ? "psram" : "internal", (unsigned)stack,
                 (unsigned)free_bytes, (unsigned)largest);
    } else {
        ESP_LOGI(TAG, "%s rc=%s (%d) stack=%s/%u internal free=%u largest=%u",
                 boundary, esp_err_to_name(rc), (int)rc,
                 (caps & MALLOC_CAP_SPIRAM) ? "psram" : "internal", (unsigned)stack,
                 (unsigned)free_bytes, (unsigned)largest);
    }
}
static int s_sock = -1;
static TaskHandle_t s_task = NULL;
static cym_ntp_server_stats_t s_stats;
static portMUX_TYPE s_stats_mux = portMUX_INITIALIZER_UNLOCKED;
#define STATS_INC(field) do { portENTER_CRITICAL(&s_stats_mux); s_stats.field++; portEXIT_CRITICAL(&s_stats_mux); } while (0)

static void ntp_server_task(void *arg)
{
    const int sock = (int)(intptr_t)arg;  // worker owns fd until suspension
    uint8_t buf[NTP_PACKET_SIZE];
    struct sockaddr_in client_addr;
    socklen_t addr_len;

    if (cym_debug_enabled()) ESP_LOGI(TAG, "NTP server task started on UDP/123");

    while (s_running) {
        addr_len = sizeof(client_addr);
        int n = recvfrom(sock, buf, sizeof(buf), 0,
                         (struct sockaddr *)&client_addr, &addr_len);
        if (!s_running) break;
        if (n < 0) {
            if (errno == EBADF) break;
            continue;
        }

        // Capture receive timestamp immediately
        struct timeval rx_tv;
        gettimeofday(&rx_tv, NULL);
        int64_t now_us = esp_timer_get_time();

        // Validate packet size
        if (n < NTP_PACKET_SIZE) {
            STATS_INC(malformed_requests);
            continue;
        }

        // Validate version (3 or 4) and mode (client = 3)
        uint8_t li_vn_mode = buf[0];
        uint8_t version = (li_vn_mode >> 3) & 0x07;
        uint8_t mode = li_vn_mode & 0x07;
        if ((version != 3 && version != 4) || mode != NTP_MODE_CLIENT) {
            STATS_INC(malformed_requests);
            continue;
        }

        // Rate limiting
        if (!rate_check_global(now_us)) {
            STATS_INC(rate_limited_requests);
            continue;
        }
        if (!rate_check_source(client_addr.sin_addr.s_addr, now_us)) {
            STATS_INC(rate_limited_requests);
            continue;
        }

        // Get timekeeper snapshot
        cym_time_snapshot_t snap;
        bool have_snap = cym_timekeeper_snapshot(&snap);

        // Build response
        uint8_t resp[NTP_PACKET_SIZE];
        memset(resp, 0, NTP_PACKET_SIZE);

        // Determine quality fields from source state
        uint8_t li, stratum;
        uint32_t ref_id;
        uint32_t root_dispersion;

        if (have_snap && (snap.source == CYM_TIME_GPS_LOCKED ||
                          snap.source == CYM_TIME_RTC_HOLDOVER ||
                          snap.source == CYM_TIME_GPS_RTC_HOLDOVER ||
                          snap.source == CYM_TIME_NETWORK_SYNC ||
                          snap.source == CYM_TIME_NTP_HOLDOVER ||
                          snap.source == CYM_TIME_RTOS_HOLDOVER)) {
            li = NTP_LI_NONE;
            if (snap.source == CYM_TIME_NETWORK_SYNC ||
                snap.source == CYM_TIME_NTP_HOLDOVER ||
                snap.source == CYM_TIME_GPS_RTC_HOLDOVER ||
                snap.source == CYM_TIME_RTOS_HOLDOVER) {
                stratum = NTP_STRATUM_SECONDARY;
                ref_id = htonl(REFID_SNTP);
            } else {
                stratum = NTP_STRATUM_PRIMARY;
                ref_id = (snap.source == CYM_TIME_GPS_LOCKED) ?
                         htonl(REFID_GPS) : htonl(REFID_RTC);
            }
            root_dispersion = uncertainty_to_dispersion(snap.uncertainty_us);
        } else {
            li = NTP_LI_ALARM;  // LI = 3
            stratum = NTP_STRATUM_UNSYNC;  // stratum 16
            ref_id = htonl(REFID_INIT);
            root_dispersion = htonl(0x00100000);  // ~16 seconds
        }

        // Byte 0: LI (2 bits) | VN (3 bits) | Mode (3 bits)
        resp[0] = (li << 6) | (version << 3) | NTP_MODE_SERVER;  // mode 4
        resp[1] = stratum;
        resp[2] = 6;  // poll interval: 2^6 = 64 seconds
        resp[3] = (uint8_t)(int8_t)NTP_PRECISION;

        // Root delay: 0 (we are the reference)
        // resp[4..7] = 0

        // Root dispersion: bytes 8-11
        memcpy(&resp[8], &root_dispersion, 4);

        // Reference ID: bytes 12-15
        memcpy(&resp[12], &ref_id, 4);

        // Reference timestamp (last discipline event): bytes 16-23
        if (have_snap && snap.last_gps_sync_epoch > 0) {
            struct timeval ref_tv = { .tv_sec = (time_t)snap.last_gps_sync_epoch, .tv_usec = 0 };
            uint32_t ref_s, ref_f;
            timeval_to_ntp(&ref_tv, &ref_s, &ref_f);
            memcpy(&resp[16], &ref_s, 4);
            memcpy(&resp[20], &ref_f, 4);
        }

        // Originate timestamp: echo client's transmit (bytes 40-47 -> 24-31)
        memcpy(&resp[24], &buf[40], 8);

        // Receive timestamp: bytes 32-39
        uint32_t rx_s, rx_f;
        timeval_to_ntp(&rx_tv, &rx_s, &rx_f);
        memcpy(&resp[32], &rx_s, 4);
        memcpy(&resp[36], &rx_f, 4);

        // Transmit timestamp: bytes 40-47 (capture just before send)
        struct timeval tx_tv;
        gettimeofday(&tx_tv, NULL);
        uint32_t tx_s, tx_f;
        timeval_to_ntp(&tx_tv, &tx_s, &tx_f);
        memcpy(&resp[40], &tx_s, 4);
        memcpy(&resp[44], &tx_f, 4);

        int sent = sendto(sock, resp, NTP_PACKET_SIZE, 0,
                          (struct sockaddr *)&client_addr, addr_len);
        if (sent == NTP_PACKET_SIZE) {
            STATS_INC(valid_requests);
        } else {
            STATS_INC(send_failures);
        }
    }

    // Self-delete WithCaps creates a cleanup task and can abort under OOM.
    // Close our fd and park; owner must observe eSuspended before reaping.
    close(sock);
    s_running = false;
    for (;;) vTaskSuspend(NULL);
}

// ── Public API ──────────────────────────────────────────────────────────────

esp_err_t cym_ntp_server_start(void)
{
    if (!ntp_owner_enter()) return ESP_ERR_INVALID_STATE;
    if (s_task) return ntp_owner_leave(s_running ? ESP_OK : ESP_ERR_INVALID_STATE);
    const bool psram = heap_caps_get_total_size(MALLOC_CAP_SPIRAM) > 0;
    const unsigned caps = MALLOC_CAP_8BIT | (psram ? MALLOC_CAP_SPIRAM : MALLOC_CAP_INTERNAL);
    const size_t stack = 4096 + ntp_stack_tls_bytes();
#if !CONFIG_SPIRAM_ALLOW_STACK_EXTERNAL_MEMORY
    if (psram) {
        ntp_boundary("stack policy unavailable", ESP_ERR_INVALID_STATE, caps, stack);
        return ntp_owner_leave(ESP_ERR_INVALID_STATE);
    }
#endif
    ntp_boundary("before socket", ESP_OK, caps, stack);
    memset(s_source_table, 0, sizeof(s_source_table));
    s_global_tokens = GLOBAL_RATE_BURST * 1000;
    s_global_last_us = 0;
    portENTER_CRITICAL(&s_stats_mux);
    memset(&s_stats, 0, sizeof(s_stats));
    portEXIT_CRITICAL(&s_stats_mux);
    s_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    esp_err_t rc = ESP_FAIL;
    if (s_sock < 0) {
        ESP_LOGE(TAG, "socket() failed: errno %d", errno);
        goto fail;
    }
    // Timeouts allow cooperative cancellation, without fd-close/reuse races.
    int opt = 1;
    struct timeval timeout = { .tv_sec = 0, .tv_usec = 100000 };
    if (setsockopt(s_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0 ||
        setsockopt(s_sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0 ||
        setsockopt(s_sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) < 0) {
        ESP_LOGE(TAG, "socket options failed: errno %d", errno);
        goto fail;
    }
    struct sockaddr_in addr = {
        .sin_family = AF_INET, .sin_port = htons(NTP_PORT),
        .sin_addr.s_addr = htonl(INADDR_ANY),
    };
    if (bind(s_sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        ESP_LOGE(TAG, "bind() UDP/123 failed: errno %d", errno);
        goto fail;
    }
    ntp_boundary("socket bound", ESP_OK, caps, stack);
    s_running = true;
    // WithCaps keeps the TCB internal. No internal-stack fallback on PSRAM OOM.
    if (xTaskCreateWithCaps(ntp_server_task, "ntp_srv", stack,
                            (void *)(intptr_t)s_sock, 5, &s_task, caps) != pdPASS) {
        s_running = false;
        rc = ESP_ERR_NO_MEM;
        goto fail;
    }
    ntp_boundary("task create", ESP_OK, caps, stack);
    return ntp_owner_leave(ESP_OK);
fail:
    if (s_sock >= 0) close(s_sock);  // task creation never succeeded
    s_sock = -1;
    ntp_boundary("start", rc, caps, stack);
    return ntp_owner_leave(rc);
}

esp_err_t cym_ntp_server_stop_wait(uint32_t timeout_ms)
{
    if (!ntp_owner_enter()) return ESP_ERR_INVALID_STATE;
    s_running = false;
    // Actual suspension, not a flag just before suspension, is the join point.
    uint32_t waited = 0;
    while (s_task && eTaskGetState(s_task) != eSuspended) {
        if (waited >= timeout_ms) {
            if (timeout_ms) ESP_LOGW(TAG, "NTP stop timeout; worker/fd/stack retained");
            return ntp_owner_leave(ESP_ERR_TIMEOUT);
        }
        uint32_t step = timeout_ms - waited;
        if (step > 10) step = 10;
        vTaskDelay(pdMS_TO_TICKS(step) ? pdMS_TO_TICKS(step) : 1);
        waited += step;
    }
    if (s_task) {
        vTaskDeleteWithCaps(s_task);  // non-self; worker already closed its fd
        s_task = NULL;
        s_sock = -1;
        if (cym_debug_enabled()) ESP_LOGI(TAG, "NTP worker reaped");
    }
    return ntp_owner_leave(ESP_OK);
}

void cym_ntp_server_stop(void)
{
    (void)cym_ntp_server_stop_wait(3000);
}

void cym_ntp_server_get_stats(cym_ntp_server_stats_t *out)
{
    if (out) {
        portENTER_CRITICAL(&s_stats_mux);
        *out = s_stats;
        portEXIT_CRITICAL(&s_stats_mux);
        out->running = s_running;
    }
}
