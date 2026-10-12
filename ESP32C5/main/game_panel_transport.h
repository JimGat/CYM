/* Main-owner SPI transport shared by normal CYM and isolated rendering.
 * LVGL rotation memory is PSRAM (or a square rotated in-place). Never use a
 * draw buffer as staging: it may be the source or contain later rotation rows.
 * One separately owned boot allocation prevents runtime private TX allocation.
 */
#ifndef CYM_GAME_PANEL_TRANSPORT_H
#define CYM_GAME_PANEL_TRANSPORT_H
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
    if (!s_panel_stage || !pixels || width <= 0 || y2 <= y1)
        return ESP_ERR_INVALID_ARG;
    const size_t row_bytes = (size_t)width * sizeof(lv_color_t);
    if (row_bytes > CYM_PANEL_STAGE_BYTES) return ESP_ERR_INVALID_ARG;
    bool locked = false;
    if (sd_spi_mutex) {
        const unsigned attempts = wait_bus ? 100 : 1;
        for (unsigned i = 0; i < attempts; i++) {
            if (xSemaphoreTake(sd_spi_mutex, pdMS_TO_TICKS(wait_bus ? 20 : 5)) == pdTRUE) {
                locked = true;
                break;
            }
            cym_panel_watchdog_feed();
        }
        if (!locked) return ESP_ERR_TIMEOUT;
    }
    const unsigned char *source = pixels;
    esp_err_t err = ESP_OK;
    for (int y = y1; y < y2;) {
        int rows = CYM_PANEL_STAGE_BYTES / row_bytes;
        if (rows > y2 - y) rows = y2 - y;
        const size_t bytes = row_bytes * rows;
        memcpy(s_panel_stage, source, bytes);
        xSemaphoreTake(flush_done_sem, 0);
        /* Each stripe fits every SPI adapter's max_transfer_sz (>=4096).
         * Thus this call queues ONE color transaction: error means no borrowed
         * color memory, unlike a partially queued multi-transaction frame.
         * Internal SRAM on these SoCs needs pointer alignment, not padded TX
         * lengths. Send exact odd RGB565 widths; never add pixels to the panel. */
        err = esp_lcd_panel_draw_bitmap(panel, x1, y, x2, y + rows, s_panel_stage);
        if (err != ESP_OK) break;  /* no completion exists; no forever retry */
        bool completed = false;
        for (unsigned i = 0; i < 100; i++) {
            if (xSemaphoreTake(flush_done_sem, pdMS_TO_TICKS(20)) == pdTRUE) {
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
