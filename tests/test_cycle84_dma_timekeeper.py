"""Compile real flush/transport and clock observation with injected faults."""
from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/home/dev/ws-c5-35-fixes/cycle84/host')
def function(s,sig):
 start=s.index(sig);i=s.index('{',start);depth=1;j=i+1
 while depth:
  depth+=(s[j]=='{')-(s[j]=='}');j+=1
 return s[start:j]
def exercise(name,code):
 OUT.mkdir(parents=True,exist_ok=True);p=OUT/(name+'.c');p.write_text(code)
 r=subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all',str(p),'-o',str(p.with_suffix(''))],capture_output=True,text=True)
 if r.returncode:raise AssertionError(r.stderr)
 r=subprocess.run([str(p.with_suffix(''))],capture_output=True,text=True,timeout=10)
 (OUT/(name+'.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise AssertionError(r.stdout+r.stderr)
 return r.stdout
TRANSPORT=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#define CONFIG_BOARD_WS_C5_35 1
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
#define ESP_OK 0
#define ESP_ERR_NO_MEM 257
#define ESP_ERR_INVALID_ARG 258
#define ESP_ERR_INVALID_STATE 259
#define ESP_ERR_TIMEOUT 260
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
#define MALLOC_CAP_DMA 1
#define MALLOC_CAP_INTERNAL 2
#define LCD_HOST 2
#define TAG "host"
typedef int esp_err_t;
typedef void *esp_lcd_panel_handle_t;
typedef uint16_t lv_color_t;
typedef struct {void *user_data;} lv_disp_drv_t;
typedef struct {int x1,y1,x2,y2;} lv_area_t;
static int lvgl_flush_counter,flush_call_count,flush_mutex_wait_count,sd_provision_active;
static void *sd_spi_mutex=(void*)1,*flush_done_sem=(void*)2;
static bool exclusive,fail_queue,never_complete,bus_busy,locked;
static unsigned lock_attempts,dma_waits,acks,releases,draws,resets,allocations,fail_on_draw;
static const uint16_t *borrowed;static uint16_t panel[320*480];
static lv_area_t pending;static uint64_t now;
static void *allocated;
static bool enforce_dma;
static jmp_buf restart_boundary;
static void *spi_bus_dma_memory_alloc(int host,size_t size,unsigned caps){assert(host==LCD_HOST);assert(caps==(MALLOC_CAP_DMA|MALLOC_CAP_INTERNAL));allocations++;allocated=aligned_alloc(64,(size+63)&~63);return allocated;}
static bool doom_ui_exclusive(void){return exclusive;}
static uint64_t esp_timer_get_time(void){now+=20000;return now;}
static const char *esp_err_to_name(int e){(void)e;return "injected";}
static void esp_task_wdt_reset(void){assert(++resets<1000);}
static void esp_restart(void){assert(borrowed&&locked&&!acks&&!releases);longjmp(restart_boundary,1);}
static void vTaskDelay(int t){(void)t;}
static int xSemaphoreTake(void*h,int t){
 if(h==sd_spi_mutex){lock_attempts++;if(bus_busy)return 0;assert(!locked);locked=true;return 1;}
 if(!t)return 0;
 dma_waits++;assert(borrowed);if(never_complete||dma_waits%4)return 0;
 for(int y=pending.y1;y<=pending.y2;y++)for(int x=pending.x1;x<=pending.x2;x++)panel[y*320+x]=*borrowed++;
 borrowed=NULL;return 1;
}
static void xSemaphoreGive(void*h){(void)h;assert(!borrowed&&locked);locked=false;releases++;}
static int esp_lcd_panel_draw_bitmap(void*p,int x1,int y1,int x2,int y2,const void*buf){
 (void)p;assert(!borrowed);draws++;
 if(fail_queue||(fail_on_draw&&draws==fail_on_draw))return ESP_ERR_NO_MEM;
 if(enforce_dma){assert(buf==allocated);assert(!((uintptr_t)buf&63));assert((x2-x1)*(y2-y1)*2<=1024);}
 pending=(lv_area_t){x1,y1,x2-1,y2-1};borrowed=buf;return 0;
}
static void lv_disp_flush_ready(lv_disp_drv_t*d){(void)d;assert(!borrowed);acks++;}
"""
class DMA(unittest.TestCase):
 def code(self):
  main=(ROOT/'ESP32C5/main/main.c').read_text();helper=(ROOT/'ESP32C5/main/game_panel_transport.h').read_text()
  init='cym_panel_transport_init();' if 'cym_panel_transport_init' in helper else ''
  metrics='#include "'+str(ROOT/'ESP32C5/components/cym_doom/include/doom_metrics.h')+'"\ndoom_metrics_t doom_metrics;\n'
  return TRANSPORT+metrics+helper+function(main,'void lvgl_flush_cb(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *color_p)\n{'),init
 def test_failed_enqueue_normal_and_exclusive_without_completion(self):
  code,init=self.code()
  print(exercise('enqueue',code+'\nint main(void){'+init+r"""
   lv_disp_drv_t d={0};lv_area_t a={0,0,6,2};uint16_t p[21]={0};fail_queue=true;
   for(int mode=0;mode<2;mode++){exclusive=mode;unsigned before=draws;lvgl_flush_cb(&d,&a,p);assert(draws==before+1);assert(!borrowed&&!locked);}
   assert(!dma_waits&&acks==2&&releases==2);puts("failed enqueue both modes: no impossible completion wait, mutex released PASS");}
"""))
 def test_non_dma_unaligned_odd_width_row_stripes_preserve_source(self):
  code,init=self.code()
  print(exercise('stripes',code+'\nint main(void){'+init+r"""
   enforce_dma=true;lv_disp_drv_t d={0};uint16_t source[320*15+1],copy[320*15];uint16_t *p=source+1;
   for(int i=0;i<320*15;i++)p[i]=i+17;memcpy(copy,p,sizeof(copy));
   for(int mode=0;mode<2;mode++)for(int w=1;w<=320;w++){
    exclusive=mode;lv_area_t a={0,0,w-1,14};lvgl_flush_cb(&d,&a,p);
    for(int y=0;y<15;y++)for(int x=0;x<w;x++)assert(panel[y*320+x]==p[y*w+x]);
    assert(!memcmp(copy,p,sizeof(copy)));assert(!borrowed&&!locked);resets=0;
   }
   assert(allocations==1);puts("dirty widths 1..320, odd lengths, non-DMA source, owned staging lifetime PASS");}
"""))
 def test_missing_real_completion_restarts_without_releasing_live_dma(self):
  code,init=self.code()
  print(exercise('missing',code+'\nint main(void){'+init+r"""
   exclusive=true;never_complete=true;lv_disp_drv_t d={0};lv_area_t a={0,0,6,2};uint16_t p[21]={0};
   if(!setjmp(restart_boundary)){lvgl_flush_cb(&d,&a,p);assert(!"must not acknowledge missing DMA");}
   assert(borrowed&&locked&&!acks&&!releases);puts("missing completion: restart retains live bus/buffer PASS");}
"""))
 def test_busy_bus_exclusive_bounded_without_borrowing(self):
  code,init=self.code()
  print(exercise('busy',code+'\nint main(void){'+init+r"""
   exclusive=true;bus_busy=true;lv_disp_drv_t d={0};lv_area_t a={0,0,6,2};uint16_t p[21]={0};lvgl_flush_cb(&d,&a,p);
   assert(!draws&&!borrowed&&!locked&&!releases&&acks==1&&lock_attempts<=100);puts("exclusive bus acquisition bounded without borrowing PASS");}
"""))
 def test_no_mutex_failed_enqueue_has_no_completion_wait(self):
  code,init=self.code()
  print(exercise('no-mutex',code+'\nint main(void){'+init+r"""
   sd_spi_mutex=NULL;lv_disp_drv_t d={0};lv_area_t a={0,0,6,2};uint16_t p[21]={0};fail_queue=true;
   lvgl_flush_cb(&d,&a,p);assert(draws==1&&!dma_waits&&!releases&&!borrowed&&acks==1);
   puts("no-mutex failed enqueue: no impossible completion wait PASS");}
"""))
 def test_error_after_completed_stripe_releases_only_completed_dma(self):
  code,init=self.code()
  print(exercise('partial',code+'\nint main(void){'+init+r"""
   exclusive=true;enforce_dma=true;fail_on_draw=2;lv_disp_drv_t d={0};lv_area_t a={0,0,319,14};uint16_t p[320*15];
   for(unsigned i=0;i<320*15;i++)p[i]=i+17;
   lvgl_flush_cb(&d,&a,p);assert(draws==2&&dma_waits==4&&releases==1&&!borrowed&&!locked&&acks==1);
   for(int x=0;x<320;x++)assert(panel[x]==p[x]);
   fail_on_draw=0;lvgl_flush_cb(&d,&a,p);assert(!borrowed&&!locked&&acks==2);
   for(int y=0;y<15;y++)for(int x=0;x<320;x++)assert(panel[y*320+x]==p[y*320+x]);
   puts("error after completed stripe: no live reuse/release, later successful recovery PASS");}
"""))
 def test_missing_completion_normal_does_not_ack_or_release(self):
  code,init=self.code()
  print(exercise('missing-normal',code+'\nint main(void){'+init+r"""
   never_complete=true;lv_disp_drv_t d={0};lv_area_t a={0,0,6,2};uint16_t p[21]={0};
   if(!setjmp(restart_boundary)){lvgl_flush_cb(&d,&a,p);assert(!"must not ack missing normal DMA");}
   assert(borrowed&&locked&&!acks&&!releases);puts("normal missing completion retains ownership through restart PASS");}
"""))
CLOCK=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
#define ESP_OK 0
#define ESP_ERR_INVALID_STATE 259
#define ESP_ERR_INVALID_ARG 258
#define ESP_ERR_TIMEOUT 260
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
#define BOARD_TIME_GPS_UNCERTAINTY_US 500000
#define BOARD_TIME_NTP_UNCERTAINTY_US 250000
#define BOARD_TIME_GPS_RTC_UNCERTAINTY_US 2000000
#define BOARD_TIME_RTOS_DRIFT_PPM 100
#define BOARD_TIME_GPS_RTC_DRIFT_PPM 100
#define ESP_LOGI(tag,fmt,...) host_log(1,fmt)
#define ESP_LOGD(tag,fmt,...) host_log(0,fmt)
#define ESP_LOGW(...) ((void)0)
typedef int esp_err_t;typedef void *SemaphoreHandle_t;typedef int pcf85063_handle_t;
typedef enum {CYM_TIME_UNSYNCED,CYM_TIME_GPS_ACQUIRING,CYM_TIME_GPS_LOCKED,CYM_TIME_NETWORK_SYNC,CYM_TIME_NTP_HOLDOVER,CYM_TIME_RTC_HOLDOVER,CYM_TIME_GPS_RTC_HOLDOVER,CYM_TIME_RTOS_HOLDOVER} cym_time_source_t;
static unsigned holdover_logs,slew_info,slew_debug,corrections,steps;
static time_t wall=1800000000;
static void host_log(int info,const char *fmt){if(info&&strstr(fmt,"Using cross-validated"))holdover_logs++;if(strstr(fmt,"Clock slewed")){if(info)slew_info++;else slew_debug++;}}
static int xSemaphoreTake(void*h,int t){(void)t;return h!=NULL;}
static void xSemaphoreGive(void*h){(void)h;}
static time_t fake_time(time_t*p){if(p)*p=wall;return wall;}
static int fake_adjtime(const struct timeval*d,struct timeval*old){(void)old;assert(d->tv_sec==1&&d->tv_usec==0);corrections++;return 0;}
static int fake_settimeofday(const struct timeval*t,const void*z){(void)t;(void)z;steps++;return 0;}
#define time fake_time
#define adjtime fake_adjtime
#define settimeofday fake_settimeofday
"""
class Timekeeper(unittest.TestCase):
 def test_entry_repeat_reentry_priority_trust_and_slew(self):
  s=(ROOT/'ESP32C5/components/cym_timekeeper/cym_timekeeper.c').read_text()
  code=CLOCK+s[s.index('static const char *TAG'):s.index('// ── NVS helpers')]
  for name in ['static void step_clock','static void slew_clock','static uint32_t grow_uncertainty','static void revoke_gps_rtc_trust','esp_err_t cym_timekeeper_observe_gps_rtc_utc']:code+=function(s,name)+'\n'
  print(exercise('clock',code+r"""
int main(void){
 s_tk_mutex=(void*)1;s_gps_rtc_trusted=true;s_last_gps_sync_epoch=wall;
 for(int i=1;i<=8;i++){wall++;assert(cym_timekeeper_observe_gps_rtc_utc(wall+1,(int64_t)i*1000000)==ESP_OK);}
 assert(s_source==CYM_TIME_GPS_RTC_HOLDOVER&&holdover_logs==1);
 assert(corrections==6&&!slew_info&&slew_debug==6&&!steps);
 assert(s_last_correction_us==1000000&&s_last_lock_mono_us==8000000&&s_holdover_base_age_ms==9000&&s_holdover_base_uncertainty_us==2000900);
 s_source=CYM_TIME_RTOS_HOLDOVER;wall++;cym_timekeeper_observe_gps_rtc_utc(wall+1,9000000);assert(holdover_logs==2);
 for(int i=0;i<3;i++){s_source= i==0?CYM_TIME_NETWORK_SYNC:i==1?CYM_TIME_GPS_LOCKED:CYM_TIME_RTC_HOLDOVER;wall++;cym_time_source_t before=s_source;cym_timekeeper_observe_gps_rtc_utc(wall+1,(int64_t)(10+i)*1000000);assert(s_source==before&&holdover_logs==2);}
 s_source=CYM_TIME_GPS_RTC_HOLDOVER;wall++;cym_timekeeper_observe_gps_rtc_utc(wall-50,13000000);assert(!s_gps_rtc_trusted&&s_source==CYM_TIME_RTOS_HOLDOVER&&holdover_logs==2);
 puts("clock entry/repeat/reentry, priority, uncertainty, trust revocation, unchanged discipline PASS");}
"""))
if __name__=='__main__':unittest.main(verbosity=2)
