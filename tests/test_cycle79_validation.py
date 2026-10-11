"""Actual production validator + real SHA256/private WAD, no mount or asset shortcut."""
from pathlib import Path
import subprocess,unittest
import run_selector_host as ui
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'.hermes/doom-prototype/fixtures/freedoom-0.13.0/freedoom1.wad'
CRYPTO=r"""
#include <openssl/sha.h>
#include <stdint.h>
#include <stddef.h>
typedef SHA256_CTX psa_hash_operation_t;
#define PSA_HASH_OPERATION_INIT {0}
#define PSA_SUCCESS 0
#define PSA_ALG_SHA_256 0
extern unsigned test_updates,test_cancel_after;
extern void test_cancel(void);
static inline int psa_crypto_init(void){return 0;}
static inline int psa_hash_setup(psa_hash_operation_t*h,int alg){(void)alg;return SHA256_Init(h)?0:-1;}
static inline int psa_hash_update(psa_hash_operation_t*h,const void*p,size_t n){int rc=SHA256_Update(h,p,n)?0:-1;if(++test_updates==test_cancel_after)test_cancel();return rc;}
static inline int psa_hash_finish(psa_hash_operation_t*h,void*p,size_t n,size_t*out){(void)n;*out=32;return SHA256_Final(p,h)?0:-1;}
static inline int psa_hash_abort(psa_hash_operation_t*h){(void)h;return 0;}
"""
class Validation(unittest.TestCase):
 def test_full_hash_missing_untrusted_and_mid_hash_exit(self):
  self.assertTrue(FIXTURE.exists(),'Mandatory real WAD fixture unavailable')
  o=ROOT/'.hermes/cycle79/validation';o.mkdir(parents=True,exist_ok=True)
  stubs=dict(ui.STUBS);stubs['psa/crypto.h']=CRYPTO
  stubs['esp_timer.h']=stubs['esp_timer.h'].replace('return fake_us;','return fake_us+=50;')
  stubs['freertos/task.h']=stubs['freertos/task.h'].replace('static inline void vTaskDelay(int t){(void)t;}','extern unsigned delay_calls;extern int64_t fake_us;\nstatic inline void vTaskDelay(int t){delay_calls++;fake_us+=(int64_t)t*10000;}')
  for name,content in stubs.items():p=o/'stubs'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
  host=ui.HOST[:ui.HOST.index('int main(int argc')]
  host=host.replace('#include "doom_ui.c"','static char test_wad[512];\n#define WAD_PATH test_wad\n#include "doom_ui.c"',1)
  host+=r"""
unsigned test_updates,test_cancel_after,delay_calls;
void test_cancel(void){__atomic_store_n(&cancel,true,__ATOMIC_RELEASE);}
static void reset_validation(const char*path){snprintf(test_wad,sizeof(test_wad),"%s",path);cancel=false;test_updates=delay_calls=0;test_cancel_after=0;lock_tries=4;hash_bytes=hash_total=0;boot_ms=cooperate_ms=(uint32_t)(esp_timer_get_time()/1000);}
int main(int argc,char**argv){assert(argc==3);reset_validation(argv[1]);assert(validate_asset());assert(hash_bytes==hash_total);assert(hash_bytes>1024*1024);unsigned complete=hash_bytes,chunks=test_updates,yields=delay_calls;assert(yields>0&&yields<chunks/4);
 reset_validation(argv[1]);test_cancel_after=3;assert(!validate_asset());assert(cancel&&hash_bytes>0&&hash_bytes<hash_total);
 reset_validation("/nonexistent-cycle79-wad");assert(!validate_asset());assert(strstr(worker_status,"Missing WAD"));
 reset_validation(argv[2]);assert(!validate_asset());assert(strstr(worker_status,"Invalid/unsupported WAD"));assert(hash_bytes==hash_total);
 printf("PRODUCTION_VALIDATION bytes=%u full_sha_chunks=%u budget_yields=%u old_per_chunk_ticks=%u tick_ms=10 simulated_clock_only; mid-hash Exit, missing, altered rejection PASS\n",complete,chunks,yields,chunks);return 0;
}
"""
  (o/'host.c').write_text(host)
  altered=o/'altered.wad';data=bytearray(FIXTURE.read_bytes());data[1024]^=1;altered.write_bytes(data)
  lv=ui.LVGL;c=ui.COMP
  flags=['-std=gnu11','-O1','-g','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_16=1','-DLV_FONT_MONTSERRAT_12=1','-DLV_FONT_MONTSERRAT_18=1','-DLV_FONT_MONTSERRAT_20=1','-I'+str(lv),'-I'+str(o/'stubs'),'-I'+str(c/'include'),'-I'+str(c),'-I'+str(ROOT/'ESP32C5/main')]
  build=subprocess.run(['cc',*flags,str(o/'host.c'),str(c/'doom_contracts.c'),str(c/'selector_art.c'),*[str(p) for p in (lv/'src').rglob('*.c')],'-lm','-lcrypto','-o',str(o/'host')],capture_output=True,text=True)
  (o/'compile.log').write_text(build.stdout+build.stderr);self.assertEqual(build.returncode,0,build.stderr)
  run=subprocess.run([str(o/'host'),str(FIXTURE),str(altered)],capture_output=True,text=True,timeout=60)
  (o/'runtime.log').write_text(run.stdout+run.stderr);self.assertEqual(run.returncode,0,run.stdout+run.stderr);print(run.stdout)
if __name__=='__main__':unittest.main(verbosity=2)
