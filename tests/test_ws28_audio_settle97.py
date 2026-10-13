from pathlib import Path
import subprocess, unittest
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.hermes/ws28-audio-settle97'
STUB=r'''#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#define ESP_OK 0
#define ESP_LOGI(...) ((void)0)
#define IO_EXPANDER_PIN_NUM_3 8
#define IO_EXPANDER_OUTPUT 1
#define pdMS_TO_TICKS(x) (x)
typedef int esp_err_t;
typedef struct handle H;
struct handle {struct {struct {int dir_out_bit_zero;} flags;} config; int(*read_direction_reg)(H*,uint32_t*);int(*read_output_reg)(H*,uint32_t*);int(*read_input_reg)(H*,uint32_t*);};
static uint32_t dir=0xff,out=3,pins=3;
static unsigned reads,delays,wait_ms,settle_after;
static int dir_error,write_error,read_error;
static int rd(H*h,uint32_t*p){(void)h;*p=dir;return 0;}
static int ro(H*h,uint32_t*p){(void)h;*p=out;return 0;}
static int ri(H*h,uint32_t*p){(void)h;reads++;if(read_error)return -1;if(reads>=settle_after)pins=out;*p=pins;return 0;}
static H device={{{0}},rd,ro,ri};static H*s_io_expander=&device;
static int esp_io_expander_set_dir(H*h,uint32_t mask,int mode){assert(h&&mask==8&&mode==1);if(dir_error)return -1;dir|=mask;return 0;}
static int esp_io_expander_set_level(H*h,uint32_t mask,int on){assert(h&&mask==8);if(write_error)return -1;if(on)out|=mask;else out&=~mask;return 0;}
void vTaskDelay(unsigned ms){assert(ms==10);delays++;wait_ms+=ms;}
static void reset(void){dir=0xff;out=pins=3;reads=delays=wait_ms=0;settle_after=1;dir_error=write_error=read_error=0;s_io_expander=&device;}
'''
HARNESS=r'''
int main(void){
reset();settle_after=3;assert(ws_c5_28_audio_amp(true));assert(reads==3&&delays==2&&wait_ms==20);assert(dir==0xff&&out==0x0b&&pins==0x0b);
reset();settle_after=1;assert(ws_c5_28_audio_amp(true));assert(reads==1&&!delays);
reset();out=pins=0x0b;settle_after=11;assert(ws_c5_28_audio_amp(false));assert(reads==11&&delays==10&&wait_ms==100&&out==3&&pins==3);
reset();settle_after=100;assert(!ws_c5_28_audio_amp(true));assert(reads==11&&delays==10&&wait_ms==100&&out==0x0b&&pins==3);
reset();read_error=1;assert(!ws_c5_28_audio_amp(true));assert(reads==1&&!delays);
reset();write_error=1;assert(!ws_c5_28_audio_amp(true));assert(!reads&&!delays&&out==3);
reset();dir_error=1;assert(!ws_c5_28_audio_amp(true));assert(!reads&&!delays&&out==3);
reset();s_io_expander=0;assert(!ws_c5_28_audio_amp(true));assert(!reads&&!delays);
return 0;}
'''
class WS28AudioSettle97(unittest.TestCase):
 def test_delayed_readback_and_bounded_failures(self):
  t=(ROOT/'ESP32C5/main/main.c').read_text();start=t.index('static bool ws_c5_28_audio_amp(bool on)');end=t.index('\n}',start)+2
  OUT.mkdir(parents=True,exist_ok=True);p=OUT/'settle.c';p.write_text(STUB+t[start:end]+HARNESS)
  cmd=['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',str(p),'-o',str(OUT/'settle')]
  run=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
  run=subprocess.run([str(OUT/'settle')],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stdout+run.stderr)
if __name__=='__main__': unittest.main(verbosity=2)
