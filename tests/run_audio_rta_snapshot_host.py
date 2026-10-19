#!/usr/bin/env python3
"""Count real production snapshot work, with immediately-ready synthetic capture."""
from pathlib import Path
import ast,os,subprocess
from audio_rta_nvs_stubs import write_nvs_stub
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'rta-snapshot';D.mkdir(parents=True,exist_ok=True)
write_nvs_stub(D)
tree=ast.parse((R/'tests/run_audio_rta_lifecycle_host.py').read_text())
strings=[n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='write_text' and n.args and isinstance(n.args[0],ast.Constant)]
port=next(s for s in strings if '#define portMUX_TYPE' in s)
a='static int64_t esp_timer_get_time(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (int64_t)t.tv_sec*1000000+t.tv_nsec/1000;}'
assert a in port
port=port.replace(a,'static int64_t modeled_us;static int64_t esp_timer_get_time(void){return modeled_us;}')
port=port.replace('static void vTaskDelay(unsigned n){usleep(n*1000);}','static void vTaskDelay(unsigned n){modeled_us+=n*10000;}')
(D/'audio_rta_host_port.h').write_text(port)
(D/'esp_err.h').write_text(next(s for s in strings if s.startswith('typedef int esp_err_t;')))
s=(R/'ESP32C5/main/audio_rta_dsp.c').read_text().replace('void audio_rta_dsp_snapshot(void*memory,audio_rta_spectrum_t*out){','unsigned snapshot_calls;\nvoid audio_rta_dsp_snapshot(void*memory,audio_rta_spectrum_t*out){snapshot_calls++;')
(D/'counted-dsp.c').write_text(s)
(D/'host.c').write_text(r"""
#define AUDIO_RTA_HOST 1
#include "audio_rta.c"
extern unsigned snapshot_calls;
struct audio_rta_board{int unused;};static unsigned reads;
size_t audio_rta_board_bytes(void){return sizeof(audio_rta_board_t);}
int audio_rta_board_open(audio_rta_board_t*b,void*bus,int g){(void)b;assert(bus&&g==24);return 0;}
int audio_rta_board_gain(audio_rta_board_t*b,int g){(void)b;(void)g;return 0;}
int audio_rta_board_close(audio_rta_board_t*b){(void)b;return 0;}
int audio_rta_board_read(audio_rta_board_t*b,int16_t*p,size_t cap,size_t*n,bool*gap){(void)b;assert(cap==512);modeled_us+=10667;*n=512;*gap=false;for(unsigned i=0;i<512;i++)p[i]=(i%48)*100;if(++reads==501)audio_rta_stop(latest.generation);return 0;}
int main(void){uint32_t g;assert(!audio_rta_start((void*)1,&g));for(int i=0;i<10000;i++){if(audio_rta_closed()&&!live_tasks)break;usleep(1000);}assert(audio_rta_closed()&&!live_tasks&&!live_alloc);
 printf("reads=%u snapshots=%u history=%llu valid=%x frames=%llu modeled_us=%lld\n",reads,snapshot_calls,(unsigned long long)latest.spectrum.samples,latest.spectrum.valid,(unsigned long long)latest.analysis_frames,(long long)modeled_us);fflush(stdout);
 assert(snapshot_calls<=110&&"do not scan 4096 samples and calculate logs on every capture read");assert(snapshot_calls>=90&&latest.spectrum.valid==0xffffff&&latest.spectrum.samples>=250000);return 0;}
""")
subprocess.run(['cc','-std=gnu11','-g','-O1','-fsanitize=address,undefined','-pthread','-I'+str(D),'-I'+str(R/'ESP32C5/main'),str(D/'host.c'),str(D/'counted-dsp.c'),'-lm','-o',str(D/'host')],check=True)
subprocess.run([str(D/'host')],check=True)
