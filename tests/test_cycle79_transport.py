"""Extract real production flush callback: busy bus and slow DMA must not lose pixels."""
from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
PRE=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define CONFIG_BOARD_WS_C5_35 1
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
#define ESP_OK 0
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
typedef int esp_err_t;
typedef void *esp_lcd_panel_handle_t;
typedef uint16_t lv_color_t;
typedef struct {void *user_data;} lv_disp_drv_t;
typedef struct {int x1,y1,x2,y2;} lv_area_t;
static int lvgl_flush_counter,flush_call_count,flush_mutex_wait_count,sd_provision_active;
static void *sd_spi_mutex=(void*)1,*flush_done_sem=(void*)2;
static unsigned lock_attempts,dma_waits,acks,releases,draws;
static const uint16_t *borrowed;static uint16_t panel[320*480];
static lv_area_t pending;static uint64_t now;
static bool doom_ui_exclusive(void){return true;}
static uint64_t esp_timer_get_time(void){return ++now;}
static void esp_task_wdt_reset(void){}
static void vTaskDelay(int t){(void)t;}
static int xSemaphoreTake(void*h,int t){
 if(h==sd_spi_mutex)return ++lock_attempts>3;
 if(!t)return 0;
 if(++dma_waits<4)return 0;
 for(int y=pending.y1;y<=pending.y2;y++)for(int x=pending.x1;x<=pending.x2;x++)panel[y*320+x]=*borrowed++;
 borrowed=NULL;return 1;
}
static void xSemaphoreGive(void*h){(void)h;assert(!borrowed);releases++;}
static int esp_lcd_panel_draw_bitmap(void*p,int x1,int y1,int x2,int y2,const void*buf){(void)p;assert(!borrowed);pending=(lv_area_t){x1,y1,x2-1,y2-1};borrowed=buf;draws++;return 0;}
static void lv_disp_flush_ready(lv_disp_drv_t*d){(void)d;assert(!borrowed);acks++;}
"""
class Transport(unittest.TestCase):
 def test_real_flush_retains_busy_and_slow_dma_buffer(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text();start=s.index('void lvgl_flush_cb(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *color_p)\n{');i=s.index('{',start);depth=1;j=i+1
  while depth:
   if s[j]=='{':depth+=1
   if s[j]=='}':depth-=1
   j+=1
  fn=s[start:j]
  o=ROOT/'.hermes/cycle79/transport';o.mkdir(parents=True,exist_ok=True)
  helper=ROOT/'ESP32C5/main/game_panel_transport.h'
  inc='#include "'+str(helper)+'"\n' if helper.exists() else ''
  metrics='#include "'+str(ROOT/'ESP32C5/components/cym_doom/include/doom_metrics.h')+'"\ndoom_metrics_t doom_metrics;\n'
  code=PRE+metrics+inc+fn+r"""
int main(void){
 memset(panel,0x7e,sizeof(panel));uint16_t pixels[320*15];memset(pixels,0,sizeof(pixels));lv_disp_drv_t d={0};
 for(int y=0;y<480;y+=15){lv_area_t a={0,y,319,y+14};dma_waits=0;lvgl_flush_cb(&d,&a,pixels);}
 assert(draws==32);assert(acks==32);assert(releases==32);assert(lock_attempts>=35);
 for(unsigned i=0;i<320*480;i++)assert(panel[i]==0);
 puts("actual production flush: busy retry, slow DMA ownership, full native coverage PASS");
}
"""
  (o/'host.c').write_text(code)
  c=subprocess.run(['cc','-std=gnu11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',str(o/'host.c'),'-o',str(o/'host')],capture_output=True,text=True)
  self.assertEqual(c.returncode,0,c.stderr)
  run=subprocess.run([str(o/'host')],capture_output=True,text=True)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
