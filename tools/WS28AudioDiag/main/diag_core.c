#include "diag_core.h"
#include <math.h>
void diag_pcm(int16_t *out, size_t count, unsigned offset) {
 for(size_t i=0;i<count;i++) {
  unsigned pos=offset+(unsigned)i;
  /* 10ms edge ramps keep the short test conservative. */
  double gain=1.0;
  if(pos<220) gain=(double)pos/220;
  if(pos>=DIAG_SAMPLES-220 && pos<DIAG_SAMPLES) gain=(double)(DIAG_SAMPLES-1-pos)/220;
  out[i]=pos<DIAG_SAMPLES ? (int16_t)(2048.0*gain*sin(6.283185307179586*440.0*pos/DIAG_RATE)) : 0;
 }
}
int diag_run(int (*step)(void *, enum diag_op), void *ctx) {
 const enum diag_op ops[]={DIAG_OFF,DIAG_DIRECTION,DIAG_SAMPLE,DIAG_ON,DIAG_SAMPLE,DIAG_OFF,DIAG_SAMPLE,DIAG_INIT,DIAG_ON,DIAG_TONE};
 int result=0;
 for(size_t i=0;i<sizeof(ops)/sizeof(ops[0]);i++) if(step(ctx,ops[i])!=0){result=-1;break;}
 /* Two independent attempts: never skip cleanup because off failed. */
 if(step(ctx,DIAG_OFF)!=0) result=-1;
 if(step(ctx,DIAG_CLEANUP)!=0) result=-1;
 if(step(ctx,DIAG_OFF)!=0) result=-1;
 return result;
}
