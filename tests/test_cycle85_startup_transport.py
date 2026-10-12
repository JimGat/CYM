"""Real transport batching/subscription and startup SD sentinel regressions."""
from pathlib import Path
import unittest
import test_cycle84_dma_timekeeper as cycle84
from test_cycle84_dma_timekeeper import exercise
ROOT=Path(__file__).resolve().parents[1]
class Transport85(unittest.TestCase):
 def test_real_transport_batches_rows_without_unsubscribed_feeds(self):
  code,init=cycle84.DMA().code()
  code=code.replace('static int esp_task_wdt_status(void *task){(void)task;return ESP_OK;}','')
  code=code.replace('static void esp_task_wdt_reset(void){assert(++resets<1000);}', 'static bool subscribed; static int esp_task_wdt_status(void *t){(void)t;return subscribed?ESP_OK:ESP_ERR_INVALID_STATE;} static void esp_task_wdt_reset(void){assert(subscribed);assert(++resets<1000);}')
  code=code.replace('<=1024','<=4096')
  exercise('cycle85-batching',code+'\nint main(void){'+init+r"""
   enforce_dma=true;lv_disp_drv_t d={0};lv_area_t a={0,0,319,14};uint16_t p[320*15];
   for(unsigned i=0;i<320*15;i++)p[i]=i+1;
   lvgl_flush_cb(&d,&a,p);assert(draws<=3&&!resets&&!borrowed&&!locked);
   for(int i=0;i<320*15;i++)assert(panel[i]==p[i]);
   subscribed=true;draws=0;lvgl_flush_cb(&d,&a,p);assert(draws<=3&&resets&&!borrowed&&!locked);
   puts("320x15 real transport <=3 transactions; pre-subscription no feeds; subscribed feeds PASS");}
""")
 def test_landscape_width_and_delayed_completion_keep_ownership(self):
  code,init=cycle84.DMA().code()
  code=code.replace("static int takes,draws,resets;", "static int takes,draws,resets; static int delayed;")
  code=code.replace("memcpy(expected,p,n);", "memcpy(expected,p,n);delayed=2;")
  code=code.replace("assert(memcmp(borrowed,expected,borrowed_bytes)==0);", "assert(memcmp(borrowed,expected,borrowed_bytes)==0);if(delayed-- > 0)return 0;")
  code=code.replace("panel[320*64]", "panel[480*64]").replace("panel[y*320+x]", "panel[y*480+x]")
  exercise("cycle85-landscape-delayed",code+"\nint main(void){"+init+r"""
   enforce_dma=true;lv_disp_drv_t d={0};lv_area_t a={0,0,479,14};uint16_t p[480*15];
   for(unsigned i=0;i<480*15;i++)p[i]=i+1;
   lvgl_flush_cb(&d,&a,p);assert(draws==4&&resets>=12&&!borrowed&&!locked);
   for(int i=0;i<480*15;i++)assert(panel[i]==p[i]);
   puts("480x15 four transactions with two delayed completion waits each; ownership and watchdog PASS");}
""")
 def test_rotated_width_batches(self):
  helper=(ROOT/'ESP32C5/main/game_panel_transport.h').read_text()
  self.assertIn('4096',helper)
class Startup85(unittest.TestCase):
 def test_initial_mount_sentinel_before_cache_and_consent(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text()
  boot=s[s.index('void app_main(void)'):s.index('static uint32_t flush_call_count')]
  self.assertIn('sd_startup_missing_dirs',boot)
  self.assertLess(boot.index('sd_startup_missing_dirs'),boot.index('sd_cache_load_all();'))
  self.assertIn('show_sd_startup_provision_prompt',boot)
  isolated=s[s.index('PANEL_CLEARED'):s.index('void app_main(void)')]
  self.assertNotIn('sd_startup_missing_dirs',isolated)
 def test_three_paths_real_stat_and_no_creation(self):
  p=ROOT/'ESP32C5/main/sd_startup_check.h'
  self.assertTrue(p.exists(),'startup read-only sentinel helper missing')
  exercise('cycle85-sentinels',r"""
#include <assert.h>
#include <stdio.h>
#include <sys/stat.h>
#include <string.h>
static unsigned mask,calls;
static int fake_stat(const char*p,struct stat*s){unsigned bit=!strcmp(p,"/sdcard/lab/deauths")?1:!strcmp(p,"/sdcard/lab/gattwalker")?2:!strcmp(p,"/sdcard/lab/otsurvey")?4:0;assert(bit);calls++;s->st_mode=(mask&bit)?S_IFREG:S_IFDIR;return 0;}

"""+p.read_text().replace('stat(','fake_stat(')+r"""
int main(void){for(mask=0;mask<8;mask++){calls=0;assert(sd_startup_missing_dirs()==mask);assert(calls==3);}puts("all directory/file combinations, three read-only sentinels PASS");}
""")
if __name__=='__main__':unittest.main()
