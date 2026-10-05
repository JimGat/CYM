#include <assert.h>
#include <stdio.h>
#include "cym_rtc_validity.h"
int main(void) {
 assert(!pcf85063_startup_epoch_valid(0,0));
 assert(!pcf85063_startup_epoch_valid(1704067199,0));
 assert(pcf85063_startup_epoch_valid(1704067200,0));
 assert(pcf85063_startup_epoch_valid(1791238000,1791237990));
 assert(!pcf85063_startup_epoch_valid(1791237980,1791237990));
 assert(!pcf85063_startup_epoch_valid(4102444800LL,0));
 assert(pcf85063_startup_epoch_valid(4102444799LL,0));
 puts("RTC startup epoch/range/rollback: PASS");return 0;
}
