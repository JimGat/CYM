/* Main-owner SPI transport shared by normal CYM and isolated rendering.
 * LVGL rotation memory is PSRAM (or a square rotated in-place). Never use a
 * draw buffer as staging: it may be the source or contain later rotation rows.
 * One separately owned boot allocation prevents runtime private TX allocation.
 */
#ifndef CYM_GAME_PANEL_TRANSPORT_H
#define CYM_GAME_PANEL_TRANSPORT_H
#include "display_diagnostics.h"
#define CYM_PANEL_STAGE_BYTES 4096
static void *s_panel_stage;

/* Startup renders before main_task subscribes. Never reset an unsubscribed task. */
static inline void cym_panel_watchdog_feed(void)
{
    if (esp_task_wdt_status(NULL) == ESP_OK) esp_task_wdt_reset();
}

/* The bus allocator supplies its native TX/RX alignment, not guessed malloc
 * alignment. Allocate after SPI init, before radio/tasks consume internal RAM. */
static inline esp_err_t cym_panel_transport_init(void)
{
    if (!s_panel_stage) {
        s_panel_stage = spi_bus_dma_memory_alloc(LCD_HOST, CYM_PANEL_STAGE_BYTES,
                                                MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
        ESP_LOGI("display", "Owned SPI DMA staging=%p bytes=%u (boot allocation)",
                 s_panel_stage, (unsigned)CYM_PANEL_STAGE_BYTES);
    }
    return s_panel_stage ? ESP_OK : ESP_ERR_NO_MEM;
}

static inline esp_err_t cym_panel_transfer(esp_lcd_panel_handle_t panel,
                                           int x1, int y1, int x2, int y2,
                                           const void *pixels, bool wait_bus)
{
    const int width = x2 - x1;
    cym_display_diag *diag = &s_display_diag[wait_bus ? 1 : 0];
    cym_diag_callback_begin(diag, width > 0 ? width : 0, y2 > y1 ? y2-y1 : 0,
                            CYM_PANEL_STAGE_BYTES, (uint32_t)esp_timer_get_time());
    if (!s_panel_stage || !pixels || width <= 0 || y2 <= y1) {
        cym_diag_callback_end(diag, false, (uint32_t)esp_timer_get_time());
        return ESP_ERR_INVALID_ARG;
    }
    const size_t row_bytes = (size_t)width * sizeof(lv_color_t);
    if (row_bytes > CYM_PANEL_STAGE_BYTES) {
        cym_diag_callback_end(diag, false, (uint32_t)esp_timer_get_time());
        return ESP_ERR_INVALID_ARG;
    }
    uint32_t admission_start = (uint32_t)esp_timer_get_time();
    unsigned admission_attempts = 0, admission_rejects = 0;
    bool locked = false;
    if (sd_spi_mutex) {
        const unsigned attempts = wait_bus ? 100 : 1;
        for (unsigned i = 0; i < attempts; i++) {
            admission_attempts++;
            if (xSemaphoreTake(sd_spi_mutex, pdMS_TO_TICKS(wait_bus ? 20 : 5)) == pdTRUE) {
                locked = true;
                break;
            }
            admission_rejects++;
            cym_panel_watchdog_feed();
        }
        if (!locked) {
            cym_diag_admission(diag, admission_attempts, admission_rejects,
                               (uint32_t)esp_timer_get_time() - admission_start);
            cym_diag_callback_end(diag, false, (uint32_t)esp_timer_get_time());
            return ESP_ERR_TIMEOUT;
        }
    }
    cym_diag_admission(diag, admission_attempts, admission_rejects,
                       (uint32_t)esp_timer_get_time() - admission_start);
    const unsigned char *source = pixels;
    esp_err_t err = ESP_OK;
    for (int y = y1; y < y2;) {
        int rows = CYM_PANEL_STAGE_BYTES / row_bytes;
        if (rows > y2 - y) rows = y2 - y;
        const size_t bytes = row_bytes * rows;
        uint32_t copy_start = (uint32_t)esp_timer_get_time();
        memcpy(s_panel_stage, source, bytes);
        cym_diag_copy(diag, (uint32_t)esp_timer_get_time() - copy_start);
        xSemaphoreTake(flush_done_sem, 0);
        /* Each stripe fits every SPI adapter's max_transfer_sz (>=4096).
         * Thus this call queues ONE color transaction: error means no borrowed
         * color memory, unlike a partially queued multi-transaction frame.
         * Internal SRAM on these SoCs needs pointer alignment, not padded TX
         * lengths. Send exact odd RGB565 widths; never add pixels to the panel. */
        uint32_t token = cym_diag_prepare(&s_display_channel);
        uint32_t draw_start = (uint32_t)esp_timer_get_time();
        err = esp_lcd_panel_draw_bitmap(panel, x1, y, x2, y + rows, s_panel_stage);
        uint32_t draw_return = (uint32_t)esp_timer_get_time();
        cym_diag_draw(diag, draw_return - draw_start, err == ESP_OK);
        if (err != ESP_OK) {
            __atomic_store_n(&s_display_channel.pending, 0, __ATOMIC_RELEASE);
            break;  /* no completion exists; no forever retry */
        }
        uint32_t wait_start = (uint32_t)esp_timer_get_time();
        bool completed = false;
        for (unsigned i = 0; i < 100; i++) {
            if (xSemaphoreTake(flush_done_sem, pdMS_TO_TICKS(20)) == pdTRUE) {
                uint32_t resumed = (uint32_t)esp_timer_get_time();
                cym_diag_resume(diag, &s_display_channel, token, draw_start,
                                draw_return, resumed, resumed - wait_start);
                completed = true;
                break;
            }
            cym_panel_watchdog_feed();
        }
        if (!completed) {
            /* A successful enqueue still owns staging and the shared bus.
             * Do NOT release either or return to LVGL on missing completion.
             * Restart is fail-closed recovery, not a fabricated DMA ack. The
             * isolated one-shot NVS intent was already consumed at boot. */
            ESP_LOGE("display", "DMA completion missing; restarting with bus/buffer retained");
            esp_restart();
            for (;;) vTaskDelay(pdMS_TO_TICKS(20));
        }
        source += bytes;
        y += rows;
        cym_panel_watchdog_feed();
    }
    if (locked) xSemaphoreGive(sd_spi_mutex);
    cym_diag_callback_end(diag, err == ESP_OK, (uint32_t)esp_timer_get_time());
    return err;
}

static inline esp_err_t game_panel_transfer(esp_lcd_panel_handle_t panel,
                                             int x1, int y1, int x2, int y2,
                                             const void *pixels)
{
    return cym_panel_transfer(panel, x1, y1, x2, y2, pixels, true);
}
static inline esp_err_t game_panel_clear(esp_lcd_panel_handle_t panel, void *buffer,
                                          int width, int height, int lines)
{
    memset(buffer, 0, (size_t)width * lines * sizeof(lv_color_t));
    for (int y = 0; y < height; y += lines) {
        esp_err_t err = game_panel_transfer(panel, 0, y, width,
                                            y + lines < height ? y + lines : height, buffer);
        if (err != ESP_OK) return err;
    }
    return ESP_OK;
}
#endif
