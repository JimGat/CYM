#pragma once
#include "esp_heap_caps.h"
// Classic CYD variants have no PSRAM. Keep passive tools bounded in DRAM;
// PSRAM boards retain original capacities and presentation geometry.
static inline unsigned observer_heap_caps(void) {
#if CONFIG_BOARD_HAS_PSRAM
    return MALLOC_CAP_SPIRAM;
#else
    return MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT;
#endif
}
static inline unsigned observer_stack_bytes(unsigned requested_bytes) {
    // ESP-IDF task stack depth is bytes, not StackType_t elements. Preserve
    // each existing depth, including the 16 KiB cleanup/rescan headroom;
    // reduce Classic data capacities, never its established stack depth.
    return requested_bytes;
}
static inline int observer_waterfall_rows(int psram_rows) {
#if CONFIG_BOARD_HAS_PSRAM
    return psram_rows;
#else
    (void)psram_rows;
    return 16;
#endif
}
