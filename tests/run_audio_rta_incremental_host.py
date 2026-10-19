#!/usr/bin/env python3
"""Production coroutine overwrite/wrap/phase reset, with ASan and UBSan."""
from pathlib import Path
import os,subprocess
R=Path(__file__).resolve().parents[1]
D=Path(os.environ['CYM_TEST_OUT'])/'rta-incremental';D.mkdir(parents=True,exist_ok=True)
(D/'host.c').write_text(r"""
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "audio_rta_dsp.c"
static int16_t pcm[512];
static void input(dsp_t*d,unsigned n){while(n){unsigned k=n>512?512:n;assert(audio_rta_dsp_ingest(d,pcm,k,NULL,NULL));n-=k;}}
static void finish(dsp_t*d){unsigned calls=0;while(audio_rta_dsp_work(d))assert(++calls<2000);}
int main(void){
 dsp_t*d=calloc(1,audio_rta_dsp_bytes());assert(d);
 for(unsigned i=0;i<512;i++)pcm[i]=(int16_t)(10000*sin(2*PI*i/48));
 for(unsigned low=0;low<2;low++)for(unsigned phase=0;phase<=6;phase++){
  audio_rta_dsp_init(d);input(d,low?32768:4096);d->next_low=low;
  unsigned calls=0;while(d->job_phase!=phase){assert(audio_rta_dsp_work(d));assert(++calls<1000);}
  if(phase)assert(d->job_low==(bool)low);
  assert(d->out.valid==0&&d->out.frames==0);
  audio_rta_dsp_reset(d);assert(!d->job_phase&&!d->out.valid&&!d->out.frames);
  input(d,4096);finish(d);assert(d->out.valid==0xfffe00&&d->out.frames==1);
 }
 for(unsigned low=0;low<2;low++){
  audio_rta_dsp_init(d);input(d,low?32768:4096);d->next_low=low;
  assert(audio_rta_dsp_work(d)&&d->job_phase==1&&d->job_low==(bool)low);
  /* Intentionally underservice the copy while capture advances one extra window. */
  for(unsigned i=0;i<(low?8u:16u);i++){input(d,low?4096:256);assert(audio_rta_dsp_work(d));}
  assert(d->analysis_restarts==1&&d->job_phase==0&&d->out.frames==0&&!d->out.valid);
  finish(d);assert(d->out.frames==(low?2u:1u)&&d->out.valid==(low?0xffffffu:0xfffe00u)&&d->last[low?0:9]==d->total);
 }
 /* Unsigned source-time arithmetic remains valid across uint64 wrap. */
 audio_rta_dsp_reset(d);d->total=UINT64_MAX-2047;input(d,4096);finish(d);
 assert(d->total==2048&&d->out.valid==0xfffe00&&d->last[9]==2048);
 input(d,512);audio_rta_spectrum_t out;audio_rta_dsp_snapshot(d,&out);
 assert(out.age[9]==512&&out.valid==0xfffe00);
 d->total+=(uint64_t)UINT32_MAX+1;audio_rta_dsp_snapshot(d,&out);
 assert(out.age[9]==UINT32_MAX&&!out.valid);
 free(d);puts("PASS production incremental: reset full/bass phases0..6, full/bass overwrite rejection/recovery, uint64 source wrap, saturating ages/stale validity");
 return 0;
}
""")
cmd=['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(R/'ESP32C5/main'),str(D/'host.c'),'-lm','-o',str(D/'host')]
subprocess.run(cmd,check=True);subprocess.run([str(D/'host')],check=True)
