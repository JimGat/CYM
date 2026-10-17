/*
 * ot_radio.c — OT Air Survey radio scheduler (Phase 3)
 *
 * PASSIVE ONLY — never transmits.  Multiplexes radio hardware across WiFi,
 * BLE, ESP-NOW, and 802.15.4 according to a profile-weighted time schedule.
 *
 * Scheduler task: priority 0 (below the main LVGL/WDT task's priority 1 — see
 * OT_SCHED_TASK_PRIO below), single FreeRTOS task, cooperative (yields every
 * pdMS_TO_TICKS(20) minimum during dwell).  Calls radio-switch hooks supplied
 * by main.c.
 *
 * Cycle: 10 000 ms.  Each slot's dwell = weight[slot] × 100 ms, floored to
 * OT_SCHED_MIN_DWELL_MS (500 ms) when non-zero.
 *
 * Why full radio-switch instead of the WiFi/BT/802.15.4 coexistence arbiter:
 * ESP-IDF's own coexistence guide (docs.espressif.com/projects/esp-idf/en/
 * stable/esp32c5/api-guides/coexist.html) marks BLE-Scan + 802.15.4-Scan as
 * an unsupported combination on the shared single-radio C5, and calls
 * continuous-RX WiFi + 802.15.4 (router/border-router style) unsupported on
 * one RF path — Espressif's own fix for that case is a second SoC. Since OT
 * Survey needs WiFi scan, BLE scan, and 802.15.4 scan all in the same
 * session, running them under CONFIG_ESP_COEX_SW_COEXIST_ENABLE concurrently
 * is a documented non-starter; sequential full deinit/reinit per slot (never
 * two stacks live at once) sidesteps the arbiter entirely instead of fighting
 * an unsupported combination. Contrast with wardrive's WiFi+BLE concurrency
 * (main.c), which the same doc DOES list as a supported/stable pairing and
 * which we tuned empirically to <=12.5% BLE duty — that one legitimately
 * rides the coex arbiter's time-slicing instead of avoiding it.
 */

#include "ot_radio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_heap_caps.h"
#include <string.h>

static const char *TAG = "ot_radio";

/* ── Tuning constants ────────────────────────────────────────────────────── */

#define OT_SCHED_CYCLE_MS      10000u  /* total cycle length */
#define OT_SCHED_MIN_DWELL_MS    500u  /* minimum per-slot dwell when weight > 0 */
#define OT_SCHED_YIELD_MS         20u  /* intra-dwell yield granularity */
#define OT_SCHED_STOP_WAIT_MS   3000u  /* max wait for task exit on stop */
#define OT_SCHED_WIFI_MAX_EXTRA_MS 4000u  /* bounded extension past the weighted WiFi/ESPNOW
                                             dwell, letting a still-in-flight passive scan
                                             finish naturally instead of being hard-aborted
                                             mid-sweep — see wifi_scan_busy in ot_radio.h */

/* Task priority — MUST stay below ESP_TASK_MAIN_PRIO (1), the priority the
 * main LVGL/WDT loop's task runs at (see esp_task.h: ESP_TASK_MAIN_PRIO =
 * ESP_TASK_PRIO_MIN + 1). Unlike the RF-HAT scan tasks (priority 2, brief
 * per-channel busy-waits), each slot switch here can run a full WiFi or BLE
 * stack init/deinit (300-700ms of largely non-yielding driver code). At
 * priority 2 that fully preempted the main task for the whole call, starving
 * lv_timer_handler() for up to ~1s at a time and tripping the firmware's own
 * "WDT timeout at 10s risk" warning. Priority 0 (tskIDLE_PRIORITY) guarantees
 * the main task always preempts this one when ready. */
#define OT_SCHED_TASK_PRIO        0u

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

_Atomic bool g_ot_survey_active = false;

/* ── Internal scheduler state ────────────────────────────────────────────── */

static ot_radio_hooks_t   s_hooks       = {0};
static _Atomic ot_sched_state_t s_state       = OT_SCHED_IDLE;
static _Atomic ot_radio_slot_t s_cur_slot    = OT_SLOT_WIFI;
static ot_survey_profile_t s_profile   = OT_PROFILE_BALANCED;
static TaskHandle_t        s_task       = NULL;
static StackType_t *s_stack;
static StaticTask_t *s_tcb;

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

            /* WiFi and ESPNOW slots share the WiFi radio's passive scan
             * (switch_to_slot() routes both to switch_to_wifi()). A full
             * 2.4+5GHz passive sweep takes ~5.5s+ — longer than most profiles'
             * weighted WiFi share (as little as 1s for WirelessHART/
             * Thread-Matter) — so without this, the scan was hard-aborted
             * mid-sweep on nearly every cycle, yielding empty or partial
             * results regardless of what was actually in range. Extend up to
             * OT_SCHED_WIFI_MAX_EXTRA_MS while the scan is still running,
             * polling at the same granularity as dwell_ms() so a stop request
             * is honored promptly. */
            if ((slot == OT_SLOT_WIFI || slot == OT_SLOT_ESPNOW) &&
                s_hooks.wifi_scan_busy) {
                uint32_t extra = 0;
                while (extra < OT_SCHED_WIFI_MAX_EXTRA_MS &&
                       s_state == OT_SCHED_RUNNING &&
                       s_hooks.wifi_scan_busy()) {
                    vTaskDelay(pdMS_TO_TICKS(OT_SCHED_YIELD_MS));
                    extra += OT_SCHED_YIELD_MS;
                }
            }
        }
    }

    /* Return radio to idle on exit. */
    if (s_hooks.switch_to_idle) s_hooks.switch_to_idle();

    ESP_LOGI(TAG, "Scheduler stopped");
    /* Publish completion, then park. Owner also verifies eSuspended before
     * deletion: publication alone is not proof this stack is off-core. */
    s_state = OT_SCHED_PARKED;
    for (;;) vTaskSuspend(NULL);
}

/* ── Public API ───────────────────────────────────────────────────────────── */

void ot_radio_init(const ot_radio_hooks_t *hooks)
{
    if (!hooks || s_state != OT_SCHED_IDLE) return;
    memcpy(&s_hooks, hooks, sizeof(s_hooks));


    ESP_LOGI(TAG, "Radio hooks registered (154=%s)",
             s_hooks.switch_to_154 ? "yes" : "no");
}

esp_err_t ot_radio_scheduler_start(ot_survey_profile_t profile)
{
    if (s_state != OT_SCHED_IDLE || s_task) {
        ESP_LOGW(TAG, "Scheduler already running");
        return ESP_ERR_INVALID_STATE;
    }
    if ((unsigned)profile >= OT_PROFILE_COUNT) return ESP_ERR_INVALID_ARG;

    g_ot_survey_active = true;
    s_profile   = profile;
    s_state     = OT_SCHED_RUNNING;
    s_cur_slot  = OT_SLOT_WIFI;

    /* Preserve 4096-byte stack capacity/priority. Record caller-owned storage. */
#ifdef CONFIG_SPIRAM
    s_stack=heap_caps_malloc(4096*sizeof(StackType_t),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    s_tcb=heap_caps_malloc(sizeof(StaticTask_t),MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    if (s_stack && s_tcb)
        s_task=xTaskCreateStaticPinnedToCore(scheduler_task,"ot_sched",4096,NULL,
                    OT_SCHED_TASK_PRIO,s_stack,s_tcb,0);
    if (!s_task) {
        heap_caps_free(s_stack);heap_caps_free(s_tcb);s_stack=NULL;s_tcb=NULL;
    }
#else
    /* No-PSRAM boards keep their existing bounded internal task path. A PSRAM
     * board fails admission instead of silently borrowing scarce internal RAM. */
    xTaskCreate(scheduler_task,"ot_sched",4096,NULL,OT_SCHED_TASK_PRIO,&s_task);
#endif

    if (!s_task) {
        s_state = OT_SCHED_IDLE;
        g_ot_survey_active = false;
        ESP_LOGE(TAG, "Failed to create scheduler task");
        return ESP_FAIL;
    }

    g_ot_survey_active = true;
    ESP_LOGI(TAG, "Survey lock ON");
    return ESP_OK;
}

bool ot_radio_scheduler_owns_current_task(void)
{
    return s_task && xTaskGetCurrentTaskHandle()==s_task;
}

esp_err_t ot_radio_scheduler_stop(void)
{
    if (s_state == OT_SCHED_IDLE) return ESP_OK;
    if (s_state == OT_SCHED_RUNNING) s_state = OT_SCHED_STOP_REQUESTED;
    for (unsigned waited=0; waited<OT_SCHED_STOP_WAIT_MS; waited+=20) {
        if (s_state == OT_SCHED_PARKED && s_task && eTaskGetState(s_task)==eSuspended) {
            bool offcore=true;
            for (unsigned core=0;core<configNUMBER_OF_CORES;core++)
                if (xTaskGetCurrentTaskHandleForCore(core)==s_task) offcore=false;
            if (!offcore) { vTaskDelay(pdMS_TO_TICKS(20));continue; }
            vTaskDelete(s_task);s_task=NULL;
            heap_caps_free(s_stack);heap_caps_free(s_tcb);s_stack=NULL;s_tcb=NULL;
            s_state=OT_SCHED_IDLE;g_ot_survey_active=false;
            return ESP_OK;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    /* No force delete, no new allocation, no conflicting admission on timeout. */
    return ESP_ERR_TIMEOUT;
}

ot_radio_slot_t ot_radio_current_slot(void) { return s_cur_slot; }
