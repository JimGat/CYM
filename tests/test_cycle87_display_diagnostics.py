"""Production diagnostic helpers with synthetic clocks; NOT hardware timings."""
from pathlib import Path
import subprocess, unittest
import test_cycle84_dma_timekeeper as c84
ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/home/dev/ws-c5-35-fixes/cycle87/host')
def run(name, code, extra=()):
 OUT.mkdir(parents=True,exist_ok=True);p=OUT/(name+'.c');p.write_text(code)
 r=subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'ESP32C5/main'),str(p),'-o',str(p.with_suffix('')),*extra],capture_output=True,text=True)
 if r.returncode:raise AssertionError(r.stderr)
 r=subprocess.run([str(p.with_suffix(''))],capture_output=True,text=True,timeout=20)
 (OUT/(name+'.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise AssertionError(r.stdout+r.stderr)
 return r.stdout
PREFIX=r"""
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "display_diagnostics.h"
"""
class Diagnostics87(unittest.TestCase):
 def test_missing_production_helper(self):
  self.assertTrue((ROOT/'ESP32C5/main/display_diagnostics.h').exists(),'approved production diagnostic helper absent')
 def test_accounting_geometry_rejection_delayed_early_wrap(self):
  print(run('accounting',PREFIX+r"""
int main(void){
 cym_display_diag d={0};cym_diag_channel c={0};
 assert(cym_diag_stripes(10,480,4096)==3);
 assert(cym_diag_stripes(480,10,4096)==3);
 assert(cym_diag_stripes(7,480,4096)==2);
 assert(cym_diag_stripes(320,15,4096)==3);
 for(int rotation=0;rotation<4;rotation++){
  unsigned w=rotation%2?10:480,h=rotation%2?480:10;
  cym_diag_callback_begin(&d,w,h,4096,100);
  cym_diag_admission(&d,2,1,70);
  cym_diag_callback_end(&d,false,200);
 }
 assert(d.callbacks==4&&d.rejected==4&&!d.accepted&&!d.completed);
 assert(d.planned==12&&d.admit_attempts==8&&d.admit_rejects==4&&d.callback_us==400);
 uint32_t token=cym_diag_prepare(&c);
 cym_diag_isr(&c,120);
 cym_diag_draw(&d,40,true);
 cym_diag_resume(&d,&c,token,100,140,160,20);
 assert(d.completed==1&&d.early==1&&d.draw_to_isr_us==20&&d.resume_us==40&&d.wait_us==20);
 uint32_t prior=token;token=cym_diag_prepare(&c);
 cym_diag_resume(&d,&c,token,200,210,220,10);
 assert(d.completed==1&&d.uncorrelated==1);
 assert(prior!=token);cym_diag_isr(&c,250);
 cym_diag_resume(&d,&c,token,200,210,290,80);
 assert(d.completed==2&&d.draw_to_isr_us==70&&d.resume_us==80&&d.early==1);
 c.next=UINT32_MAX;token=cym_diag_prepare(&c);assert(token==1);
 cym_diag_isr(&c,5);cym_diag_resume(&d,&c,token,UINT32_MAX-9,UINT32_MAX-4,15,20);
 assert(d.draw_to_isr_us==85&&d.resume_us==90);
 d.copy_us=UINT32_MAX-3;cym_diag_copy(&d,10);assert(d.copy_us==6);
 puts("synthetic accounting: native10x480, rotations/odd widths, rejection, delayed/early/stale completion and rollover PASS");
}
"""))
 def test_isr_snapshot_concurrency(self):
  print(run('concurrency',PREFIX+r"""
#include <pthread.h>
static cym_diag_channel c;static uint32_t done;
static void *writer(void *p){(void)p;for(uint32_t i=1;i<100000;i++){__atomic_store_n(&c.pending,i,__ATOMIC_RELEASE);cym_diag_isr(&c,i*3);}__atomic_store_n(&done,1,__ATOMIC_RELEASE);return NULL;}
int main(void){pthread_t t;assert(!pthread_create(&t,NULL,writer,NULL));unsigned observed=0;while(!__atomic_load_n(&done,__ATOMIC_ACQUIRE)){uint32_t token,stamp;if(cym_diag_sample(&c,&token,&stamp)&&token){assert(stamp==token*3);observed++;}}pthread_join(t,NULL);uint32_t token,stamp;assert(cym_diag_sample(&c,&token,&stamp)&&stamp==token*3);printf("bounded concurrent ISR snapshots PASS observed=%u\n",observed);}
""",('-pthread',)))
 def test_real_transport_native_and_fail_closed(self):
  code,init=c84.DMA().code()
  print(run('transport-native',code+'\nint main(void){'+init+r"""
 enforce_dma=true;lv_disp_drv_t d={0};lv_area_t a={0,0,9,479};uint16_t p[10*480];for(int i=0;i<4800;i++)p[i]=i+1;
 lvgl_flush_cb(&d,&a,p);assert(draws==3&&!borrowed&&!locked&&acks==1);
 assert(s_display_diag[0].completed==3&&s_display_diag[0].accepted_draws==3&&s_display_diag[0].planned==3);
 assert(s_display_diag[0].geometry[0].width==10&&s_display_diag[0].geometry[0].height==480);
 for(int y=0;y<480;y++)for(int x=0;x<10;x++)assert(panel[y*320+x]==p[y*10+x]);
 fail_queue=true;lvgl_flush_cb(&d,&a,p);assert(s_display_diag[0].completed==3&&s_display_diag[0].rejected==1);
 fail_queue=false;bus_busy=true;exclusive=true;lvgl_flush_cb(&d,&a,p);assert(s_display_diag[1].admit_attempts==100&&s_display_diag[1].rejected==1&&!s_display_diag[1].completed);
 puts("real transport synthetic native10x480 completion vs accepted/rejected/busy PASS");}
"""))
 def test_transport_early_completion_correlates_before_return(self):
  code,init=c84.DMA().code()
  code=code.replace('if(!t)return 0;', 'if(!t)return 0;if(early_ready){early_ready=false;return 1;}')
  code=code.replace('static void host_completion(void);','static bool early_ready;static void host_completion(void);')
  code=code.replace('borrowed=buf;return 0;', 'borrowed=buf;borrowed=NULL;host_completion();early_ready=true;return 0;')
  print(run('early-transport',code+'\nint main(void){'+init+r"""
 lv_disp_drv_t d={0};lv_area_t a={0,0,6,2};uint16_t p[21]={0};lvgl_flush_cb(&d,&a,p);lvgl_flush_cb(&d,&a,p);
 assert(draws==2&&acks==2&&s_display_diag[0].completed==2&&s_display_diag[0].early==2&&!s_display_diag[0].uncorrelated&&!borrowed&&!locked);
 puts("production transport synthetic ISR before draw return; sequential correct correlation PASS");}
"""))
 def test_production_io_lock_hold_boundaries(self):
  session=(ROOT/'ESP32C5/components/cym_doom/doom_session.c').read_text()
  metrics=str(ROOT/'ESP32C5/components/cym_doom/include/doom_metrics.h')
  chunk=session[session.index('static uint32_t io_admission_us'):session.index('int doom_owned_forbidden')]
  code=r"""
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdlib.h>
#define ESP_PLATFORM 1
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
#include """+'"'+metrics+'"'+r"""
doom_metrics_t doom_metrics;
#include <errno.h>
static inline void doom_read_diag(unsigned *c,size_t s,size_t n,size_t r,int e,int f,int er){(void)c;(void)s;(void)n;(void)r;(void)e;(void)f;(void)er;}
static inline void doom_seek_diag(unsigned *c,long o,int w,int r,int e){(void)c;(void)o;(void)w;(void)r;(void)e;}
static uint32_t clock_us;static bool busy,held;static void *sd_spi_mutex=(void*)1;
static unsigned file_n;static FILE *files[16];static char wad_path[]="fixture";
static uint32_t metric_us(void){return clock_us;}
static uint32_t metric_delta(uint32_t start,uint32_t end){return end-start;}
static uint32_t metric_elapsed(uint32_t start){return metric_delta(start,metric_us());}
static void check_stop(void){}
static void doom_engine_fail(const char *s){(void)s;abort();}
static int xSemaphoreTake(void*p,int ticks){assert(p==sd_spi_mutex&&ticks==2000&&!held);clock_us+=30;if(busy)return 0;held=true;return 1;}
static void xSemaphoreGive(void*p){assert(p==sd_spi_mutex&&held);clock_us+=1003;held=false;}
static FILE *fake_fopen(const char*p,const char*m){(void)p;(void)m;assert(held);clock_us+=10;return (FILE*)3;}
static int fake_fclose(FILE*f){(void)f;assert(held);clock_us+=11;return 0;}
static size_t fake_fread(void*p,size_t s,size_t n,FILE*f){(void)p;(void)f;assert(held);clock_us+=20;return s?n:0;}
static int fake_fseek(FILE*f,long o,int w){(void)f;(void)o;(void)w;assert(held);clock_us+=12;return -1;}
static long fake_ftell(FILE*f){(void)f;assert(held);clock_us+=13;return 42;}
#define ferror(f) 0
#define feof(f) 0
#define fopen fake_fopen
#define fclose fake_fclose
#define fread fake_fread
#define fseek fake_fseek
#define ftell fake_ftell
"""
  print(run('io-boundaries',code+chunk+r"""
int main(void){__atomic_store_n(&doom_metrics.io_phase,DM_IO_INIT,__ATOMIC_RELAXED);FILE*f=doom_owned_fopen("fixture","rb");assert(f);char b[6];assert(doom_owned_fread(b,2,3,f)==3);assert(doom_owned_fseek(f,0,SEEK_SET)==-1);assert(doom_owned_ftell(f)==42);assert(!doom_owned_fclose(f));assert(!held&&!file_n);
 assert(DM_IO_GET(DM_IO_INIT,admission_us)==150&&DM_IO_GET(DM_IO_INIT,hold_us)==66);
 assert(DM_IO_GET(DM_IO_INIT,bytes)==6&&DM_IO_GET(DM_IO_INIT,failures)==1&&DM_IO_GET(DM_IO_INIT,tells)==1);
 __atomic_store_n(&doom_metrics.io_phase,DM_IO_RUNNING,__ATOMIC_RELAXED);busy=true;assert(!io_lock(DM_IO_READ));assert(DM_IO_GET(DM_IO_RUNNING,admission_us)==30&&DM_IO_GET(DM_IO_RUNNING,failures)==1&&!DM_IO_GET(DM_IO_RUNNING,hold_us));
 puts("production I/O synthetic mutex admission/hold, VFS operations and rejection phase PASS");}
"""))
 def test_reporter_real_elapsed_and_rate_gate(self):
  report=(ROOT/'ESP32C5/main/display_diagnostics_report.h').read_text()
  code=PREFIX+r"""
#include <stdarg.h>
static uint64_t now;static unsigned logs;
static bool cym_debug_enabled(void){return true;}
static uint32_t cym_debug_generation(void){return 0;}
static uint64_t esp_timer_get_time(void){return now;}
static void host_log(const char*t,const char*f,...){(void)t;logs++;va_list ap;va_start(ap,f);vprintf(f,ap);puts("");va_end(ap);}
#define ESP_LOGI host_log
"""+report+r"""
int main(void){now=1000000;cym_display_diag_report();cym_diag_callback_begin(&s_display_diag[0],10,480,4096,100);cym_diag_callback_end(&s_display_diag[0],false,200);now=4999000;cym_display_diag_report();assert(!logs);now=9500000;cym_display_diag_report();assert(logs==1);now=9600000;cym_display_diag_report();assert(logs==1);puts("synthetic reporter actual interval=9500ms; bounded rate PASS");}
"""
  output=run('reporter',code);self.assertIn('interval_ms=9500',output);self.assertIn('g0=10x480/9600B/3',output);print(output)
 def test_engine_io_phase_accounting(self):
  metrics=str(ROOT/'ESP32C5/components/cym_doom/include/doom_metrics.h')
  print(run('engine-io',r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include """+'"'+metrics+'"'+r"""
doom_metrics_t doom_metrics;
int main(void){dm_io_record(DM_IO_INIT,DM_IO_READ,30,50,17,0);dm_io_record(DM_IO_RUNNING,DM_IO_SEEK,70,9,0,1);dm_io_record(DM_IO_INIT,DM_IO_OPEN,2000,0,0,1);
 assert(DM_IO_GET(DM_IO_INIT,reads)==1&&DM_IO_GET(DM_IO_INIT,opens)==1&&DM_IO_GET(DM_IO_INIT,bytes)==17);
 assert(DM_IO_GET(DM_IO_INIT,admission_us)==2030&&DM_IO_GET(DM_IO_INIT,hold_us)==50&&DM_IO_GET(DM_IO_INIT,failures)==1);
 assert(DM_IO_GET(DM_IO_RUNNING,seeks)==1&&DM_IO_GET(DM_IO_RUNNING,failures)==1);
 assert(!DM_IO_GET(DM_IO_VALIDATION,reads));puts("synthetic engine I/O separate phase/admission/hold/operation/read-byte accounting PASS");}
"""))
if __name__=='__main__':unittest.main(verbosity=2)
