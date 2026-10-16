"""Compile production seek/WAD adapters; failed seek logging is bounded and unlocked."""
from pathlib import Path
import os,subprocess,tempfile,unittest
from test_sd_psram_led_capabilities import body
ROOT=Path(__file__).resolve().parents[1]
PRE=r"""
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdarg.h>
#include <errno.h>
#include <string.h>
#define CYM_DEBUG_HOST_STATE 1
#define DOOM_STARTUP_DIAG_HOST 1
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
#define MALLOC_CAP_DMA 4
#define MALLOC_CAP_SPIRAM 8
typedef void *TaskHandle_t;
static bool debug=true,locked;static unsigned logs,samples,seeks,reads,read_diag_count;
static int seek_rc,seek_errno;static char output[2048];
bool cym_debug_enabled(void){return debug;}
static size_t heap_caps_get_free_size(unsigned c){assert(!locked);samples++;return c;}
static size_t heap_caps_get_largest_free_block(unsigned c){assert(!locked);samples++;return c;}
static unsigned uxTaskGetStackHighWaterMark(TaskHandle_t t){assert(!locked);samples++;return t?2:1;}
static void logger(const char *tag,const char *fmt,...){assert(!locked&&tag);va_list ap;va_start(ap,fmt);char b[1024];vsnprintf(b,sizeof(b),fmt,ap);va_end(ap);if(strstr(b,"WAD_SEEK_FAILED"))strcpy(output,b);logs++;errno=ERANGE;}
#define ESP_LOGI logger
#include "doom_startup_diag.h"
#define DM_IO_SEEK 1
static void check_stop(void){}
static void doom_engine_fail(const char*s){(void)s;assert(0);}
static bool io_lock(unsigned op){assert(op==1&&!locked);locked=true;return true;}
static void io_unlock(void){assert(locked);locked=false;errno=EBUSY;}
static void io_observed(unsigned op,unsigned n,bool fail){assert(!locked&&op==1&&n==0&&fail==(seek_rc!=0));errno=EAGAIN;}
static int fake_seek(FILE*f,long off,int whence){assert(locked&&f&&off==100&&whence==SEEK_SET);seeks++;errno=seek_errno;return seek_rc;}
#define fseek fake_seek
typedef struct{unsigned length;}wad_file_t;
typedef struct{wad_file_t wad;FILE*f;}native_wad;
static size_t doom_owned_fread(void*b,size_t s,size_t n,FILE*f){assert(!locked&&b&&f&&s==1);reads++;return n;}
"""
class SeekDiagnostics307(unittest.TestCase):
 def test_real_wad_seek_failure_and_controls(self):
  source=(ROOT/'ESP32C5/components/cym_doom/doom_session.c').read_text()
  code=PRE+'int doom_owned_fseek(FILE*f,long off,int whence){'+body(source,'doom_owned_fseek')+'}\n'
  code+='static size_t wad_read(wad_file_t*p,unsigned off,void*buf,size_t n){'+body(source,'wad_read')+'}\n'
  code+=r"""
int main(void){native_wad w={.wad={10000},.f=(FILE*)1};char b[8396];
seek_rc=-1;seek_errno=ENOMEM;assert(wad_read(&w.wad,100,b,sizeof(b))==0);
assert(seeks==1&&!reads&&!locked&&logs==2&&samples==7&&errno==ENOMEM);
assert(strstr(output,"offset=100")&&strstr(output,"result=-1"));char exp[32];snprintf(exp,sizeof(exp),"errno=%d",ENOMEM);assert(strstr(output,exp));
for(int i=0;i<20;i++)assert(!wad_read(&w.wad,100,b,sizeof(b)));
assert(read_diag_count==4&&logs==8&&samples==28);
debug=false;read_diag_count=0;logs=samples=0;assert(!wad_read(&w.wad,100,b,sizeof(b))&&errno==ENOMEM);assert(!logs&&!samples&&!read_diag_count);
debug=true;seek_rc=0;seek_errno=EDOM;assert(wad_read(&w.wad,100,b,sizeof(b))==sizeof(b)&&reads==1&&errno==EDOM);assert(!logs&&!samples);
unsigned before=seeks;assert(!wad_read(&w.wad,10001,b,1)&&seeks==before);return 0;}
"""
  with tempfile.TemporaryDirectory(dir=os.environ.get('CYM_WD_TEST_TMPDIR')) as d:
   p=Path(d);(p/'test.c').write_text(code)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'ESP32C5/components/cym_doom/include'),str(p/'test.c'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
