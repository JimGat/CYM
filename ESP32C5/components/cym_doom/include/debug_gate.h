#pragma once
#include <stdbool.h>
#include <stdint.h>
#ifdef ESP_PLATFORM
#include "../../../main/debug_settings.h"
#elif defined(CYM_DEBUG_HOST_STATE)
bool cym_debug_enabled(void);
uint32_t cym_debug_generation(void);
void cym_debug_memory_report(void);
#else
/* Legacy headless engine fixtures retain measured counters. Focused settings
 * tests exercise the actual runtime API with mocked NVS, not this host default. */
static inline bool cym_debug_enabled(void){return true;}
static inline uint32_t cym_debug_generation(void){return 1;}
static inline void cym_debug_memory_report(void){}
#endif
/* Site-scoped optional chatter; warnings and fatal stderr paths are untouched. */
#define CYM_GAME_DEBUG_PRINTF(...) do {if(cym_debug_enabled())printf(__VA_ARGS__);} while(0)
#define CYM_GAME_DEBUG_DEH_PRINTF(...) do {if(cym_debug_enabled())DEH_printf(__VA_ARGS__);} while(0)
#define CYM_GAME_DEBUG_PUTS(...) do {if(cym_debug_enabled())puts(__VA_ARGS__);} while(0)
