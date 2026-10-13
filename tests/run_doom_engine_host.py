#!/usr/bin/env python3
"""Build and run the actual imported engine with external official Freedoom.
No downloads, asset installation, source mutation, or firmware builds.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--wad',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--silent',action='store_true',help='Exercise production sound adapter with mocked safely unavailable audio');a=p.parse_args()
 assert hashlib.sha256(a.wad.read_bytes()).hexdigest()=='7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d'
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);comp=ROOT/'ESP32C5/components/cym_doom'
 (out/'esp_heap_caps.h').write_text('#ifndef HOST_ESP_HEAP_CAPS_H\n#define HOST_ESP_HEAP_CAPS_H\n#include <stddef.h>\n#include <stdlib.h>\n#define MALLOC_CAP_SPIRAM 1\n#define MALLOC_CAP_8BIT 2\nstatic inline void *heap_caps_malloc(size_t n,unsigned c){(void)c;return malloc(n);}\nstatic inline void *heap_caps_calloc(size_t n,size_t s,unsigned c){(void)c;return calloc(n,s);}\nstatic inline void heap_caps_free(void *p){free(p);}\n#endif\n')
 (out/'state.ld').write_text('SECTIONS { .doom_state : { __doom_state_start = .; *libcym_doom_engine.a:(.data .data.* .bss .bss.* .sdata .sdata.* .sbss .sbss.* COMMON) __doom_state_end = .; } } INSERT AFTER .data;\n')
 args=['cc','-std=gnu11','-g','-O1','-fno-common','-fdata-sections','-ffunction-sections','-fno-strict-aliasing','-fwrapv','-fsanitize=address','-D_POSIX_C_SOURCE=200809L','-D_DEFAULT_SOURCE','-I'+str(out),'-I'+str(comp/'engine'),'-I'+str(comp/'include')]
 prov=json.loads((comp/'PROVENANCE.json').read_text());objects=[]
 if a.silent:(out/'esp_log.h').write_text('#pragma once\n#define ESP_LOGW(...) ((void)0)\n')
 with (out/'compile.log').open('w') as log:
  for entry in prov['imported_files']:
   if not entry['path'].endswith('.c'):continue
   src=comp/entry['path'];obj=out/(src.name+'.o')
   subprocess.run(args+['-include',str(comp/'include/doom_runtime_shim.h'),'-c',str(src),'-o',str(obj)],check=True,stdout=log,stderr=log);objects.append(str(obj))
  assert len(objects)==80
  for src in [comp/'engine/i_cym_sound.c',comp/'doom_mixer.c']:
   obj=out/(src.name+'.o');extra=['-DESP_PLATFORM','-DCONFIG_BOARD_WS_C5_28=1'] if a.silent and src.name=='i_cym_sound.c' else [];subprocess.run(args+extra+['-include',str(comp/'include/doom_runtime_shim.h'),'-c',str(src),'-o',str(obj)],check=True,stdout=log,stderr=log);objects.append(str(obj))
  if a.silent:
   mock=out/'silent_audio.c';mock.write_text('#include <stdbool.h>\n#include <stdlib.h>\n#include "doom_audio.h"\n#include "doom_metrics.h"\nunsigned long cym_host_audio_samples,cym_host_audio_nonzero,cym_host_audio_starts;\nbool cym_debug_enabled(void){return false;}\nbool doom_audio_begin(void){return false;}\nbool doom_audio_silent_ready(void){return true;}\nbool doom_audio_healthy(void){return false;}\nunsigned doom_audio_demand(void){return 0;}\nbool doom_audio_write(const int16_t*p,size_t n){(void)p;(void)n;abort();}\nint doom_audio_end(void){return 0;}\n')
   obj=out/'silent_audio.o';subprocess.run(args+['-c',str(mock),'-o',str(obj)],check=True,stdout=log,stderr=log);objects.append(str(obj))
  subprocess.run(['ar','rcs',str(out/'libcym_doom_engine.a')]+objects,check=True,stdout=log,stderr=log)
  host=ROOT/'tests/doom_engine_host.c'
  if a.silent:
   host=out/'silent_engine_host.c';text=(ROOT/'tests/doom_engine_host.c').read_text();assert text.count('assert(cym_host_audio_starts>0);assert(cym_host_audio_samples>0);assert(cym_host_audio_nonzero>0);')==1;text=text.replace('assert(cym_host_audio_starts>0);assert(cym_host_audio_samples>0);assert(cym_host_audio_nonzero>0);','assert(cym_host_audio_starts==0);assert(cym_host_audio_samples==0);assert(cym_host_audio_nonzero==0);').replace('REAL_ENGINE_AUDIO','REAL_ENGINE_SILENT').replace('SFX_ONLY host_sink','mock_safe_audio_failure');host.write_text(text)
  subprocess.run(args+[str(host),str(comp/'doom_session.c'),str(comp/'doom_contracts.c'),str(out/'libcym_doom_engine.a'),'-Wl,-T,'+str(out/'state.ld'),'-lm','-o',str(out/'engine-test')],check=True,stdout=log,stderr=log)
 r=subprocess.run([str(out/'engine-test'),str(a.wad.resolve())],capture_output=True,text=True,timeout=180,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:detect_stack_use_after_return=1'})
 (out/'runtime.log').write_text(r.stdout+r.stderr)
 print('\n'.join(x for x in (r.stdout+r.stderr).splitlines() if 'REAL_ENGINE' in x or 'ERROR:' in x))
 raise SystemExit(r.returncode)
if __name__=='__main__':main()
