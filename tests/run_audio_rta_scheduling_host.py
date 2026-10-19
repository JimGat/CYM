#!/usr/bin/env python3
'''Production session + DSP regression: immediate I/O, overrun feedback, cancellation.'''
from pathlib import Path
import ast,os,subprocess
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'rta-scheduling';D.mkdir(parents=True,exist_ok=True)
tree=ast.parse((R/'tests/run_audio_rta_lifecycle_host.py').read_text())
strings=[n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='write_text' and n.args and isinstance(n.args[0],ast.Constant)]
port=next(s for s in strings if '#define portMUX_TYPE' in s)
port=port.replace('static void vTaskDelay(unsigned n){usleep(n*1000);}', 'static atomic_int delays; static _Atomic long long simulated_us; static void (*yield_hook)(void); static void vTaskDelay(unsigned n){assert(n>0);delays++;simulated_us+=n*10000;if(yield_hook)yield_hook();usleep(100);}')
a='static int64_t esp_timer_get_time(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (int64_t)t.tv_sec*1000000+t.tv_nsec/1000;}'
assert port.count(a)==1
port=port.replace(a,'static _Atomic long long simulated_us; static void (*clock_hook)(void); static int64_t esp_timer_get_time(void){if(clock_hook)clock_hook();return simulated_us;}')
port=port.replace('static bool cym_debug_enabled(void){return false;}', '')
port=port.replace('#define ESP_LOGI(...) ((void)0)', '#define ESP_LOGI(...) capture_log(__VA_ARGS__)\nstatic atomic_int log_lines; static bool debug_on=true; static bool cym_debug_enabled(void){return debug_on;} static void capture_log(const char*tag,const char*fmt,...){(void)tag;if(strstr(fmt,"diag ")){assert(debug_on);char line[1024];va_list args;va_start(args,fmt);vsnprintf(line,sizeof(line),fmt,args);va_end(args);assert(strstr(line,"generation=1 state=")&&strstr(line,"samples=")&&strstr(line,"valid=")&&strstr(line,"read_us=")&&strstr(line,"process_us=")&&strstr(line,"rms_x10="));puts(line);log_lines++;}}')
(D/'audio_rta_host_port.h').write_text(port)
(D/'esp_err.h').write_text(next(s for s in strings if s.startswith('typedef int esp_err_t;')))
(D/'host.c').write_text(r'''
#define AUDIO_RTA_HOST 1
#include "audio_rta.c"
#include <math.h>
static atomic_int opened,trig_calls,runtime_trig,reads,opens;
static double counted_cos(double x){trig_calls++;if(opened)runtime_trig++;return cos(x);}
static double counted_sin(double x){trig_calls++;if(opened)runtime_trig++;return sin(x);}
#define cos counted_cos
#define sin counted_sin
#include "audio_rta_dsp.c"
#undef cos
#undef sin
struct audio_rta_board {int seen;};
static int mode,open_delays,first=1,cancel_at=1,runtime_cancelled;
static void work_clock(void){simulated_us+=2000;}
static void cancel_processing(void){
 if(opened && owner && ((dsp_t*)owner->dsp)->full_count==4096 && !((dsp_t*)owner->dsp)->out.frames){runtime_cancelled=1;audio_rta_stop(latest.generation);}
}
size_t audio_rta_board_bytes(void){return sizeof(audio_rta_board_t);}
esp_err_t audio_rta_board_open(audio_rta_board_t*b,void*bus,int gain){assert(bus&&gain==0);opens++;opened=1;b->seen=trig_calls;open_delays=delays;if(mode==2)audio_rta_controls(latest.generation,true,false,0,false);return ESP_OK;}
esp_err_t audio_rta_board_gain(audio_rta_board_t*b,int gain){(void)b;(void)gain;return ESP_OK;}
esp_err_t audio_rta_board_close(audio_rta_board_t*b){(void)b;opened=0;return ESP_OK;}
esp_err_t audio_rta_board_read(audio_rta_board_t*b,int16_t*p,size_t cap,size_t*n,bool*discontinuity){*discontinuity=false;assert(cap==512);reads++;simulated_us+=1000;*n=512;for(int i=0;i<512;i++)p[i]=(i%48<24)?10000:-10000;
 if(reads>=200)audio_rta_stop(latest.generation);
 if(mode==4){if(reads==30)audio_rta_controls(latest.generation,true,true,0,false);if(reads==40)audio_rta_controls(latest.generation,false,true,0,false);if(reads==60)audio_rta_controls(latest.generation,false,true,6,false);}
 if(mode==5){*discontinuity=true;return ESP_OK;}
 if(mode==6)*n=0;
 if(mode==10&&reads==8){clock_hook=work_clock;yield_hook=cancel_processing;}
 if(mode>=8&&mode<10){simulated_us+=10000;if(mode==9)debug_on=false;}
 /* Model observed feedback: rebuilding transcendental tables while RX is
  * active overruns the ring again. No unconditional sleep hides starvation. */
 if(mode==1 && (first||b->seen!=trig_calls)){first=0;b->seen=trig_calls;*discontinuity=true;return ESP_OK;}
 return ESP_OK;}
static void cancel_on_yield(void){if(delays==cancel_at)audio_rta_stop(latest.generation);}
int main(int argc,char**argv){assert(argc==2||argc==3);mode=atoi(argv[1]);if(argc==3)cancel_at=atoi(argv[2]);if(mode==3)yield_hook=cancel_on_yield;uint32_t g;assert(!audio_rta_start((void*)1,&g));
 for(int i=0;i<30000;i++){if(audio_rta_closed()&&!live_tasks)break;usleep(1000);}
 assert(audio_rta_closed()&&!live_tasks&&!live_alloc);audio_rta_snapshot_t s;assert(audio_rta_snapshot(g,&s));
 if(mode==1){assert(s.overruns==1 && s.sequence>0 && "overrun must recover without rebuilding tables");assert(runtime_trig==0);}
 if(mode==2){assert(delays-open_delays>=3 && "immediately ready frozen reads must block for main and idle");}
 if(mode!=3&&mode<8){assert(delays-open_delays==3 && "50-ms budget must not sleep on every read");}
 if(mode==3){assert(delays==cancel_at);assert(opens==0 && "cancel during preparation must not acquire I2S");}
 if(mode>=4&&mode<10){assert(runtime_trig==0);assert(delays-open_delays>=3);}
 if(mode==4){assert(s.gain_db==6&&s.spectrum.valid&&s.sequence>0);}
 if(mode==5){assert(s.overruns==199&&s.sequence==0);}
 if(mode==6){assert(s.spectrum.valid==0&&s.sequence==0&&s.spectrum.frames==0);}
 assert(s.read_calls==(uint64_t)reads && s.input_samples==(uint64_t)(mode==6?0:reads*512));
 if(mode==5)assert(s.history_resets==199 && s.spectrum.frames==0);
 if(mode==8){assert(log_lines>=2&&log_lines<=3);assert(s.spectrum.frames>0&&s.max_work_us>0&&s.read_us>0);}
 if(mode==9)assert(log_lines==0);
 if(mode==10){assert(runtime_cancelled&&reads==8&&s.sequence==7&&s.spectrum.frames==0);}
 if(mode==7){assert(s.spectrum.valid&&s.sequence>0);
  portENTER_CRITICAL(&mux);latest.state=RTA_RUNNING;latest.timestamp_us=simulated_us;portEXIT_CRITICAL(&mux);
  assert(audio_rta_snapshot(g,&s)&&!s.stale);simulated_us+=500001;assert(audio_rta_snapshot(g,&s)&&s.stale);
  portENTER_CRITICAL(&mux);latest.state=RTA_FROZEN;portEXIT_CRITICAL(&mux);assert(audio_rta_snapshot(g,&s)&&!s.stale);
 }
 printf("PASS mode=%d reads=%d overruns=%u sequence=%llu runtime_trig=%d blocking_points=%d opens=%d\n",mode,reads,s.overruns,(unsigned long long)s.sequence,runtime_trig,delays,opens);
 return 0;}
''')
subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-pthread','-I'+str(D),'-I'+str(R/'ESP32C5/main'),str(D/'host.c'),'-lm','-o',str(D/'host')],check=True)
results=[subprocess.run([str(D/'host'),str(mode)]).returncode for mode in (1,2,3,4,5,6,7,8,9,10)]
results += [subprocess.run([str(D/'host'),'3',str(checkpoint)]).returncode for checkpoint in (32,65)]
assert not any(results),results
