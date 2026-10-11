from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'ESP32C5/components/cym_doom'
class StorageGate(unittest.TestCase):
 def test_real_admission_wrappers_fault_and_race(self):
  out=ROOT/'.hermes/doom-prototype/storage-host';out.mkdir(parents=True,exist_ok=True)
  stub=out/'freertos/FreeRTOS.h';stub.parent.mkdir(exist_ok=True)
  stub.write_text('#include <pthread.h>\ntypedef pthread_mutex_t portMUX_TYPE;\n#define portMUX_INITIALIZER_UNLOCKED PTHREAD_MUTEX_INITIALIZER\n#define portENTER_CRITICAL(p) pthread_mutex_lock(p)\n#define portEXIT_CRITICAL(p) pthread_mutex_unlock(p)\n')
  code=r"""
#include "storage_gate.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
FILE *__wrap_fopen(const char*,const char*);int __wrap_fclose(FILE*);
int __wrap_open(const char*,int,...);int __wrap_close(int);
int __wrap_mkdir(const char*,mode_t);int __wrap_unlink(const char*);int __wrap_remove(const char*);int __wrap_rename(const char*,const char*);
static bool fail_open,fail_close;
static atomic_bool mutator_live,release_mutator;
FILE *__real_fopen(const char*p,const char*m){(void)p;(void)m;return fail_open?NULL:(FILE*)malloc(1);}
int __real_fclose(FILE*f){if(fail_close)return EOF;free(f);return 0;}
int __real_open(const char*p,int f,...){(void)p;(void)f;return fail_open?-1:7;}
int __real_close(int fd){(void)fd;return fail_close?-1:0;}
int __real_mkdir(const char*p,mode_t m){(void)p;(void)m;atomic_store(&mutator_live,true);while(!atomic_load(&release_mutator)){}return 0;}
int __real_unlink(const char*p){(void)p;return 0;}
int __real_rmdir(const char*p){(void)p;return 0;}
int __real_remove(const char*p){(void)p;return 0;}
int __real_rename(const char*a,const char*b){(void)a;(void)b;return 0;}
static void *directory_worker(void*p){(void)p;assert(__wrap_mkdir("/sdcard/new",0775)==0);return NULL;}
static void *racer(void*p){(void)p;for(int i=0;i<10000;i++){FILE*f=__wrap_fopen("/sdcard/race","wb");if(f)assert(__wrap_fclose(f)==0);}return NULL;}
int main(void){
 assert(storage_gate_active()==0);FILE*f=__wrap_fopen("/sdcard/a","wb");assert(f&&storage_gate_active()==1);
 assert(!storage_gate_freeze());assert(!__wrap_fopen("/sdcard/b","wb")&&errno==EBUSY);assert(storage_gate_active()==1);
 assert(__wrap_unlink("/sdcard/a")==-1&&errno==EBUSY);assert(__wrap_rename("/other","/sdcard/a")==-1);
 assert(__wrap_fclose(f)==0&&storage_gate_active()==0);assert(storage_gate_freeze());
 f=__wrap_fopen("/sdcardx/not-sd","wb");assert(f&&storage_gate_active()==0);assert(__wrap_fclose(f)==0);
 storage_gate_thaw();fail_open=true;assert(!__wrap_fopen("/sdcard/a","wb")&&storage_gate_active()==0);assert(__wrap_open("/sdcard/a",O_RDONLY)==-1&&storage_gate_active()==0);fail_open=false;
 int fd=__wrap_open("/sdcard/a",O_CREAT|O_WRONLY,0644);assert(fd==7&&storage_gate_active()==1);assert(!storage_gate_freeze());assert(__wrap_close(fd)==0&&storage_gate_active()==0);storage_gate_thaw();
 FILE*handles[32];for(int i=0;i<32;i++)handles[i]=__wrap_fopen("/sdcard/table","rb");assert(storage_gate_active()==32);assert(!__wrap_fopen("/sdcard/overflow","wb")&&errno==EMFILE);for(int i=0;i<32;i++)assert(__wrap_fclose(handles[i])==0);assert(storage_gate_active()==0);
 pthread_t thread;pthread_create(&thread,NULL,directory_worker,NULL);while(!atomic_load(&mutator_live)){}assert(!storage_gate_freeze());atomic_store(&release_mutator,true);pthread_join(thread,NULL);assert(storage_gate_active()==0);storage_gate_thaw();
 pthread_create(&thread,NULL,racer,NULL);for(int i=0;i<10000;i++){(void)storage_gate_freeze();storage_gate_thaw();}pthread_join(thread,NULL);assert(storage_gate_active()==0);
 f=__wrap_fopen("/sdcard/fault","wb");fail_close=true;assert(__wrap_fclose(f)==EOF);assert(storage_gate_active()==1&&!storage_gate_freeze());fail_close=false;assert(__wrap_fclose(f)==0);assert(storage_gate_active()==0);
 puts("production SD admission: freeze/new-open race, bounded32 handles, real-close retention, mutator/file/FD faults, namespace PASS");return 0;
}
"""
  (out/'cases.c').write_text(code)
  r=subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-pthread','-I'+str(out),'-I'+str(COMP/'include'),str(out/'cases.c'),str(COMP/'storage_gate.c'),str(COMP/'storage_gate_fs.c'),'-o',str(out/'cases')],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  r=subprocess.run([str(out/'cases')],capture_output=True,text=True,timeout=30);(out/'runtime.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
