// Narrow Waveshare 5B transport. Canonical application remains ESP32C5/main/main.c.
#include "ws_s3_5b_port.h"
#if defined(CONFIG_BOARD_WS_S3_5B)
#include "board_hal.h"
#include "cym_viewport.h"
#include "esp_lcd_panel_rgb.h"
#include "esp_cache.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_check.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_timer.h"
#include <string.h>
#if LV_COLOR_DEPTH != 16 || LV_COLOR_16_SWAP
#error "WS-S3-5B requires native RGB565 (LV_COLOR_DEPTH=16, LV_COLOR_16_SWAP=0)"
#endif
static const char *TAG = "ws_s3_5b";
static const cym_viewport_t viewport = {BOARD_LCD_WIDTH, BOARD_LCD_HEIGHT, BOARD_UI_SCALE};
static i2c_master_bus_handle_t shared_bus;
static i2c_master_dev_handle_t ch_mode, ch_output, gt911;
static SemaphoreHandle_t io_lock, touch_lock;
static uint8_t outputs = 0x1E; // EXIO1 touch RST, EXIO2 BL, EXIO3 LCD RST, EXIO4 SD_CS
// ISR context and semaphore control block MUST remain internal for cache-off windows.
typedef struct {
 esp_lcd_panel_handle_t panel;
 uint16_t *fb[2];
 SemaphoreHandle_t frame_done;
 StaticSemaphore_t frame_done_storage;
 volatile uint32_t boundaries;
 uint32_t pending_boundary;
 unsigned next;
 bool pending;
} rgb_state_t;
static DRAM_ATTR rgb_state_t rgb;
static esp_err_t add_device(uint8_t address, i2c_master_dev_handle_t *dev) {
 i2c_device_config_t cfg={.dev_addr_length=I2C_ADDR_BIT_LEN_7,.device_address=address,.scl_speed_hz=400000};
 return i2c_master_bus_add_device(shared_bus,&cfg,dev);
}
static esp_err_t set_outputs(uint8_t mask, uint8_t value) {
 if(!io_lock || !ch_output) return ESP_ERR_INVALID_STATE;
 if(xSemaphoreTake(io_lock,pdMS_TO_TICKS(100))!=pdTRUE) return ESP_ERR_TIMEOUT;
 uint8_t next=(outputs & ~mask) | (value & mask);
 esp_err_t err=i2c_master_transmit(ch_output,&next,1,100);
 if(err==ESP_OK) outputs=next;
 xSemaphoreGive(io_lock);return err;
}
esp_err_t board_sd_set_selected(bool selected) { return set_outputs(1<<4,selected?0:(1<<4)); }
esp_err_t ws_s3_5b_backlight(bool on) { return set_outputs(1<<2,on?(1<<2):0); }
esp_err_t ws_s3_5b_bus_init(i2c_master_bus_handle_t bus) {
 if(!bus) return ESP_ERR_INVALID_ARG;
 shared_bus=bus;io_lock=xSemaphoreCreateMutex();touch_lock=xSemaphoreCreateMutex();
 if(!io_lock || !touch_lock) return ESP_ERR_NO_MEM;
 ESP_RETURN_ON_ERROR(add_device(0x24,&ch_mode),TAG,"CH422G mode function");
 ESP_RETURN_ON_ERROR(add_device(0x38,&ch_output),TAG,"CH422G output function");
 uint8_t mode=1;ESP_RETURN_ON_ERROR(i2c_master_transmit(ch_mode,&mode,1,100),TAG,"CH422G mode");
 // Preserve every output bit during resets. Keep backlight dark until framebuffer ready.
 ESP_RETURN_ON_ERROR(set_outputs(0xff,0x1A),TAG,"CH422G startup outputs");
 ESP_RETURN_ON_ERROR(set_outputs(1<<3,0),TAG,"LCD reset low");
 vTaskDelay(pdMS_TO_TICKS(10));
 ESP_RETURN_ON_ERROR(set_outputs(1<<3,1<<3),TAG,"LCD reset high");
 vTaskDelay(pdMS_TO_TICKS(50));
 return ESP_OK;
}
static bool IRAM_ATTR frame_complete(esp_lcd_panel_handle_t panel,
 const esp_lcd_rgb_panel_event_data_t *event, void *ctx) {
 (void)panel;(void)event;rgb_state_t *s=ctx;BaseType_t wake=pdFALSE;
 s->boundaries++;
 xSemaphoreGiveFromISR(s->frame_done,&wake);return wake==pdTRUE;
}
esp_err_t ws_s3_5b_display_init(esp_lcd_panel_handle_t *panel) {
 if(!panel || !shared_bus) return ESP_ERR_INVALID_STATE;
 rgb.frame_done=xSemaphoreCreateBinaryStatic(&rgb.frame_done_storage);
 rgb.next=1; // driver starts with framebuffer0
 // Latest vendor 08_lvgl_v8_demo explicit 1024x600 branch: 21MHz, H145/170/30 V23/12/2.
 // Older IO_Test uses 18MHz H188/44/88 V16/3/6. Use the newer resolution-specific profile.
 esp_lcd_rgb_panel_config_t cfg={
  .clk_src=LCD_CLK_SRC_DEFAULT,
  .timings={.pclk_hz=21000000,.h_res=1024,.v_res=600,
   .hsync_back_porch=145,.hsync_front_porch=170,.hsync_pulse_width=30,
   .vsync_back_porch=23,.vsync_front_porch=12,.vsync_pulse_width=2,
   .flags.pclk_active_neg=1},
  .data_width=16,.num_fbs = 2,.bounce_buffer_size_px=1024*10,.dma_burst_size=64,
  .hsync_gpio_num=46,.vsync_gpio_num=3,.de_gpio_num=5,.pclk_gpio_num=7,.disp_gpio_num=-1,
  .data_gpio_nums={14,38,18,17,10,39,0,45,48,47,21,1,2,42,41,40},
  .flags.fb_in_psram=1,
 };
 ESP_RETURN_ON_ERROR(esp_lcd_new_rgb_panel(&cfg,&rgb.panel),TAG,"RGB allocate");
 void *fb0=NULL,*fb1=NULL;
 ESP_RETURN_ON_ERROR(esp_lcd_rgb_panel_get_frame_buffer(rgb.panel,2,&fb0,&fb1),TAG,"RGB buffers");
 rgb.fb[0]=fb0;rgb.fb[1]=fb1;
 size_t bytes=1024*600*sizeof(uint16_t);
 memset(rgb.fb[0],0,bytes);memset(rgb.fb[1],0,bytes);
 ESP_RETURN_ON_ERROR(esp_cache_msync(rgb.fb[0],bytes,ESP_CACHE_MSYNC_FLAG_DIR_C2M),TAG,"fb0 cache");
 ESP_RETURN_ON_ERROR(esp_cache_msync(rgb.fb[1],bytes,ESP_CACHE_MSYNC_FLAG_DIR_C2M),TAG,"fb1 cache");
 esp_lcd_rgb_panel_event_callbacks_t cb={.on_frame_buf_complete=frame_complete};
 ESP_RETURN_ON_ERROR(esp_lcd_rgb_panel_register_event_callbacks(rgb.panel,&cb,&rgb),TAG,"RGB callbacks");
 ESP_RETURN_ON_ERROR(esp_lcd_panel_reset(rgb.panel),TAG,"RGB reset");
 ESP_RETURN_ON_ERROR(esp_lcd_panel_init(rgb.panel),TAG,"RGB init");
 spi_bus_config_t sd={.mosi_io_num=11,.miso_io_num=13,.sclk_io_num=12,
  .quadwp_io_num=-1,.quadhd_io_num=-1,.max_transfer_sz=4096};
 ESP_RETURN_ON_ERROR(spi_bus_initialize(BOARD_SD_SPI_HOST,&sd,SPI_DMA_CH_AUTO),TAG,"SD bus");
 *panel=rgb.panel;
 ESP_LOGI(TAG,"1024x600 RGB / 512x300 logical x2; two PSRAM FB, 10-line bounce; RTC bus shared");
 return ESP_OK;
}
static bool wait_retired(void) {
 int64_t deadline=esp_timer_get_time()+250000;
 while((int32_t)(rgb.boundaries-rgb.pending_boundary)<0) {
  if(esp_timer_get_time()>=deadline) return false;
  xSemaphoreTake(rgb.frame_done,pdMS_TO_TICKS(20));
 }
 rgb.pending=false;rgb.next^=1;return true;
}
void ws_s3_5b_flush(lv_disp_drv_t *drv,const lv_area_t *area,lv_color_t *pixels) {
 // Timeout never gives permission to overwrite an in-flight framebuffer. Next flush
 // first rechecks the outstanding retirement fence; panel buffers live for boot lifetime.
 if(rgb.pending && !wait_retired()) {lv_disp_flush_ready(drv);return;}
 if(area->x1!=0 || area->y1!=0 || area->x2!=BOARD_LCD_WIDTH-1 || area->y2!=BOARD_LCD_HEIGHT-1) {
  ESP_LOGE(TAG,"RGB viewport needs full_refresh frame");lv_disp_flush_ready(drv);return;
 }
 uint16_t *target=rgb.fb[rgb.next];
 if(!cym_viewport_expand_rgb565(&viewport,(const uint16_t *)pixels,target)) {lv_disp_flush_ready(drv);return;}
 esp_err_t err=esp_cache_msync(target,1024*600*2,ESP_CACHE_MSYNC_FLAG_DIR_C2M);
 if(err==ESP_OK) err=esp_lcd_panel_draw_bitmap(rgb.panel,0,0,1024,600,target);
 if(err==ESP_OK) {
  // IDF bounce completion changes bb_fb_index before the callback. Two boundaries
  // after submission ensure any racing old-frame boundary and its preloads retired.
  rgb.pending_boundary=rgb.boundaries+2;rgb.pending=true;
  if(!wait_retired()) ESP_LOGE(TAG,"RGB retirement timeout; buffer frozen until fence completes");
 } else ESP_LOGE(TAG,"RGB submit: %s",esp_err_to_name(err));
 lv_disp_flush_ready(drv);
}
static esp_err_t gt_read(uint16_t reg,uint8_t *data,size_t len) {
 uint8_t cmd[2]={reg & 0xff,reg>>8};return i2c_master_transmit_receive(gt911,cmd,2,data,len,100);
}
static esp_err_t gt_write(uint16_t reg,uint8_t value) {
 uint8_t cmd[3]={reg & 0xff,reg>>8,value};return i2c_master_transmit(gt911,cmd,3,100);
}
esp_err_t ws_s3_5b_touch_init(void) {
 // GT911 selects 0x5D with INT held LOW during reset (official vendor sequence).
 gpio_config_t irq={.pin_bit_mask=1ULL<<4,.mode=GPIO_MODE_OUTPUT};
 ESP_RETURN_ON_ERROR(gpio_config(&irq),TAG,"touch INT output");gpio_set_level(4,0);
 ESP_RETURN_ON_ERROR(set_outputs(1<<1,0),TAG,"touch reset low");vTaskDelay(pdMS_TO_TICKS(100));
 ESP_RETURN_ON_ERROR(set_outputs(1<<1,1<<1),TAG,"touch reset high");vTaskDelay(pdMS_TO_TICKS(200));
 gpio_set_direction(4,GPIO_MODE_INPUT);
 uint8_t id[4];
 if(i2c_master_probe(shared_bus,0x5D,100)==ESP_OK) ESP_RETURN_ON_ERROR(add_device(0x5D,&gt911),TAG,"GT911 5D");
 else ESP_RETURN_ON_ERROR(add_device(0x14,&gt911),TAG,"GT911 14");
 ESP_RETURN_ON_ERROR(gt_read(0x8140,id,4),TAG,"GT911 product");
 ESP_LOGI(TAG,"GT911 product %.4s; inverse viewport touch",id);return ESP_OK;
}
bool ws_s3_5b_touch_read(uint16_t *x,uint16_t *y,bool *pressed) {
 if(!x || !y || !pressed) return false;
 *pressed=false;
 if(!gt911 || xSemaphoreTake(touch_lock,pdMS_TO_TICKS(100))!=pdTRUE) return false;
 static bool contact=false;static uint16_t last_x,last_y;
 uint8_t status=0,point[8];bool ok=false;
 esp_err_t err=gt_read(0x814E,&status,1);
 if(err==ESP_OK && (status & 0x80)) {
  unsigned count=status & 0x0f;
  if(count>0 && count<=5 && gt_read(0x8150,point,sizeof(point))==ESP_OK) {
   uint16_t px=point[1] | point[2]<<8,py=point[3] | point[4]<<8;
   *pressed=cym_viewport_touch(&viewport,px,py,x,y);ok=true;
  } else ok=(count==0);
  if(gt_write(0x814E,0)!=ESP_OK) ok=false;
  contact=ok ? *pressed : false;
  if(contact) {last_x=*x;last_y=*y;}
 } else if(err==ESP_OK) {
  // Not-ready means no new sample, NOT release. GT911 reports release as ready/count0.
  *pressed=contact;*x=last_x;*y=last_y;ok=true;
 } else contact=false;
 xSemaphoreGive(touch_lock);return ok;
}
#endif
