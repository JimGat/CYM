// Platform-only hooks: this file is NOT rebound. No global operator override.
#include "cym_zx_alloc.h"
#include <atomic>
#include <cstdlib>
#include <cstring>
#include <cstddef>
#include <cstdint>
#include <new>
#ifdef ESP_PLATFORM
#include "esp_heap_caps.h"
#include "esp_attr.h"
#include "esp_log.h"
#endif
namespace {
// Plain compatible pointers: imported stdlib methods may allocate/free outside
// the private archives. Never prepend headers to a pointer passed across ABI.
struct Entry {void *pointer;size_t size;};
#ifdef ESP_PLATFORM
EXT_RAM_BSS_ATTR Entry entries[512];
#else
Entry entries[512];
#endif
std::atomic<size_t> foreign_frees{0};
std::atomic<size_t> live{0},peak{0},calls{0},failures{0};
#ifndef ESP_PLATFORM
std::atomic<long> fail_after{-1};std::atomic<int> fault_kind{0};
#endif
void *allocate(size_t size) {
 calls.fetch_add(1);
#ifndef ESP_PLATFORM
 long n=fail_after.load();if(n>=0){if(n==0){failures.fetch_add(1);return nullptr;}fail_after.fetch_sub(1);}
#endif
 Entry *slot=nullptr;
 for(auto &e:entries)if(!e.pointer){slot=&e;break;}
 if(!slot){failures.fetch_add(1);return nullptr;}
#ifdef ESP_PLATFORM
 void *p=heap_caps_malloc(size?size:1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
#else
 void *p=std::malloc(size?size:1);
#endif
 if(!p){failures.fetch_add(1);return nullptr;}
 *slot={p,size};size_t nlive=live.fetch_add(size)+size,old=peak.load();
 while(nlive>old&&!peak.compare_exchange_weak(old,nlive)){}return p;
}
void release(void *p) noexcept {
 if(!p)return;
 bool found=false;
 for(auto &e:entries)if(e.pointer==p){live.fetch_sub(e.size);e={};found=true;break;}
 if(!found)foreign_frees.fetch_add(1);
 std::free(p); // Compatible with both heap_caps_malloc and runtime malloc.

}
}
extern "C" cym_zx_alloc_stats_t cym_zx_alloc_stats(void){return {live.load(),peak.load(),calls.load(),failures.load(),foreign_frees.load()};}
#ifndef ESP_PLATFORM
extern "C" void cym_zx_test_fail_after(long n,int k){fault_kind=k;fail_after=n;}
#endif
extern "C" void *cym_zx_malloc(size_t n){return allocate(n);}
extern "C" void cym_zx_free(void *p){release(p);}
extern "C" void *cym_zx_calloc(size_t n,size_t s){if(s&&n>SIZE_MAX/s)return nullptr;void *p=allocate(n*s);if(p)std::memset(p,0,n*s);return p;}
extern "C" void *cym_zx_realloc(void *p,size_t n) {
 if(!n){release(p);return nullptr;}void *v=allocate(n);
 if(v&&p){size_t old=0;for(auto &e:entries)if(e.pointer==p){old=e.size;break;}
  // Only imported C realloc users may reach this hook; reject unknown pointers.
  if(!old){release(v);return nullptr;}
  std::memcpy(v,p,old<n?old:n);release(p);}return v;
}
extern "C" void *cym_zx_new(size_t n) {
 void *p=allocate(n?n:1);if(p)return p;
#ifndef ESP_PLATFORM
 if(fault_kind.load())throw 1;
#endif
 throw std::bad_alloc();
}
extern "C" void *cym_zx_new_nothrow(size_t n,const std::nothrow_t&) noexcept {try{return cym_zx_new(n);}catch(...){return nullptr;}}
extern "C" void cym_zx_delete(void *p) noexcept {release(p);}
extern "C" void cym_zx_delete_sized(void *p,size_t) noexcept {release(p);}
extern "C" void cym_zx_delete_nothrow(void *p,const std::nothrow_t&) noexcept {release(p);}
// Standard toolchain/IDF ABI guards retained; no custom lock/unwind protocol.
// QR/GF metadata lives until process exit: no default-heap destructor registry.
// Native has the same lifetime; the OS reclaims persistent tables at exit.
extern "C" int cym_zx_atexit(void (*)(void*),void*,void*) noexcept {return 0;}

#ifdef ESP_PLATFORM
// The copied libsupc++ eh_alloc.o alone uses this hook, including its unchanged
// 2048-byte emergency reserve. Do NOT use the bounded decoder side table: an
// exhausted decoder allocator must still be able to throw/catch bad_alloc.
// Constructors run after PSRAM/cache init; exceptions themselves execute in
// flash and are cache-on only. Standard generic free accepts these pointers.
extern "C" void *cym_zx_eh_malloc(size_t n) noexcept {
 // First invocation is the startup reserve, before scheduler/other CPUs.
 static bool reported=false;
 if(!reported) {
  reported=true;
  ESP_EARLY_LOGI("qr_eh", "stage=arena_before bytes=%u internal_free=%u internal_largest=%u DMA_free=%u DMA_largest=%u",
   (unsigned)n,(unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
   (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
   (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA),
   (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA));
  void *p=heap_caps_malloc(n?n:1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
  ESP_EARLY_LOGI("qr_eh", "stage=arena_after success=%d internal_free=%u internal_largest=%u DMA_free=%u DMA_largest=%u",
   p!=nullptr,(unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
   (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
   (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA),
   (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA));
  return p;
 }
 return heap_caps_malloc(n?n:1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
}
#endif
