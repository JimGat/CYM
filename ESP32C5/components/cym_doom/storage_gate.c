/* CYM game integration; GPL-2.0-or-later. See LICENSE.engine and NOTICE.md. */
/* Admission, not cleanup: refuse reset with any real SD open/operation.
 * Double-check after reservation closes the freeze-vs-new-owner race. */
#include "storage_gate.h"
#include <stdatomic.h>
static atomic_bool frozen;
static atomic_uint active;
bool storage_gate_enter(void)
{
 if(atomic_load_explicit(&frozen,memory_order_seq_cst))return false;
 atomic_fetch_add_explicit(&active,1,memory_order_seq_cst);
 if(atomic_load_explicit(&frozen,memory_order_seq_cst)){
  atomic_fetch_sub_explicit(&active,1,memory_order_seq_cst);return false;
 }
 return true;
}
void storage_gate_leave(void){atomic_fetch_sub_explicit(&active,1,memory_order_seq_cst);}
bool storage_gate_freeze(void){atomic_store_explicit(&frozen,true,memory_order_seq_cst);return atomic_load_explicit(&active,memory_order_seq_cst)==0;}
void storage_gate_thaw(void){atomic_store_explicit(&frozen,false,memory_order_seq_cst);}
uint32_t storage_gate_active(void){return atomic_load_explicit(&active,memory_order_seq_cst);}
