#include "diag_core.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
struct state { int fail, calls, off, cleanup, tones, holds_off, holds_on; bool amp_on, audio_started; };
static int step(void *v, enum diag_op op) {
 struct state *s=v; s->calls++;
 if(op==DIAG_OFF) {s->off++;s->amp_on=false;}
 if(op==DIAG_ON) s->amp_on=true;
 if(op==DIAG_HOLD_OFF) {assert(!s->amp_on&&!s->audio_started);s->holds_off++;}
 if(op==DIAG_HOLD_ON) {assert(s->amp_on&&!s->audio_started);s->holds_on++;}
 if(op==DIAG_INIT) {assert(s->holds_on==1&&s->holds_off==2&&!s->amp_on);s->audio_started=true;}
 if(op==DIAG_CLEANUP) s->cleanup++;
 if(op==DIAG_TONE) s->tones++;
 return s->calls==s->fail ? -1 : 0;
}
int main(void){
 int16_t pcm[256];unsigned nonzero=0;int peak=0;
 for(unsigned pos=0;pos<DIAG_SAMPLES;pos+=256){
  unsigned n=DIAG_SAMPLES-pos; if(n>256)n=256;diag_pcm(pcm,n,pos);
  for(unsigned i=0;i<n;i++){int a=abs(pcm[i]);assert(a<=2048);if(a>peak)peak=a;nonzero+=a!=0;}
 }
 assert(nonzero>DIAG_SAMPLES*9/10);assert(peak>=2040);
 struct state ok={0};assert(diag_run(step,&ok)==0);assert(ok.tones==1&&ok.cleanup==1&&ok.off==4);
 /* Three bounded meter windows must be in the policy before audio init. */
 assert(ok.calls==16&&ok.holds_on==1&&ok.holds_off==2);
 assert(DIAG_HOLD_ON_SECONDS==15&&DIAG_HOLD_OFF_SECONDS==5);
 assert(diag_window_remaining_us(100,100,15000000)==15000000);
 assert(diag_window_remaining_us(100,14999999,15000000)==101);
 assert(diag_window_remaining_us(100,15000100,15000000)==0);
 assert(diag_window_remaining_us(100,16000100,15000000)==0);
 for(int fail=1;fail<=ok.calls;fail++){struct state s={.fail=fail};assert(diag_run(step,&s)!=0);assert(s.off>=1&&s.cleanup==1);}
 /* Successful sample callback includes permanently mismatching inputs: not a gate. */
 printf("PASS PCM samples=%u nonzero=%u peak=%d; policy fault positions=%d cleanup/off mandatory mismatch not gated\n",DIAG_SAMPLES,nonzero,peak,ok.calls);
 return 0;
}
