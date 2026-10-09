/* Private silent native embedding. The caller MUST be the sole engine worker.
 * No LVGL, ISR, asynchronous callback or foreign task may enter this module.
 * Full mutable engine state is captured before Create, restored after raw owned
 * resource reclamation. This includes function-local statics, not a hand-picked
 * list of globals. Linker boundaries are a mandatory build/link contract.
 * Host tests are evidence for headless engine lifetime, NOT hardware/UI proof.
 */
#include "doom_session.h"
#include "doom_contracts.h"
#include "doomgeneric.h"
#include "w_file.h"
#include "doomkeys.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <stdbool.h>
#include <time.h>
#include <sys/stat.h>
#ifdef ESP_PLATFORM
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
extern SemaphoreHandle_t sd_spi_mutex;
#endif
#ifdef ESP_PLATFORM
extern unsigned char _doom_init_start[], _doom_init_end[];
extern unsigned char _doom_zero_start[], _doom_zero_end[];
extern unsigned char _doom_common_start[], _doom_common_end[];
#else
extern unsigned char __doom_state_start[],__doom_state_end[];
#endif
void doom_engine_tables_init(void);
#define OWN_MAX 4096
static void **owned;
static size_t owned_n;
static FILE *files[16];
static unsigned file_n;
static void *state;
/* ASan poisons inter-global padding; snapshot intentionally includes that padding.
 * Volatile byte copies avoid treating section padding as an engine object access.
 * Engine itself remains fully ASan-instrumented. */
__attribute__((no_sanitize_address)) static void copy_state(void *dst,const void *src,size_t n){volatile unsigned char *d=dst;const volatile unsigned char *s=src;for(size_t i=0;i<n;i++)d[i]=s[i];}
static char wad_path[256],error_text[256];
static bool active,armed;
static jmp_buf *boundary;
static doom_frame_fn frame_fn;
static void *frame_ctx;
static uint16_t palette[256];
static doom_keys keys;
static unsigned desired_keys;
static bool stop_requested;
_Noreturn void doom_engine_fail(const char *);
void doom_session_request_stop(void){__atomic_store_n(&stop_requested,true,__ATOMIC_RELEASE);}
static void check_stop(void){if(__atomic_load_n(&stop_requested,__ATOMIC_ACQUIRE))doom_engine_fail("Exit requested");}
#ifdef ESP_PLATFORM
static TaskHandle_t owner;
static bool same_owner(void){return xTaskGetCurrentTaskHandle()==owner;}
#else
/* Host gate is deliberately single-threaded; no concurrent entry supported. */
static bool same_owner(void){return true;}
#endif
/* Fatal propagation is only reachable inside call_engine(), on its live stack.
 * No VFS mutex is held here: wrappers unlock before invoking this function.
 * Unexpected outside-boundary calls are an adapter programming defect and must
 * never be exposed as user input or called from an async callback.
 */
_Noreturn void doom_engine_fail(const char *message){
    snprintf(error_text,sizeof(error_text),"%s",message?message:"Engine fault");
    if(armed&&boundary&&same_owner())longjmp(*boundary,1);
#ifdef ESP_PLATFORM
    /* Contain a contract violation to its worker, never abort the CYM process.
     * This fallback is NOT join proof; adapter must not make this path reachable.
     */
    vTaskSuspend(NULL);
    for(;;)vTaskDelay(pdMS_TO_TICKS(1000));
#else
    fprintf(stderr,"BOUNDARY_CONTRACT_VIOLATION %s\n",error_text);_Exit(90);
#endif
}
_Noreturn void doom_engine_exit(int status){doom_engine_fail(status==0?"Engine requested Exit":"Engine fatal exit requested");}
#ifndef ESP_PLATFORM
static long test_fail_after=-1;
static unsigned test_alloc_count;
void doom_session_test_fail_after(long n){test_fail_after=n;test_alloc_count=0;}
#endif
static void *raw_alloc(size_t n){
#ifdef ESP_PLATFORM
    return heap_caps_malloc(n,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
#else
    return malloc(n);
#endif
}
void *doom_owned_malloc(size_t n){check_stop();
#ifndef ESP_PLATFORM
if(test_fail_after>=0&&(long)test_alloc_count++==test_fail_after)doom_engine_fail("Injected allocation failure");
#endif
if(!owned||owned_n==OWN_MAX)doom_engine_fail("Owned allocation registry full");void *p=raw_alloc(n?n:1);if(!p)doom_engine_fail("Insufficient memory during engine init/tick");owned[owned_n++]=p;return p;}
void *doom_owned_calloc(size_t n,size_t s){if(s&&n>SIZE_MAX/s)doom_engine_fail("Allocation overflow");size_t bytes=n*s;void *p=doom_owned_malloc(bytes);memset(p,0,bytes);return p;}
void doom_owned_free(void *p){if(!p)return;for(size_t i=0;i<owned_n;i++)if(owned[i]==p){free(p);owned[i]=owned[--owned_n];return;}doom_engine_fail("Unregistered engine free");}
void *doom_owned_realloc(void *p,size_t n){if(!p)return doom_owned_malloc(n);if(!n){doom_owned_free(p);return NULL;}for(size_t i=0;i<owned_n;i++)if(owned[i]==p){
#ifdef ESP_PLATFORM
void *q=heap_caps_realloc(p,n,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
#else
void *q=realloc(p,n);
#endif
if(!q)doom_engine_fail("Engine realloc failed");owned[i]=q;return q;}doom_engine_fail("Unregistered engine realloc");}
/* Every VFS operation unlocks transport BEFORE returning to the engine. */
static bool io_lock(void){
#ifdef ESP_PLATFORM
    return sd_spi_mutex&&xSemaphoreTake(sd_spi_mutex,pdMS_TO_TICKS(2000))==pdTRUE;
#else
    return true;
#endif
}
static void io_unlock(void){
#ifdef ESP_PLATFORM
    xSemaphoreGive(sd_spi_mutex);
#endif
}
FILE *doom_owned_fopen(const char *p,const char *mode){check_stop();if(!p||strcmp(p,wad_path)||(strcmp(mode,"rb")&&strcmp(mode,"r")))return NULL;if(file_n==16)doom_engine_fail("File registry full");if(!io_lock())doom_engine_fail("SD transport busy");FILE *f=fopen(p,mode);io_unlock();if(f)files[file_n++]=f;return f;}
int doom_owned_fclose(FILE *f){if(!f)return 0;for(unsigned i=0;i<file_n;i++)if(files[i]==f){if(!io_lock())doom_engine_fail("SD close transport busy");int rc=fclose(f);io_unlock();files[i]=files[--file_n];return rc;}doom_engine_fail("Unregistered engine file close");}
size_t doom_owned_fread(void *p,size_t s,size_t n,FILE *f){check_stop();if(s&&n>SIZE_MAX/s)doom_engine_fail("File read overflow");if(!io_lock())doom_engine_fail("SD read transport busy");size_t result=fread(p,s,n,f);io_unlock();return result;}
int doom_owned_fseek(FILE *f,long off,int whence){check_stop();if(!io_lock())doom_engine_fail("SD seek transport busy");int rc=fseek(f,off,whence);io_unlock();return rc;}
long doom_owned_ftell(FILE *f){if(!io_lock())doom_engine_fail("SD tell transport busy");long result=ftell(f);io_unlock();return result;}
int doom_owned_forbidden(const char *p){(void)p;doom_engine_fail("Host shell/SD write disabled in prototype");}
int doom_owned_rename(const char *p,const char *q){(void)q;return doom_owned_forbidden(p);}
char *doom_owned_getenv(const char *name){(void)name;return NULL;}
static int call_engine(void (*fn)(void)){jmp_buf stack_boundary;if(armed||!same_owner())return -1;boundary=&stack_boundary;armed=true;int failed=setjmp(stack_boundary);if(!failed)fn();armed=false;boundary=NULL;return failed?-1:0;}
void doom_session_set_frame(doom_frame_fn fn,void *ctx){if(!active){frame_fn=fn;frame_ctx=ctx;}}
size_t doom_session_state_bytes(void){
#ifdef ESP_PLATFORM
return (size_t)(_doom_init_end-_doom_init_start)+(size_t)(_doom_zero_end-_doom_zero_start)+(size_t)(_doom_common_end-_doom_common_start);
#else
return (size_t)(__doom_state_end-__doom_state_start);
#endif
}
static void snapshot_state(bool restore){
#ifdef ESP_PLATFORM
size_t n=(size_t)(_doom_init_end-_doom_init_start);
size_t z=(size_t)(_doom_zero_end-_doom_zero_start);
if(restore){copy_state(_doom_init_start,state,n);copy_state(_doom_zero_start,(unsigned char *)state+n,z);copy_state(_doom_common_start,(unsigned char *)state+n+z,(size_t)(_doom_common_end-_doom_common_start));}
else{copy_state(state,_doom_init_start,n);copy_state((unsigned char *)state+n,_doom_zero_start,z);copy_state((unsigned char *)state+n+z,_doom_common_start,(size_t)(_doom_common_end-_doom_common_start));}
#else
if(restore)copy_state(__doom_state_start,state,doom_session_state_bytes());
else copy_state(state,__doom_state_start,doom_session_state_bytes());
#endif
}
size_t doom_session_owned(void){return owned_n+file_n;}
const char *doom_session_error(void){return error_text;}
/* Stop must run on the same worker, OUTSIDE a fatal boundary. The task-level
 * caller must report joined only after this returns. No upstream teardown is
 * invoked on partially initialized globals, and no atexit callback is called.
 */
int doom_session_stop(void){if(armed||!same_owner())return -1;while(file_n){FILE *f=files[file_n-1];if(!io_lock()){snprintf(error_text,sizeof(error_text),"SD cleanup busy - ownership retained");return -1;}fclose(f);io_unlock();--file_n;}
while(owned_n)free(owned[--owned_n]);free(owned);owned=NULL;if(state){snapshot_state(true);free(state);state=NULL;}active=false;memset(&keys,0,sizeof(keys));desired_keys=0;return 0;}
static void create(void){static char *argv[]={"cym-doom","-iwad",wad_path,"-nosound","-nomusic","-warp","1","1",NULL};doom_engine_tables_init();doomgeneric_Create(8,argv);}
int doom_session_start(const char *path){if(active||armed||!path||strlen(path)>=sizeof(wad_path))return -1;
#ifdef ESP_PLATFORM
owner=xTaskGetCurrentTaskHandle();
#endif
stop_requested=false;error_text[0]=0;snprintf(wad_path,sizeof(wad_path),"%s",path);size_t bytes=doom_session_state_bytes();if(!bytes){snprintf(error_text,sizeof(error_text),"Missing engine state linker region");return -1;}state=raw_alloc(bytes);owned=raw_alloc(OWN_MAX*sizeof(*owned));if(!state||!owned){free(state);state=NULL;free(owned);owned=NULL;snprintf(error_text,sizeof(error_text),"No memory for engine ownership/reset state");return -1;}snapshot_state(false);owned_n=file_n=0;active=true;memset(&keys,0,sizeof(keys));desired_keys=0;int rc=call_engine(create);if(rc)doom_session_stop();return rc;}
int doom_session_tick(void){if(!active)return -1;return call_engine(doomgeneric_Tick);}
void doom_session_set_keys(unsigned mask){__atomic_store_n(&desired_keys,mask,__ATOMIC_RELEASE);}
void DG_Init(void){memset(palette,0,sizeof(palette));}
void DG_DrawFrame(void){check_stop();if(frame_fn)frame_fn(DG_ScreenBuffer,frame_ctx);}
void DG_SleepMs(uint32_t ms){check_stop();
#ifdef ESP_PLATFORM
vTaskDelay(pdMS_TO_TICKS(ms?ms:1));
#else
struct timespec t={.tv_sec=ms/1000,.tv_nsec=(long)(ms%1000)*1000000};nanosleep(&t,NULL);
#endif
}
uint32_t DG_GetTicksMs(void){
#ifdef ESP_PLATFORM
return (uint32_t)(esp_timer_get_time()/1000);
#else
struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint32_t)((uint64_t)t.tv_sec*1000+t.tv_nsec/1000000);
#endif
}
int DG_GetKey(int *pressed,unsigned char *key){unsigned bit;bool down;static const unsigned char map[]={KEY_LEFTARROW,KEY_UPARROW,KEY_RIGHTARROW,KEY_DOWNARROW,KEY_FIRE,KEY_USE,KEY_ESCAPE,KEY_ENTER,KEY_ESCAPE};doom_keys_set(&keys,__atomic_load_n(&desired_keys,__ATOMIC_ACQUIRE));if(!doom_keys_next(&keys,&bit,&down))return 0;unsigned i=0;while((1u<<i)!=bit)i++;*pressed=down;*key=map[i];return 1;}
void DG_SetWindowTitle(const char *title){printf("[CYM_DOOM] TITLE %s\n",title);}
void DG_PaletteLoad(const void *data){const uint8_t *p=data;for(unsigned i=0;i<256;i++)palette[i]=(uint16_t)(((p[i*3]>>3)<<11)|((p[i*3+1]>>2)<<5)|(p[i*3+2]>>3));}
uint16_t DG_PaletteColor565(uint8_t i){return palette[i];}
uint16_t doom_session_color565(uint8_t i){return palette[i];}
int DG_FileExists(const char *path){if(strcmp(path,wad_path))return 0;if(!io_lock())doom_engine_fail("SD stat transport busy");struct stat s;int rc=stat(path,&s);io_unlock();return rc==0;}
void *DG_FileOpen(const char *p){return doom_owned_fopen(p,"rb");}
void DG_FileClose(void *p){if(p)doom_owned_fclose(p);}
size_t DG_FileRead(void *f,void *buf,size_t n){return doom_owned_fread(buf,1,n,f);}
int DG_FileSeek(void *f,unsigned off){return doom_owned_fseek(f,off,SEEK_SET)==0;}
unsigned DG_FileSize(void *f){long pos=doom_owned_ftell(f);if(doom_owned_fseek(f,0,SEEK_END))return 0;long size=doom_owned_ftell(f);doom_owned_fseek(f,pos,SEEK_SET);return size<0||size>INT32_MAX?0:(unsigned)size;}
typedef struct {wad_file_t wad;FILE *f;} native_wad;
extern wad_file_class_t esp32_wad_file;
static wad_file_t *wad_open(char *path){FILE *f=doom_owned_fopen(path,"rb");if(!f)return NULL;native_wad *w=doom_owned_calloc(1,sizeof(*w));w->f=f;w->wad.file_class=&esp32_wad_file;w->wad.length=DG_FileSize(f);return &w->wad;}
static void wad_close(wad_file_t *p){native_wad *w=(native_wad *)p;doom_owned_fclose(w->f);doom_owned_free(w);}
static size_t wad_read(wad_file_t *p,unsigned off,void *buf,size_t n){native_wad *w=(native_wad *)p;if(off>w->wad.length||n>w->wad.length-off)return 0;if(doom_owned_fseek(w->f,off,SEEK_SET))return 0;return doom_owned_fread(buf,1,n,w->f);}
wad_file_class_t esp32_wad_file={wad_open,wad_close,wad_read};
