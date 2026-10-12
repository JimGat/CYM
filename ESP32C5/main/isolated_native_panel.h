/* ONLY included inside WS28/WS35 isolated boot. Normal transport untouched.
 * Rasterizer writes the independent internal aligned 4096-byte boot stage
 * only AFTER LVGL synchronous flush has drained; sole main panel owner.
 */
#ifndef CYM_ISOLATED_NATIVE_PANEL_H
#define CYM_ISOLATED_NATIVE_PANEL_H
static bool game_native_send(void *ctx,doom_rect r,const uint16_t *pixels)
{
 (void)ctx;cym_display_diag *d=&s_display_diag[1];
 if(pixels!=s_panel_stage||r.x<0||r.y<0||r.w<=0||r.h<=0||
    (size_t)r.w*r.h>CYM_PANEL_STAGE_BYTES/sizeof(uint16_t))return false;
 if(!game_native_poll(NULL))return false;
 uint32_t before=(uint32_t)esp_timer_get_time();
 cym_diag_callback_begin(d,r.w,r.h,CYM_PANEL_STAGE_BYTES,before);
 uint32_t admission=(uint32_t)esp_timer_get_time();
 /* One local tick admission only; no 2s retry series or lock over a frame.
  * Priority inheritance still applies while engine owns shared SD transport. */
 bool locked=sd_spi_mutex&&xSemaphoreTake(sd_spi_mutex,pdMS_TO_TICKS(10))==pdTRUE;
 cym_diag_admission(d,1,!locked,(uint32_t)esp_timer_get_time()-admission);
 if(!locked){cym_diag_callback_end(d,false,(uint32_t)esp_timer_get_time());return false;}
 xSemaphoreTake(flush_done_sem,0);
 uint32_t token=cym_diag_prepare(&s_display_channel),start=(uint32_t)esp_timer_get_time();
 esp_err_t err=esp_lcd_panel_draw_bitmap(panel_handle,r.x,r.y,r.x+r.w,r.y+r.h,pixels);
 uint32_t returned=(uint32_t)esp_timer_get_time();cym_diag_draw(d,returned-start,err==ESP_OK);
 bool complete=false;
 if(err==ESP_OK){
  uint32_t wait=(uint32_t)esp_timer_get_time();
  for(unsigned tries=0;tries<100;tries++){
   if(xSemaphoreTake(flush_done_sem,pdMS_TO_TICKS(20))==pdTRUE){
    uint32_t seen,stamp;
    if(cym_diag_sample(&s_display_channel,&seen,&stamp)&&seen==token){
     uint32_t resumed=(uint32_t)esp_timer_get_time();
     cym_diag_resume(d,&s_display_channel,token,start,returned,resumed,resumed-wait);
     complete=true;break;
    }
   }
   /* Poll cancellation, but NEVER release/reuse accepted DMA until completion.
    * This poll changes keys/cancel only; cleanup/join is outside this helper. */
   (void)game_native_poll(NULL);cym_panel_watchdog_feed();
  }
  if(!complete){
   ESP_LOGE("display","Native DMA completion missing; reboot retains bus/stage (intent consumed)");
   esp_restart();for(;;)vTaskDelay(pdMS_TO_TICKS(20));
  }
 }else __atomic_store_n(&s_display_channel.pending,0,__ATOMIC_RELEASE);
 xSemaphoreGive(sd_spi_mutex);
 cym_diag_callback_end(d,complete,(uint32_t)esp_timer_get_time());
 if(complete)DM_ADD(panel_flushes,1);
 DM_ADD(panel_us,(uint32_t)esp_timer_get_time()-before);
 return complete;
}
#endif
