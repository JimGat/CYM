/*
 * ot_radio.c — OT Air Survey radio scheduler (Phase 3)
 *
 * PASSIVE ONLY — never transmits.  Multiplexes radio hardware across WiFi,
 * BLE, ESP-NOW, and 802.15.4 according to a profile-weighted time schedule.
 *
 * Scheduler task: priority 2, single FreeRTOS task, cooperative (yields every
 * pdMS_TO_TICKS(20) minimum).  Calls radio-switch hooks supplied by main.c.
 *
 * Cycle: 10 000 ms.  Each slot's dwell = weight[slot] × 100 ms, floored to
 * OT_SCHED_MIN_DWELL_MS (500 ms) when non-zero.
 */

#include "ot_radio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <string.h>

static const char *TAG = "ot_radio";

/* ── Tuning constants ────────────────────────────────────────────────────── */

#define OT_SCHED_CYCLE_MS      10000u  /* total cycle length */
#define OT_SCHED_MIN_DWELL_MS    500u  /* minimum per-slot dwell when weight > 0 */
#define OT_SCHED_YIELD_MS         20u  /* intra-dwell yield granularity */
#define OT_SCHED_STOP_WAIT_MS   3000u  /* max wait for task exit on stop */

/* ── Profile weight table ────────────────────────────────────────────────── */
/*
 * Rows: ot_survey_profile_t (0–7)
 * Cols: OT_SLOT_WIFI, OT_SLOT_BLE, OT_SLOT_154, OT_SLOT_ESPNOW
 * Each row sums to 100; multiply by 100 ms to get per-slot dwell in ms.
 */
const uint8_t OT_PROFILE_WEIGHTS[OT_PROFILE_COUNT][OT_SLOT_COUNT] = {
    /*   WIFI  BLE  154  ESPNOW */
    {  30,   30,   30,   10 },  /* OT_PROFILE_BALANCED */
    {  70,   20,    0,   10 },  /* OT_PROFILE_WIFI_HEAVY */
    {  20,   70,    0,   10 },  /* OT_PROFILE_BLE_HEAVY */
    {  20,   10,   70,    0 },  /* OT_PROFILE_154_HEAVY */
    {  30,   20,    0,   50 },  /* OT_PROFILE_ESPNOW_FOCUS */
    {  20,   70,    0,   10 },  /* OT_PROFILE_DRONE_WATCH */
    {  10,    5,   80,    5 },  /* OT_PROFILE_WIRELESSHART */
    {  10,   10,   75,    5 },  /* OT_PROFILE_THREAD_MATTER */
};

/* ── Survey lock flag (owned here, read from main.c via extern) ──────────── */

volatile bool g_ot_survey_active = false;

/* ── Internal scheduler state ────────────────────────────────────────────── */

static ot_radio_hooks_t   s_hooks       = {0};
static ot_sched_state_t   s_state       = OT_SCHED_IDLE;
static ot_radio_slot_t    s_cur_slot    = OT_SLOT_WIFI;
static ot_survey_profile_t s_profile   = OT_PROFILE_BALANCED;
static TaskHandle_t        s_task       = NULL;
static SemaphoreHandle_t   s_stop_sem   = NULL; /* signalled when task exits */

/* ── Helpers ─────────────────────────────────────────────────────────────── */

const char *ot_radio_slot_name(ot_radio_slot_t slot)
{
    switch (slot) {
    case OT_SLOT_WIFI:   return "WiFi";
    case OT_SLOT_BLE:    return "BLE";
    case OT_SLOT_154:    return "802.15.4";
    case OT_SLOT_ESPNOW: return "ESP-NOW";
    default:             return "?";
    }
}

static bool switch_to_slot(ot_radio_slot_t slot)
{
    switch (slot) {
    case OT_SLOT_WIFI:
    case OT_SLOT_ESPNOW:
        /* ESP-NOW scouts run on the WiFi radio; same switch. */
        if (s_hooks.switch_to_wifi) return s_hooks.switch_to_wifi();
        return false;
    case OT_SLOT_BLE:
        if (s_hooks.switch_to_ble) return s_hooks.switch_to_ble();
        return false;
    case OT_SLOT_154:
        if (s_hooks.switch_to_154) return s_hooks.switch_to_154();
        return false;
    default:
        return false;
    }
}

/* Dwell for `ms` milliseconds, yielding every OT_SCHED_YIELD_MS ticks. */
static bool dwell_ms(uint32_t ms)
{
    uint32_t remaining = ms;
    while (remaining > 0 && s_state == OT_SCHED_RUNNING) {
        uint32_t chunk = remaining < OT_SCHED_YIELD_MS ? remaining : OT_SCHED_YIELD_MS;
        vTaskDelay(pdMS_TO_TICKS(chunk));
        remaining -= chunk;
    }
    return s_state == OT_SCHED_RUNNING;
}

/* ── Scheduler task ──────────────────────────────────────────────────────── */

static void scheduler_task(void *arg)
{
    ESP_LOGI(TAG, "Scheduler started, profile=%s",
             ot_survey_profile_name(s_profile));

    const uint8_t *weights = OT_PROFILE_WEIGHTS[s_profile];

    while (s_state == OT_SCHED_RUNNING) {
        for (int slot = 0; slot < OT_SLOT_COUNT; slot++) {
            if (s_state != OT_SCHED_RUNNING) break;

            uint8_t w = weights[slot];
            if (w == 0) continue;

            /* Skip 802.15.4 if hook not wired (CYD2USB). */
            if (slot == OT_SLOT_154 && !s_hooks.switch_to_154) {
                ESP_LOGD(TAG, "Slot 154 unavailable on this board — skip");
                continue;
            }

            uint32_t dwell = (uint32_t)w * (OT_SCHED_CYCLE_MS / 100u);
            if (dwell < OT_SCHED_MIN_DWELL_MS) dwell = OT_SCHED_MIN_DWELL_MS;

            ESP_LOGD(TAG, "-> %s for %lums", ot_radio_slot_name(slot), (unsigned long)dwell);
            s_cur_slot = (ot_radio_slot_t)slot;

            if (!switch_to_slot(slot)) {
                /* Radio switch failed — brief pause and continue cycle. */
                ESP_LOGW(TAG, "Radio switch to %s failed", ot_radio_slot_name(slot));
                vTaskDelay(pdMS_TO_TICKS(200));
                continue;
            }

            if (!dwell_ms(dwell)) break; /* stop requested during dwell */
        }
    }

    /* Return radio to idle on exit. */
    if (s_hooks.switch_to_idle) s_hooks.switch_to_idle();

    ESP_LOGI(TAG, "Scheduler stopped");
    s_task = NULL;
    if (s_stop_sem) xSemaphoreGive(s_stop_sem);
    vTaskDelete(NULL);
}

/* ── Public API ───────────────────────────────────────────────────────────── */

void ot_radio_init(const ot_radio_hooks_t *hooks)
{
    if (!hooks) return;
    memcpy(&s_hooks, hooks, sizeof(s_hooks));

    if (!s_stop_sem) s_stop_sem = xSemaphoreCreateBinary();

    ESP_LOGI(TAG, "Radio hooks registered (154=%s)",
             s_hooks.switch_to_154 ? "yes" : "no");
}

esp_err_t ot_radio_scheduler_start(ot_survey_profile_t profile)
{
    if (s_state == OT_SCHED_RUNNING) {
        ESP_LOGW(TAG, "Scheduler already running");
        return ESP_ERR_INVALID_STATE;
    }
    if (profile >= OT_PROFILE_COUNT) return ESP_ERR_INVALID_ARG;

    s_profile   = profile;
    s_state     = OT_SCHED_RUNNING;
    s_cur_slot  = OT_SLOT_WIFI;

    /* Allocate task stack from PSRAM when available, else DRAM. */
#ifdef CONFIG_SPIRAM
    StackType_t *stack = (StackType_t *)heap_caps_malloc(
        4096 * sizeof(StackType_t), MALLOC_CAP_SPIRAM);
    StaticTask_t *tcb = (StaticTask_t *)heap_caps_malloc(
        sizeof(StaticTask_t), MALLOC_CAP_INTERNAL);
    if (stack && tcb) {
        s_task = xTaskCreateStaticPinnedToCore(
            scheduler_task, "ot_sched", 4096, NULL, 2, stack, tcb, 0);
    } else {
        if (stack) heap_caps_free(stack);
        if (tcb)   heap_caps_free(tcb);
        s_task = NULL;
    }
    if (!s_task) {
        /* Static create failed, fall back to dynamic. */
        xTaskCreate(scheduler_task, "ot_sched", 4096, NULL, 2, &s_task);
    }
#else
    xTaskCreate(scheduler_task, "ot_sched", 4096, NULL, 2, &s_task);
#endif

    if (!s_task) {
        s_state = OT_SCHED_IDLE;
        ESP_LOGE(TAG, "Failed to create scheduler task");
        return ESP_FAIL;
    }

    g_ot_survey_active = true;
    ESP_LOGI(TAG, "Survey lock ON");
    return ESP_OK;
}

esp_err_t ot_radio_scheduler_stop(void)
{
    if (s_state == OT_SCHED_IDLE) return ESP_OK;

    s_state = OT_SCHED_STOP_REQUESTED;

    /* Wait for the task to exit and signal the semaphore. */
    if (s_stop_sem) {
        if (xSemaphoreTake(s_stop_sem, pdMS_TO_TICKS(OT_SCHED_STOP_WAIT_MS)) != pdTRUE) {
            /* Timed out — force-delete as a last resort. */
            ESP_LOGW(TAG, "Scheduler task did not exit in %u ms — force deleting",
                     OT_SCHED_STOP_WAIT_MS);
            if (s_task) { vTaskDelete(s_task); s_task = NULL; }
        }
    }

    s_state            = OT_SCHED_IDLE;
    g_ot_survey_active = false;
    ESP_LOGI(TAG, "Survey lock OFF");
    return ESP_OK;
}

ot_radio_slot_t ot_radio_current_slot(void) { return s_cur_slot; }
