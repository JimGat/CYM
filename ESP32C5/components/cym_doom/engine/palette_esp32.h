#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void DG_PaletteLoad(const void *playpal);
uint16_t DG_PaletteColor565(uint8_t index);

#ifdef __cplusplus
}
#endif