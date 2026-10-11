/* CYM game integration; GPL-2.0-or-later. See LICENSE.engine and NOTICE.md. */
#ifndef CYM_STORAGE_GATE_H
#define CYM_STORAGE_GATE_H
#include <stdbool.h>
#include <stdint.h>
bool storage_gate_enter(void);
void storage_gate_leave(void);
bool storage_gate_freeze(void);
void storage_gate_thaw(void);
uint32_t storage_gate_active(void);
#endif
