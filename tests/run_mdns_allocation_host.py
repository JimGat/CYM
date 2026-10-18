#!/usr/bin/env python3
# Native production-overlay regression; SDK boundaries and fragmentation are modeled.
from pathlib import Path
import ast,re,subprocess,os,json
R=Path(os.environ.get('CYM_REPO','/home/dev/projects/CYM-NM28C5-jarvis-ws35-docs'));E=Path(os.environ['CYM_TEST_OUT']);E.mkdir(parents=True,exist_ok=True);D=E/'pressure';D.mkdir(exist_ok=True)
U=R/'ESP32C5/managed_components/espressif__mdns'
subprocess.run(['python3',str(R/'scripts/mdns-overlay.py'),str(U),str(E/'generated')],check=True)
s=Path(os.environ.get('CYM_MDNS_SOURCE',str(E/'generated/mdns_service.c'))).read_text()
def fn(name):
 m=re.search(r'^(?:static )?(?:esp_err_t|bool|void) '+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
tree=ast.parse((R/'tests/run_targeted_mdns_host.py').read_text())
node=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='extra' for t in n.targets))
code=eval(compile(ast.Expression(node),'<existing production test>','eval'),{'fn':fn})
code=code[:code.index('int main(void)')]
code=re.sub(r'static int service_task_start\(void\)\{[^\n]*\}', '',code)
code=code.replace('static int mdns_priv_responder_init(void){if(fail==1)return 1;server=true;return 0;}', 'esp_err_t mdns_priv_responder_init(void);')
code=code.replace('static void mdns_priv_responder_free(void){server=false;}', 'void mdns_priv_responder_free(void);')
code=code.replace('static int service_task_stop(void){return stop_timeout?ESP_ERR_TIMEOUT:0;}', 'static void *s_service_task_handle; static int service_task_stop(void){if(stop_timeout)return ESP_ERR_TIMEOUT;s_service_task_handle=NULL;return 0;}')
code=code.replace('static void mdns_mem_task_free(void*p){if(p){stack_freed++;free(p);}}','')
code=code.replace('static void vSemaphoreDelete(void*p){assert(p);}', 'static void vSemaphoreDelete(void*p);')
code=code.replace('static void *xQueueCreate(int n,int z){(void)n;(void)z;return fail==2?NULL:(void*)1;}', 'static void *xQueueCreate(int n,int z);')
code=code.replace('static void vQueueDelete(void*q){assert(q&&!s_action_queue);queue_deleted++;}', 'static void vQueueDelete(void*q);')
ix=code.index('esp_err_t mdns_free_wait(void);');prefix=code[:ix];production=code[ix:]
stub=r"""
#include <stdint.h>
#include <string.h>
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
#define MALLOC_CAP_SPIRAM 4
#define CONFIG_MDNS_MEMORY_CUSTOM_IMPL 0
#define CONFIG_MDNS_TASK_CREATE_FROM_INTERNAL 1
#define MDNS_SERVICE_STACK_DEPTH 4096
#define MDNS_TASK_PRIORITY 1
#define MDNS_TASK_AFFINITY 0
#define ESP_IDF_VERSION 0
#define ESP_IDF_VERSION_VAL(a,b,c) 1
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
#define ESP_RETURN_ON_FALSE(c,e,...) do{if(!(c))return(e);}while(0)
#define ESP_GOTO_ON_FALSE(c,e,l,...) do{if(!(c)){ret=(e);goto l;}}while(0)
#define ESP_GOTO_ON_ERROR(c,l,...) do{ret=(c);if(ret)goto l;}while(0)
typedef unsigned char StackType_t;typedef struct {char b[96];} StaticTask_t;
static void *s_service_task_handle;static int allocs,live,created,fault;static size_t big,small,psram,initial_big;
typedef struct {void*p;size_t n;int region;}rec_t;static rec_t rec[100];static int nr;
static void *heap_caps_malloc(size_t n,unsigned caps){
 allocs++;int region=0;size_t *space;
 if(caps&4){space=&psram;region=2;}else if(n==4096||allocs==1){space=&big;}else{space=&small;region=1;}
 if(n==4096)printf("STACK request=%zu caps=%u free=%zu largest=%zu\n",n,caps,big+small,big);
 if(*space<n||allocs==fault)return NULL;
 void *p=calloc(1,n);assert(p);*space-=n;rec[nr++]=(rec_t){p,n,region};live++;printf("ALLOC n=%zu caps=%u region=%d\n",n,caps,region);return p;
}
static void *heap_caps_calloc(size_t n,size_t z,unsigned c){return heap_caps_malloc(n*z,c);}
static void heap_caps_free(void*p){if(!p)return;for(int i=0;i<nr;i++)if(rec[i].p==p){size_t *space=rec[i].region==2?&psram:rec[i].region==1?&small:&big;*space+=rec[i].n;free(p);rec[i].p=NULL;live--;return;}assert(0);}
static void *xSemaphoreCreateBinary(void){return heap_caps_malloc(84,3);}
static void *xSemaphoreCreateMutex(void){return heap_caps_malloc(84,3);}
static void vSemaphoreDelete(void*p){heap_caps_free(p);}
static void *xQueueCreate(int n,int z){return heap_caps_malloc(84+n*z,3);}
static void vQueueDelete(void*p){heap_caps_free(p);}
static int tcb_fail,timer_error,netif_error;
static void *s_timer_handle;
typedef struct {void(*callback)(void*);void*arg;int dispatch_method;const char*name;} esp_timer_create_args_t;
#define ESP_TIMER_TASK 1
#define MDNS_TIMER_PERIOD_US 100
static void timer_cb(void*p){(void)p;}
static int esp_timer_create(const esp_timer_create_args_t*a,void**h){assert(a);if(timer_error)return timer_error;*h=(void*)1;return ESP_OK;}
static int esp_timer_start_periodic(void*h,int period){assert(h&&period);return ESP_OK;}
static void service_task(void*p){(void)p;}
static void *xTaskCreateStaticPinnedToCore(void(*f)(void*),const char*n,int d,void*a,int pri,void*stack,StaticTask_t*tcb,int core){assert(d==4096&&stack&&tcb);if(tcb_fail)return NULL;created++;return tcb;}
typedef void (*mdns_hostname_changed_cb_t)(void);typedef void mdns_srv_item_t;typedef void *SemaphoreHandle_t;
typedef struct mdns_host_item_t {const char*hostname;void*address_list;struct mdns_host_item_t*next;}mdns_host_item_t;
"""
resp=(E/'generated/mdns_responder.c').read_text();types=resp[resp.index('typedef struct mdns_hostname_changed_callback_s'):resp.index('static const char *TAG')]
stub+=types+'static mdns_server_t *s_server;\n'
stub+='static void free_delegated_hostnames(void){}\nstatic void free_hostname_changed_callbacks(void){}\n'
mem=re.sub(r'^#include .*$','',(E/'generated/mdns_mem_caps.c').read_text(),flags=re.M)
saved=s;s=resp;respfn=fn('mdns_priv_responder_init')+fn('mdns_priv_responder_free');s=saved
prefix=prefix.replace('return server;', 'return s_server != NULL;').replace('return fail==3?-1:0;', 'return netif_error;')
# Execute the production application hook too; only heap/SDK/log sinks are modeled.
saved=s;s=(R/'ESP32C5/main/main.c').read_text();hook=fn('cym_mdns_alloc_boundary');s=saved
stub += r"""
static int debug_on, samples, markers;
static const char *TAG="host";
static bool cym_debug_enabled(void){return debug_on;}
static size_t heap_caps_get_free_size(unsigned caps){assert(caps==3);samples++;return big+small;}
static size_t heap_caps_get_largest_free_block(unsigned caps){assert(caps==3);samples++;return big;}
static const char *esp_err_to_name(int e){return e==0?"ESP_OK":e==1?"ESP_ERR_NO_MEM":"ESP_FAIL";}
#define ESP_LOGW(tag,fmt,...) do{markers++;printf(fmt "\n",__VA_ARGS__);}while(0)
""" + hook + '\n#define CYM_MDNS_BOUNDARY(stage,phase,bytes,error) cym_mdns_alloc_boundary(stage,phase,bytes,error)\n'
# actual helper definitions must precede init and their own forward references
ix=prefix.index('static bool mdns_priv_is_server_init')
code=prefix[:ix]+stub+mem+respfn+prefix[ix:]+fn('start_timer')+fn('create_task_with_caps')+fn('service_task_start')+production
main=r"""
int main(int argc,char**argv){assert(argc==6);setbuf(stdout,NULL);
int high=atoi(argv[1]),success=atoi(argv[2]);fault=atoi(argv[3]);debug_on=atoi(argv[4]);int mode=atoi(argv[5]);
tcb_fail=mode==1;timer_error=mode==2?ESP_ERR_NO_MEM:0;netif_error=mode==3?ESP_ERR_NO_MEM:0;
initial_big=(high?4096:3072)+sizeof(mdns_server_t);big=initial_big;small=1830+84+84+16*sizeof(void*)+84;psram=100000;
int rc=mdns_init();printf("RESULT rc=%d live=%d created=%d responder_host=%zu\n",rc,live,created,sizeof(mdns_server_t));
if(success){assert(rc==ESP_OK&&created==1);}else{assert(rc==(tcb_fail?ESP_FAIL:ESP_ERR_NO_MEM)&&!created);}
assert(mdns_free_wait()==ESP_OK);mdns_priv_responder_free();mdns_priv_responder_free();
assert(!live&&!pcbs&&!s_action_queue&&!s_stack_buffer&&!s_service_semaphore&&!s_server);assert(big==initial_big);
assert(debug_on?(markers>0&&samples==2*markers):(!markers&&!samples));
/* Every failed allocation must permit a subsequent successful init/free. */
fault=0;tcb_fail=timer_error=netif_error=0;allocs=nr=created=0;big=4096+sizeof(mdns_server_t);initial_big=big;
assert(mdns_init()==ESP_OK&&created==1);assert(mdns_free_wait()==ESP_OK);assert(!live&&!s_server&&big==initial_big);
/* Exercise every generated data wrapper with successful and failed allocation. */
for(int f=0;f<2;f++){
 allocs=nr=0;fault=f?1:0;void*p=mdns_mem_calloc(2,8);assert(f?!p:!!p);mdns_mem_free(p);
 allocs=nr=0;fault=f?1:0;p=mdns_mem_strdup("abc");assert(f?!p:!!p);if(p)assert(!strcmp(p,"abc"));mdns_mem_free(p);
 allocs=nr=0;fault=f?1:0;p=mdns_mem_strndup("abcdef",3);assert(f?!p:!!p);if(p)assert(!strcmp(p,"abc"));mdns_mem_free(p);assert(!live);
}
return 0;}
"""
p=D/'pressure.c';p.write_text(code+main);records=[]
for placement in ['INTERNAL','SPIRAM']:
 exe=D/placement.lower();cmd=['cc','-D_GNU_SOURCE','-std=c11','-g','-fsanitize=address,undefined','-no-pie','-DCONFIG_MDNS_MEMORY_ALLOC_'+placement+'=1','-DCONFIG_MDNS_MEMORY_ALLOC_'+('SPIRAM' if placement=='INTERNAL' else 'INTERNAL')+'=0',str(p),'-o',str(exe)]
 x=subprocess.run(cmd,capture_output=True,text=True);(D/(placement+'-compile.log')).write_text(x.stdout+x.stderr);assert x.returncode==0,x.stderr
 for debug in [0,1]:
  for name,high,success,fault,mode in [('low-honest-no-mem',0,0,0,0),('high-success-control',1,1,0,0),('data-oom',1,0,1,0),('semaphore-oom',1,0,2,0),('queue-oom',1,0,3,0),('mutex-oom',1,0,4,0),('stack-oom',1,0,5,0),('static-tcb-create-fail',1,0,0,1),('timer-no-mem',1,0,0,2),('netif-no-mem',1,0,0,3)]:
   cmd=[str(exe),str(high),str(success),str(fault),str(debug),str(mode)];x=subprocess.run(cmd,capture_output=True,text=True);log=D/(placement+'-'+name+'-debug'+str(debug)+'.log');log.write_text(x.stdout+x.stderr)
   if debug:
    initial=x.stdout.split('RESULT')[0]
    for stage in ['responder-data','data-malloc']:
     assert 'stage='+stage+' phase=before' in initial and 'stage='+stage+' phase=after' in initial
    stage_by_fault={1:'data-malloc',2:'responder-semaphore',3:'action-queue',4:'service-mutex',5:'stack'}
    failed_stage=stage_by_fault.get(fault) or ('stack' if not high else 'static-tcb-task-create' if mode==1 else 'timer-create' if mode==2 else 'netif-init' if mode==3 else None)
    if failed_stage:
     line=next(l for l in initial.splitlines() if 'stage='+failed_stage+' phase=after' in l)
     assert 'rc='+('ESP_FAIL' if mode==1 else 'ESP_ERR_NO_MEM') in line,line
    assert 'stage=responder-data phase=before' in x.stdout
    if fault==2:assert 'stage=responder-semaphore phase=after bytes=0 rc=ESP_ERR_NO_MEM' in x.stdout
    if name=='low-honest-no-mem':assert 'stage=stack phase=before bytes=4096 rc=ESP_OK' in x.stdout and 'stage=stack phase=after bytes=4096 rc=ESP_ERR_NO_MEM' in x.stdout
   else:assert 'mDNS boundary' not in x.stdout
   records.append(dict(placement=placement,name=name,debug=debug,command=cmd,rc=x.returncode,log=str(log)));print(placement,name,debug,x.returncode,flush=True);assert x.returncode==0,log.read_text()
(E/'pressure-results.json').write_text(json.dumps(records,indent=2))
print('PASS',len(records),'production allocation/unwind/reinit/debug cases; native responder72 vs target36; SDK/allocator fixtures, not hardware')
