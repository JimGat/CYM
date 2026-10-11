/* Isolated main-owner SPI transport. LVGL lends rotated draw memory until
 * flush_ready: neither a busy bus nor a delayed DMA is permission to discard it.
 * Wait in bounded slices feeding the main watchdog; retain bus and buffer until
 * the real completion ISR. No worker enters LVGL or this helper.
 */
#ifndef CYM_GAME_PANEL_TRANSPORT_H
#define CYM_GAME_PANEL_TRANSPORT_H
static inline void game_panel_transfer(esp_lcd_panel_handle_t panel,
                                      int x1,int y1,int x2,int y2,const void *pixels)
{
    while(xSemaphoreTake(sd_spi_mutex,pdMS_TO_TICKS(20))!=pdTRUE)
        esp_task_wdt_reset();
    xSemaphoreTake(flush_done_sem,0);
    /* A failed enqueue borrows no buffer. Retry without falsely acknowledging
     * pixels. A persistent hardware failure deliberately remains fail-closed. */
    while(esp_lcd_panel_draw_bitmap(panel,x1,y1,x2,y2,pixels)!=ESP_OK) {
        esp_task_wdt_reset();vTaskDelay(1);
    }
    while(xSemaphoreTake(flush_done_sem,pdMS_TO_TICKS(20))!=pdTRUE)
        esp_task_wdt_reset();
    xSemaphoreGive(sd_spi_mutex);
}
static inline void game_panel_clear(esp_lcd_panel_handle_t panel,void *buffer,
                                   int width,int height,int lines)
{
    memset(buffer,0,(size_t)width*lines*sizeof(lv_color_t));
    for(int y=0;y<height;y+=lines)
        game_panel_transfer(panel,0,y,width,y+lines<height?y+lines:height,buffer);
}
#endif
