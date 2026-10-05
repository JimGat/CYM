// Pure UTC startup gate, shared by PCF85063 users. Calendar/OS validated separately.
#pragma once
#include <stdbool.h>
#include <stdint.h>
static inline bool pcf85063_startup_epoch_valid(int64_t epoch, int64_t last_trusted) {
 return epoch >= 1704067200LL && epoch < 4102444800LL &&
        (last_trusted == 0 || epoch >= last_trusted - 2);
}
