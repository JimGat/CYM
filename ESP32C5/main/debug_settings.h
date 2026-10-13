/* Shared persisted diagnostics. Readers never touch NVS or UI objects. */
#ifndef CYM_DEBUG_SETTINGS_H
#define CYM_DEBUG_SETTINGS_H
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
bool cym_debug_enabled(void);
uint32_t cym_debug_generation(void);
esp_err_t cym_debug_load(void);
esp_err_t cym_debug_set(bool enabled);
int cym_debug_command(int argc, char **argv);
esp_err_t cym_debug_console_start(void);
void cym_debug_memory_report(void);
#endif
