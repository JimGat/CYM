"""Compile production startup helpers and the real read wrapper; no hardware claims."""
from pathlib import Path
import os, subprocess, tempfile, unittest
from test_sd_psram_led_capabilities import body
ROOT=Path(__file__).resolve().parents[1]
INC=ROOT/'ESP32C5/components/cym_doom/include'
PRE=r"""
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <setjmp.h>
#define CYM_DEBUG_HOST_STATE 1
#define DOOM_STARTUP_DIAG_HOST 1
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
#define MALLOC_CAP_DMA 4
#define MALLOC_CAP_SPIRAM 8
typedef void *TaskHandle_t;
static bool debug;
static int samples,logs,locked,unlocks,reads,stops,observed;
static char output[4096],read_output[4096];
bool cym_debug_enabled(void){return debug;}
static size_t heap_caps_get_free_size(unsigned c){assert(!locked);samples++;return c*100;}
static size_t heap_caps_get_largest_free_block(unsigned c){assert(!locked);samples++;return c*10;}
static unsigned uxTaskGetStackHighWaterMark(TaskHandle_t t){assert(!locked);samples++;return t?222:111;}
static void log_info(const char *tag,const char *fmt,...){assert(!locked);assert(strcmp(tag,"CYM_DOOM")==0);va_list ap;va_start(ap,fmt);vsnprintf(output,sizeof(output),fmt,ap);va_end(ap);if(strstr(fmt,"WAD_READ_SHORT"))strcpy(read_output,output);logs++;errno=ERANGE;}
#define ESP_LOGI log_info
#include "doom_startup_diag.h"
static size_t got;static int read_errno,err_flag,eof_flag;
static size_t fake_read(void *p,size_t s,size_t n,FILE *f){assert(locked);assert(p&&f);(void)s;(void)n;reads++;errno=read_errno;return got;}
static int fake_error(FILE *f){assert(f&&locked);errno=ENOTTY;return err_flag;}
static int fake_eof(FILE *f){assert(f&&locked);errno=ENOSPC;return eof_flag;}
#define fread fake_read
#define ferror fake_error
#define feof fake_eof
#define DM_IO_READ 1
#define DM_ADD(a,b) ((void)(b))
static unsigned read_diag_count;
static jmp_buf fail;
static void check_stop(void){stops++;}
_Noreturn static void doom_engine_fail(const char *s){assert(s);longjmp(fail,1);}
static bool admit=true;
static bool io_lock(unsigned op){assert(op==1&&!locked);if(!admit)return false;locked=1;return true;}
static void io_unlock(void){assert(locked);locked=0;unlocks++;errno=EBUSY;}
static void io_observed(unsigned op,uint32_t n,bool failed){assert(op==1&&!locked);assert(n==got*2);assert(failed==(err_flag!=0));observed++;errno=EAGAIN;}
static uint32_t metric_us(void){return 10;}
"""
class StartupDiag306(unittest.TestCase):
 def test_production_helpers_and_read_wrapper(self):
  session=(ROOT/'ESP32C5/components/cym_doom/doom_session.c').read_text()
  code=PRE+'size_t doom_owned_fread(void *p,size_t s,size_t n,FILE *f){'+body(session,'doom_owned_fread')+'}\n'+r"""
int main(void){
 debug=false;doom_startup_diag("OFF",0,NULL);assert(!samples&&!logs);
 debug=true;doom_startup_diag("TEST",-7,(void*)1);assert(samples==8&&logs==1);
 assert(strstr(output,"TEST")&&strstr(output,"result=-7"));
 assert(strstr(output,"free_internal=300")&&strstr(output,"largest_internal=30"));
 assert(strstr(output,"free_dma=400")&&strstr(output,"largest_dma=40"));
 assert(strstr(output,"free_psram=800")&&strstr(output,"largest_psram=80"));
 assert(strstr(output,"stack_current=111")&&strstr(output,"stack_audio=222"));
 char buf[16];FILE *f=(FILE*)1;
 for(int on=0;on<2;on++)for(int scenario=0;scenario<4;scenario++){
  debug=on;read_diag_count=0;samples=logs=0;
  got=scenario==0?4:(scenario==1?2:0);err_flag=scenario==2;eof_flag=scenario==1;
  read_errno=scenario==2?ENOMEM:EDOM;
  int u=unlocks,rd=reads;size_t rc=doom_owned_fread(buf,2,4,f);
  assert(rc==got&&!locked&&unlocks==u+1&&reads==rd+1&&errno==read_errno);
  assert(logs==((on&&scenario!=0)?2:0));
  assert(samples==((on&&scenario!=0)?7:0));
  if(on&&scenario!=0){assert(strstr(output,"WAD_READ_MEMORY"));assert(strstr(read_output,"requested_items=4")&&strstr(read_output,"item_size=2")&&strstr(read_output,"requested_bytes=8"));char expected[64];snprintf(expected,sizeof(expected),"errno=%d",read_errno);assert(strstr(read_output,expected));snprintf(expected,sizeof(expected),"returned_items=%lu",(unsigned long)got);assert(strstr(read_output,expected));snprintf(expected,sizeof(expected),"ferror=%d",err_flag);assert(strstr(read_output,expected));snprintf(expected,sizeof(expected),"feof=%d",eof_flag);assert(strstr(read_output,expected));}
 }
 debug=true;got=0;err_flag=1;eof_flag=0;read_errno=ENOMEM;read_diag_count=0;samples=logs=0;
 for(int i=0;i<20;i++)assert(doom_owned_fread(buf,2,4,f)==0&&errno==ENOMEM);
 assert(logs==8&&samples==28&&read_diag_count==4);
 int rd=reads,u=unlocks;
 if(!setjmp(fail)){doom_owned_fread(buf,2,SIZE_MAX,f);assert(0);}assert(reads==rd&&unlocks==u&&!locked);
 admit=false;if(!setjmp(fail)){doom_owned_fread(buf,2,4,f);assert(0);}assert(reads==rd&&unlocks==u&&!locked);
 return 0;
}
"""
  with tempfile.TemporaryDirectory(dir=os.environ.get('CYM_WD_TEST_TMPDIR')) as d:
   p=Path(d);(p/'test.c').write_text(code)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(INC),str(p/'test.c'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
 def test_allocation_boundaries_and_init_entry(self):
  audio=(ROOT/'ESP32C5/components/cym_doom/doom_audio.c').read_text()
  b=body(audio,'doom_audio_begin')
  for before,call,after in [('I2S_CHANNEL_BEFORE','i2s_new_channel(','I2S_CHANNEL_AFTER'),('I2S_STD_BEFORE','i2s_channel_init_std_mode(','I2S_STD_AFTER'),('PCM_QUEUE_BEFORE','heap_caps_malloc(','PCM_QUEUE_AFTER'),('AUDIO_TASK_BEFORE','xTaskCreate(','AUDIO_TASK_AFTER')]:
   self.assertLess(b.index(before),b.index(call));self.assertLess(b.index(call),b.index(after))
   self.assertLess(b.index(after),b.index('goto fail',b.index(call)))
  self.assertIn('ch.dma_desc_num=4;ch.dma_frame_num=256;ch.auto_clear=true;',b)
  self.assertIn('xQueueCreateStatic(8,sizeof(audio_block),audio_queue_storage,&audio_queue_control)',b)
  self.assertIn('MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT',b)
  self.assertIn('xTaskCreate(audio_worker,"cym_pcm",4096,NULL,3,&audio_task)',b)
  session=(ROOT/'ESP32C5/components/cym_doom/doom_session.c').read_text()
  b=body(session,'doom_session_start');self.assertLess(b.index('ENGINE_INIT_ENTRY'),b.index('state=raw_alloc'))
  rd=body(session,'doom_owned_fread');self.assertLess(rd.index('errno'),rd.index('io_unlock'))
  self.assertLess(rd.index('feof'),rd.index('io_unlock'));self.assertLess(rd.index('io_unlock'),rd.index('doom_read_diag'))
  self.assertNotIn('register_failed_alloc',audio+session)
if __name__=='__main__':unittest.main()
