#pragma once
/* Task-context, one-shot startup checkpoints. Never call under a bus lock.
 * No owned buffers, allocation hooks, per-successful-read logs or ISR work. */
#include "debug_gate.h"
#include <stddef.h>
#if defined(ESP_PLATFORM) || defined(DOOM_STARTUP_DIAG_HOST)
#ifndef DOOM_STARTUP_DIAG_HOST
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#endif
static inline void doom_startup_diag(const char *phase,int result,TaskHandle_t audio)
{
 if(!cym_debug_enabled())return;
 size_t fi=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
 size_t li=heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
 /* Match sdmmc allocate_dma_buf's exact MALLOC_CAP_DMA request. */
 size_t fd=heap_caps_get_free_size(MALLOC_CAP_DMA);
 size_t ld=heap_caps_get_largest_free_block(MALLOC_CAP_DMA);
 size_t fp=heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
 size_t lp=heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
 unsigned long current=(unsigned long)uxTaskGetStackHighWaterMark(NULL);
 unsigned long pcm=audio?(unsigned long)uxTaskGetStackHighWaterMark(audio):0;
 ESP_LOGI("CYM_DOOM","STARTUP_MEMORY phase=%s result=%d free_internal=%lu largest_internal=%lu free_dma=%lu largest_dma=%lu free_psram=%lu largest_psram=%lu stack_current=%lu stack_audio=%lu",phase,result,(unsigned long)fi,(unsigned long)li,(unsigned long)fd,(unsigned long)ld,(unsigned long)fp,(unsigned long)lp,current,pcm);
}
static inline void doom_read_diag(unsigned *count,size_t size,size_t requested,size_t returned,int error,int eof,int saved_errno)
{
 if(!size||returned==requested||!cym_debug_enabled()||*count>=4)return;
 ++*count;
 ESP_LOGI("CYM_DOOM","WAD_READ_SHORT requested_items=%lu returned_items=%lu item_size=%lu requested_bytes=%lu returned_bytes=%lu ferror=%d feof=%d errno=%d",(unsigned long)requested,(unsigned long)returned,(unsigned long)size,(unsigned long)(size*requested),(unsigned long)(size*returned),error,eof,saved_errno);
 doom_startup_diag("WAD_READ_MEMORY",saved_errno,NULL);
}
static inline void doom_seek_diag(unsigned *count,long offset,int whence,int result,int saved_errno)
{
 if(!result||!cym_debug_enabled()||*count>=4)return;
 ++*count;
 ESP_LOGI("CYM_DOOM","WAD_SEEK_FAILED offset=%ld whence=%d result=%d errno=%d",offset,whence,result,saved_errno);
 doom_startup_diag("WAD_SEEK_MEMORY",saved_errno,NULL);
}

#else
/* Headless legacy engine builds have no hardware heap or task diagnostics. */
static inline void doom_startup_diag(const char *phase,int result,void *audio){(void)phase;(void)result;(void)audio;}
static inline void doom_read_diag(unsigned *count,size_t size,size_t requested,size_t returned,int error,int eof,int saved_errno){(void)count;(void)size;(void)requested;(void)returned;(void)error;(void)eof;(void)saved_errno;}
static inline void doom_seek_diag(unsigned *count,long offset,int whence,int result,int saved_errno){(void)count;(void)offset;(void)whence;(void)result;(void)saved_errno;}
#endif
