from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.hermes/revision91'
class Revision91(unittest.TestCase):
 def test_production_accounting(self):
  OUT.mkdir(parents=True,exist_ok=True)
  src=OUT/'account.c';src.write_text("""#include "ui_diagnostics.h"
#include <assert.h>
int main(void){cym_ui_diag d={0};cym_ui_diag_add(&d,0,40);cym_ui_diag_add(&d,0,10);cym_ui_diag_add(&d,1,7);cym_ui_diag_add(&d,2,25);
assert(d.window[0].count==2&&d.window[0].us==50&&d.window[0].max_us==40);assert(d.total[0].count==2&&d.total[0].us==50);
cym_ui_diag_reset_window(&d);assert(!d.window[0].count&&!d.window[0].us&&!d.window[0].max_us);assert(d.total[0].count==2&&d.total[0].max_us==40);
cym_ui_diag_add(&d,0,5);assert(d.window[0].max_us==5&&d.total[0].max_us==40);assert(d.total[1].us==7&&d.total[2].us==25);
assert(cym_ui_diag_elapsed(0xfffffff0u,0x10u)==32);return 0;}""")
  p=subprocess.run(['cc','-Wall','-Wextra','-Werror','-I'+str(ROOT/'ESP32C5/main'),str(src),'-o',str(OUT/'account')],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
  self.assertEqual(subprocess.run([str(OUT/'account')]).returncode,0)
 def extract(self,text,signature):
  a=text.index(signature);b=text.index('{',a);depth=1;i=b+1
  while depth:
   depth+=(text[i]=='{')-(text[i]=='}');i+=1
  return text[a:i]
 def run_c(self,name,code):
  OUT.mkdir(parents=True,exist_ok=True);src=OUT/(name+'.c');src.write_text(code)
  p=subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-unused-variable','-Wno-misleading-indentation',str(src),'-o',str(OUT/name)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
  p=subprocess.run([str(OUT/name)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
 def test_ws35_production_amp(self):
  function=self.extract((ROOT/'ESP32C5/main/ws_c5_35_port.c').read_text(),'bool ws_c5_35_audio_amp(bool on)')
  code=r"""#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stddef.h>
#define ESP_OK 0
#define ESP_LOGI(...) ((void)0)
#define WS35_EXIO_REG_OUTPUT 3
#define BOARD_POWER_ENABLE_EXIO 5
typedef int esp_err_t;
static void*s_exio_dev=(void*)1;static uint16_t mode_shadow=0x23,output_shadow=0xa5e3;
static int write_fail,read_fail,mismatch,writes;static uint16_t hardware;
int i2c_master_transmit(void*h,const uint8_t*p,size_t n,int timeout){assert(h&&n==3&&p[0]==3&&timeout==100);writes++;if(write_fail)return -1;hardware=p[1]|(p[2]<<8);return 0;}
int i2c_master_transmit_receive(void*h,const uint8_t*p,size_t n,uint8_t*out,size_t len,int timeout){assert(h&&n==1&&p[0]==4&&len==2&&timeout==100);if(read_fail)return -1;*out=(hardware&255)^(mismatch?32:0);out[1]=hardware>>8;return 0;}
"""+function+r"""
int main(void){uint16_t keep=output_shadow&~32;assert(ws_c5_35_audio_amp(false));assert((output_shadow&~32)==keep&&!(hardware&32));assert(ws_c5_35_audio_amp(true));assert((output_shadow&~32)==keep&&(hardware&32));uint16_t before=output_shadow;write_fail=1;assert(!ws_c5_35_audio_amp(false)&&output_shadow==before);write_fail=0;read_fail=1;assert(!ws_c5_35_audio_amp(false)&&!(output_shadow&32));read_fail=0;mismatch=1;assert(!ws_c5_35_audio_amp(true));mismatch=0;assert(ws_c5_35_audio_amp(false));int count=writes;mode_shadow&=~32;assert(!ws_c5_35_audio_amp(true)&&writes==count);mode_shadow|=32;s_exio_dev=0;assert(!ws_c5_35_audio_amp(true)&&writes==count);return 0;}
"""
  self.run_c('amp35',code)
 def test_ws28_production_amp(self):
  function=self.extract((ROOT/'ESP32C5/main/main.c').read_text(),'static bool ws_c5_28_audio_amp(bool on)')
  code=r"""#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#define ESP_OK 0
#define ESP_LOGI(...) ((void)0)
#define IO_EXPANDER_PIN_NUM_3 8
#define IO_EXPANDER_OUTPUT 1
#define pdMS_TO_TICKS(x) (x)
void vTaskDelay(unsigned ms){assert(ms==10);}
typedef int esp_err_t;
typedef struct handle H;struct handle{struct{struct{int dir_out_bit_zero;}flags;}config;int(*read_direction_reg)(H*,uint32_t*);int(*read_output_reg)(H*,uint32_t*);int(*read_input_reg)(H*,uint32_t*);};
static uint32_t dir=0xa3,out=0xd7;static int step,fail_at=-1,mismatch;
static int op(void){return step++==fail_at?-1:0;}
int rd(H*h,uint32_t*p){(void)h;if(op())return -1;*p=dir;return 0;}int ro(H*h,uint32_t*p){(void)h;if(op())return -1;*p=out;return 0;}int ri(H*h,uint32_t*p){(void)h;if(op())return -1;*p=out^(mismatch?8:0);return 0;}
static H handle={{{0}},rd,ro,ri};static H*s_io_expander=&handle;
int esp_io_expander_set_dir(H*h,uint32_t mask,int direction){assert(h&&mask==8&&direction==1);if(op())return -1;dir|=mask;return 0;}
int esp_io_expander_set_level(H*h,uint32_t mask,int on){assert(h&&mask==8);if(op())return -1;out=on?out|mask:out&~mask;return 0;}
"""+function+r"""
int main(void){uint32_t keepdir=dir&~8,keepout=out&~8;assert(ws_c5_28_audio_amp(true));assert((dir&~8)==keepdir&&(out&~8)==keepout&&(out&8));assert(ws_c5_28_audio_amp(false)&&!(out&8));for(int f=0;f<5;f++){step=0;fail_at=f;assert(!ws_c5_28_audio_amp(true));assert((dir&~8)==keepdir&&(out&~8)==keepout);}fail_at=-1;mismatch=1;assert(!ws_c5_28_audio_amp(true));mismatch=0;assert(ws_c5_28_audio_amp(false));s_io_expander=0;assert(!ws_c5_28_audio_amp(true));return 0;}
"""
  self.run_c('amp28',code)
 def test_navigation_wrappers(self):
  main=(ROOT/'ESP32C5/main/main.c').read_text()
  wrappers='\n'.join(self.extract(main,'static void '+n+'('+param+')\n{') for n,param in [('show_settings_screen','void'),('show_hardware_options_screen','void'),('settings_tile_event_cb','lv_event_t *e'),('hw_options_tile_event_cb','lv_event_t *e')])
  code=r"""#include <stdint.h>
#include <assert.h>
typedef int lv_event_t;
enum {CYM_UI_SETTINGS=2,CYM_UI_HARDWARE=3,CYM_UI_SETTINGS_EVENT=4,CYM_UI_HARDWARE_EVENT=5};
static unsigned calls[6],recorded[6];static uint32_t clk;
uint32_t cym_ui_diag_clock(void){return clk+=10;}
void cym_ui_diag_record(unsigned kind,uint32_t started){assert(kind>=2&&kind<=5&&clk==started);recorded[kind]++;}
static void show_settings_screen_measured(void){calls[2]++;}
static void show_hardware_options_screen_measured(void){calls[3]++;}
static void settings_tile_event_cb_measured(lv_event_t*e){assert(e);calls[4]++;}
static void hw_options_tile_event_cb_measured(lv_event_t*e){assert(e);calls[5]++;}
"""+wrappers+r"""
int main(void){int event=9;show_settings_screen();show_hardware_options_screen();settings_tile_event_cb(&event);hw_options_tile_event_cb(&event);for(int i=2;i<6;i++)assert(calls[i]==1&&recorded[i]==1);return 0;}
"""
  self.run_c('nav-wrappers',code)
 def test_pinned_hooks(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('lvdiag',ROOT/'scripts/lvgl-diag-copy.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  source=(ROOT/'ESP32C5/managed_components/lvgl__lvgl/src/core/lv_refr.c').read_text();output=m.instrument(source)
  self.assertEqual(output.count('cym_ui_diag_record(0,'),1);self.assertEqual(output.count('cym_ui_diag_record(1,'),3)
  self.assertEqual(output.count('call_flush_cb('),source.count('call_flush_cb('))
  with self.assertRaises(ValueError):m.instrument(source+'\n')
if __name__=='__main__':unittest.main()
