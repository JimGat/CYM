from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'ESP32C5/components/cym_doom'
class Optional98(unittest.TestCase):
 def test_actual_sound_module_policy(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'.hermes') as out:
   p=Path(out)
   (p/'esp_log.h').write_text('#pragma once\n#define ESP_LOGW(...) ((void)0)\n')
   (p/'policy.c').write_text(r"""#include <assert.h>
#include <setjmp.h>
#include "i_cym_sound.c"
doom_metrics_t doom_metrics;
int W_GetNumForName(char *s){(void)s;assert(!"silent test must not load SFX");return 0;}
int W_LumpLength(unsigned int n){(void)n;return 0;}
void *W_CacheLumpNum(int n,int tag){(void)n;(void)tag;return NULL;}
static jmp_buf rejected;
static bool begin_ok,clean_ok,healthy,write_ok;
static int stop_rc,writes,stops;
bool cym_debug_enabled(void){return false;}
bool doom_audio_begin(void){return begin_ok;}
bool doom_audio_silent_ready(void){return clean_ok;}
bool doom_audio_healthy(void){return healthy;}
unsigned doom_audio_demand(void){return 1;}
bool doom_audio_write(const int16_t*p,size_t n){assert(p&&n==DOOM_AUDIO_BLOCK);writes++;return write_ok;}
int doom_audio_end(void){stops++;return stop_rc;}
_Noreturn void doom_engine_fail(const char*s){assert(s);longjmp(rejected,1);}
int main(void){
 begin_ok=false;clean_ok=true;if(!setjmp(rejected)){assert(!init(false));}else{assert(!"safe init failure must permit silent engine operation");}update();assert(!writes&&!stops);
 clean_ok=false;if(!setjmp(rejected)){init(false);assert(!"unsafe init must reject");}
 begin_ok=true;clean_ok=true;healthy=false;stop_rc=0;assert(init(false));update();assert(!ready&&stops==1&&!writes);
 begin_ok=true;healthy=false;stop_rc=-1;assert(init(false));if(!setjmp(rejected)){update();assert(!"unsafe runtime cleanup must reject");}
 stop_rc=0;healthy=true;write_ok=false;assert(init(false));update();assert(!ready&&writes==1);
 clean_ok=false;healthy=false;assert(init(false));if(!setjmp(rejected)){update();assert(!"unqualified silent board must reject");}
 return 0;}
""")
   cmd=['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-DESP_PLATFORM','-DCONFIG_BOARD_WS_C5_28=1','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-fsanitize=address,undefined','-I'+str(p),'-I'+str(COMP/'engine'),'-I'+str(COMP/'include'),str(p/'policy.c'),str(COMP/'doom_mixer.c'),'-o',str(p/'policy')]
   result=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   result=subprocess.run([str(p/'policy')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
