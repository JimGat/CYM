#!/usr/bin/env python3
"""Production USB worker + settings + installed IDF linenoise, with distinct TLS/global streams."""
from pathlib import Path
import ast,re,os,subprocess
R=Path(__file__).resolve().parents[1]
D=Path(os.environ['CYM_TEST_OUT'])/'stream';D.mkdir(parents=True,exist_ok=True)
IDF=Path('/home/dev/esp/esp-idf/components/console')
COMPAT=int(os.environ.get('CYM_CONSOLE_COMPAT','1'))
SECONDARY=int(os.environ.get('CYM_CONSOLE_SECONDARY','1'))
def literal(path,name):
 for n in ast.parse(path.read_text()).body:
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets):return ast.literal_eval(n.value)
def strip(s):return re.sub(r'^#include .*$', '',s,flags=re.M)
stub=literal(R/'tests/run_targeted_console_host.py','stub')
stub=stub.replace('static bool cym_debug_enabled(void){return false;}','').replace('static unsigned cym_debug_generation(void){return 0;}','').replace('static int cym_debug_command(int n,char **a){(void)n;(void)a;return 0;}','')
stub=stub.replace('static void vTaskDelay(unsigned n){(void)n;}','static void vTaskDelay(unsigned n);')
a=stub.index('static FILE *mock_fopen');b=stub.index('static int esp_console_init',a)
stub=stub[:a]+stub[b:]
a=stub.index('static void linenoiseSetDumbMode');b=stub.index('static void usb_serial_jtag_vfs_set_rx_line_endings',a)
stub=stub[:a]+stub[b:]
stub=stub.replace('(void)f;(void)n;(void)a;assert(depth==4096', 'worker=f;(void)n;(void)a;assert(depth==4096')
prefix=r"""
#include <unistd.h>
#include <fcntl.h>
#include <setjmp.h>
#include <pthread.h>
#include <ctype.h>
#include "linenoise.h"
static void (*worker)(void*);
"""
extra=r"""
__thread FILE *tls_stdin,*tls_stdout,*tls_stderr;
static FILE *global_in,*global_out,*global_err,*usb_in,*usb_out;
static jmp_buf done;
static int delays,reads,wrong_fd,commands,scenario,pos,event,save_fail,connected=1;
static const char *input;
static bool usb_serial_jtag_is_connected(void){return connected;}
static void vTaskDelay(unsigned n){assert(n>=20&&n<=100);if(++delays>300)longjmp(done,1);if(!connected){connected=1;}}
ssize_t host_read(int fd,void *p,size_t n){
 assert(n==1);reads++;
 if(fd!=fileno(usb_in)){wrong_fd++;errno=EAGAIN;return -1;}
 if(scenario==0){errno=EAGAIN;return -1;}
 if(scenario==5 && pos==6 && event++<8){errno=event%2?EINTR:EAGAIN;return -1;}
 if(scenario==6){errno=EIO;return -1;}
 if(scenario==1 && event++<6){if(event%2){errno=EAGAIN;return -1;}return 0;}
 if(scenario==2 && pos==8 && event==0){event++;connected=0;return -1;}
 if(scenario==3 && pos==8 && event==0){event++;errno=EIO;return -1;}
 if(!input[pos]){errno=EAGAIN;return -1;}
 char c=input[pos++];*(char*)p=c=='\r'?'\n':c;return 1;
}
static FILE *mock_fopen(const char *p,const char *m){
 assert(!strcmp(p,CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG?"/dev/secondary":"/dev/usbserjtag"));
 FILE *f=tmpfile();assert(f);if(*m=='r')usb_in=f;else usb_out=f;opened++;return f;
}
#define fopen mock_fopen
static int mock_fclose(FILE*f){closed++;return fclose(f);}
#define fclose mock_fclose
#define read host_read
static int mock_fcntl(int fd,int cmd,...){assert(fd==fileno(usb_in));return cmd==F_GETFL?0:0;}
#define fcntl mock_fcntl
#define ESP_ERR_NVS_NOT_FOUND 9
#define ESP_ERR_TIMEOUT 10
#define NVS_READONLY 0
#define NVS_READWRITE 1
#define pdTRUE 1
typedef unsigned nvs_handle_t;typedef void *SemaphoreHandle_t;
static int stored,staged;
static SemaphoreHandle_t xSemaphoreCreateMutex(void){return &stored;}
static int xSemaphoreTake(void*h,unsigned t){assert(h&&t==250);return 1;}
static void xSemaphoreGive(void*h){assert(h);}
static int nvs_open(const char*n,int m,unsigned*h){assert(!strcmp(n,"settings"));(void)m;*h=42;return 0;}
static int nvs_get_u8(unsigned h,const char*k,uint8_t*v){assert(h==42&&!strcmp(k,"debug_diag"));*v=stored;return 0;}
static int nvs_set_u8(unsigned h,const char*k,uint8_t v){assert(h==42&&!strcmp(k,"debug_diag"));staged=v;return 0;}
static int nvs_commit(unsigned h){assert(h==42);if(save_fail)return ESP_FAIL;stored=staged;return 0;}
static void nvs_close(unsigned h){assert(h==42);}
"""
settings=strip((R/'ESP32C5/main/debug_settings.c').read_text())
header=R/'ESP32C5/main/debug_console_stdio.h'
if header.exists():extra+='\n'+strip(header.read_text())+'\n'
extra+='\n'+settings+'\n'
extra+=r"""
#include "/home/dev/esp/esp-idf/components/console/split_argv.c"
static int esp_console_run(char*l,int*r){char *a[32];size_t n=esp_console_split_argv(l,a,32);if(!n)return ESP_ERR_INVALID_ARG;commands++;if(strcmp(a[0],"debug"))return ESP_ERR_NOT_FOUND;*r=cym_debug_command(n,a);return 0;}
"""
source=strip((R/'ESP32C5/main/debug_console.c').read_text())
main=r"""
static void *other(void*p){(void)p;assert(stdin==global_in&&stdout==global_out&&stderr==global_err);assert(tls_stdout==NULL);return NULL;}
int main(int argc,char**argv){assert(argc==2);scenario=atoi(argv[1]);
 global_in=stdin;global_out=stdout;global_err=stderr;tls_stdin=stdin;tls_stdout=stdout;tls_stderr=stderr;
 assert(cym_debug_load()==0);assert(cym_debug_console_start()==0&&worker);
 input=scenario==2||scenario==3?"debug on\ndebug status\n":"\n\bdebug statuX\bs\r\ndebug on\ndebug status\ndebug off\n";
 if(scenario==7)input="debug invalid\nmissing\ndebug query\n";
 if(scenario==4){input="debug on\n";save_fail=1;}
 linenoiseSetDumbMode(1);linenoiseSetMaxLineLen(100);
 if(!setjmp(done))worker(NULL);
 FILE *after_in=stdin,*after_out=stdout,*after_err=stderr;stdin=global_in;stdout=global_out;stderr=global_err;
 fflush(usb_out);fseek(usb_out,0,SEEK_END);long len=ftell(usb_out);rewind(usb_out);char *text=calloc(len+1,1);assert(fread(text,1,len,usb_out)==(size_t)len);
 int prompts=0;for(char*p=text;(p=strstr(p,"debug> "));p+=7)prompts++;
 fprintf(global_out,"scenario=%d reads=%d wrong_fd=%d commands=%d prompts=%d delays=%d global_changed=%d\n",scenario,reads,wrong_fd,commands,prompts,delays,after_in!=global_in||after_out!=global_out||after_err!=global_err);fflush(global_out);
 assert(wrong_fd==0);assert(after_in==global_in&&after_out==global_out&&after_err==global_err);
 pthread_t t;assert(!pthread_create(&t,NULL,other,NULL));assert(!pthread_join(t,NULL));
 if(scenario==0||scenario==6){assert(commands==0&&prompts<=1);}
 else if(scenario==7){assert(commands==3&&!stored&&strstr(text,"Usage: debug")&&strstr(text,"Unrecognized command")&&strstr(text,"Debug OFF"));}
 else if(scenario==2||scenario==3){assert(commands==1&&!stored);assert(strstr(text,"Debug OFF"));}
 else if(scenario==4){assert(commands==1&&!stored&&strstr(text,"Debug persistence failed:"));}
 else {assert(commands==4&&!stored);assert(strstr(text,"Debug OFF")&&strstr(text,"Debug ON persisted; applied immediately")&&strstr(text,"Debug ON\n")&&strstr(text,"Debug OFF persisted; applied immediately"));}
 free(text);puts("PASS actual production worker/IDF linenoise/TLS/output/idle/recovery");return 0;
}
"""
(D/'worker.c').write_text(prefix+stub+extra+source+main)
(D/'sdkconfig.h').write_text(f'#define CONFIG_IDF_TARGET_LINUX 1\n#define CONFIG_LIBC_PICOLIBC 1\n#define CONFIG_LIBC_PICOLIBC_NEWLIB_COMPATIBILITY {COMPAT}\n')
(D/'stdio-bufio.h').write_text('/* Host uses glibc FILE; Linux linenoise needs no bufio internals. */\n')
flags=['cc','-D_GNU_SOURCE','-std=gnu11','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(D),'-I'+str(IDF/'linenoise'),'-DCONFIG_LIBC_PICOLIBC=1',f'-DCONFIG_LIBC_PICOLIBC_NEWLIB_COMPATIBILITY={COMPAT}',f'-DCONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG={SECONDARY}']
subprocess.run(flags+['-Dread=host_read','-include',str(IDF/'private_include/console_stdio_private.h'),'-c',str(IDF/'linenoise/linenoise.c'),'-o',str(D/'linenoise.o')],check=True)
subprocess.run(flags+[str(D/'worker.c'),str(D/'linenoise.o'),'-pthread','-o',str(D/'worker')],check=True)
failed=0
for scenario in range(8):
 p=subprocess.run([str(D/'worker'),str(scenario)],env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
 failed+=p.returncode!=0
print('COMPAT',COMPAT,'SECONDARY',SECONDARY,'SCENARIOS',8,'FAILED',failed,flush=True)
raise SystemExit(bool(failed))
