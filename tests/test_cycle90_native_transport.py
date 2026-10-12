"""Actual isolated stripe helper and main loop, injected bus/DMA faults."""
from pathlib import Path
import subprocess,unittest
from test_cycle84_dma_timekeeper import TRANSPORT
ROOT=Path(__file__).resolve().parents[1]
class NativeTransport(unittest.TestCase):
 def test_real_native_stripe_completion_and_faults(self):
  helper=ROOT/'ESP32C5/main/isolated_native_panel.h'
  self.assertTrue(helper.exists(),'missing isolated completion-owned native stripe helper')
  pre=TRANSPORT.replace('static bool exclusive,','static bool cancel_on_wait,input_exit;\nstatic bool exclusive,').replace('dma_waits++;assert(borrowed);','dma_waits++;assert(borrowed);if(cancel_on_wait)input_exit=true;').replace('now+=20000','now+=100').replace('assert(borrowed&&locked&&!acks&&!releases);longjmp','assert(borrowed&&locked);longjmp')
  code=pre+'\n#include "doom_native.h"\n#include "doom_metrics.h"\ndoom_metrics_t doom_metrics;\n#include "game_panel_transport.h"\n'
  code+=r"""
static esp_lcd_panel_handle_t panel_handle;
static unsigned input_polls;
static bool game_native_poll(void *ctx){(void)ctx;input_polls++;return !input_exit;}
#include "isolated_native_panel.h"
static void host_completion(void){cym_diag_isr(&s_display_channel,(uint32_t)esp_timer_get_time());}
int main(void){
 assert(cym_panel_transport_init()==ESP_OK);uint16_t *p=s_panel_stage;
 doom_rect r={0,0,320,6};enforce_dma=true;
 for(unsigned i=0;i<1920;i++)p[i]=i+7;
 assert(!game_native_send(NULL,(doom_rect){0,0,320,7},p));assert(!draws);
 bus_busy=true;assert(!game_native_send(NULL,r,p));assert(lock_attempts==1&&!borrowed&&!locked&&!draws);
 bus_busy=false;fail_queue=true;assert(!game_native_send(NULL,r,p));assert(!borrowed&&!locked&&!dma_waits);
 fail_queue=false;unsigned completed=s_display_diag[1].completed;
 assert(game_native_send(NULL,r,p));assert(!borrowed&&!locked&&s_display_diag[1].completed==completed+1);
 for(int i=0;i<1920;i++)assert(panel[i]==i+7);
 /* Exit cannot release accepted memory during delayed completion. */
 input_exit=true;assert(!game_native_send(NULL,r,p));assert(!borrowed&&!locked);
 input_exit=false;cancel_on_wait=true;unsigned prior=input_polls;
 assert(game_native_send(NULL,r,p));assert(input_exit&&!borrowed&&!locked&&input_polls>prior);
 cancel_on_wait=input_exit=false;never_complete=true;
 if(!setjmp(restart_boundary)){game_native_send(NULL,r,p);assert(!"missing completion must restart");}
 assert(borrowed&&locked);puts("actual native stripe: bounded SD admission, delayed/rejected/missing DMA, no false completion, retained ownership PASS");
}
"""
  out=Path('/home/dev/ws-c5-35-fixes/cycle90/host');out.mkdir(parents=True,exist_ok=True);(out/'native-transport.c').write_text(code)
  r=subprocess.run(['cc','-std=gnu11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'ESP32C5/main'),'-I'+str(ROOT/'ESP32C5/components/cym_doom/include'),str(out/'native-transport.c'),'-o',str(out/'native-transport')],capture_output=True,text=True)
  (out/'native-transport-compile.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(out/'native-transport')],capture_output=True,text=True);(out/'native-transport.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)

 def test_actual_main_loop_local_priority_and_positive_block(self):
  source=(ROOT/'ESP32C5/main/main.c').read_text();start=source.index('    doom_ui_boot_start(doom_prototype_home,sd_mounted_lazy);');end=source.index('\n}\n#endif',start)
  loop=source[start:end]
  code=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <setjmp.h>
#include <stdio.h>
#include "doom_native.h"
#define CYM_PANEL_STAGE_BYTES 4096
#define pdTRUE 1
#define pdMS_TO_TICKS(n) ((n)/10)
#define ESP_ERROR_CHECK(n) assert((n)==0)
#define ESP_LOGI(...) ((void)0)
static int sd_mounted_lazy,lvgl_mutex,tick_timer,s_panel_stage;
static struct {uint32_t pending;} s_display_channel;
static struct {uint32_t callback_us;} s_display_diag[2];
static unsigned priority=1,handler_calls,native_calls,blocks,engine_steps,pcm_steps,takeovers;
static bool handler_active;static jmp_buf finish;
static void doom_prototype_home(void){}
static void doom_ui_boot_start(void (*home)(void),bool sd){(void)home;(void)sd;}
static bool game_native_send(void *c,doom_rect r,const uint16_t *p){(void)c;(void)r;(void)p;return true;}
static bool game_native_poll(void *c){(void)c;return true;}
static void doom_ui_native_configure(int buf,size_t cap,doom_native_send send,doom_native_poll poll){(void)buf;assert(cap==2048&&send&&poll);}
static void doom_ui_boot_fire(bool b){(void)b;}
#define BOOT_BTN_GPIO 0
static int gpio_get_level(int pin){(void)pin;return 1;}
static bool xSemaphoreTake(int m,int t){(void)m;(void)t;return true;}
static void xSemaphoreGive(int m){(void)m;assert(!handler_active);}
static uint32_t esp_timer_get_time(void){static uint32_t us;return us+=100;}
static void lv_timer_handler(void){assert(priority==1);handler_active=true;handler_calls++;handler_active=false;}
static void cym_diag_handler(void *d,uint32_t time,uint32_t cb){(void)d;(void)time;(void)cb;}
static bool doom_ui_native_takeover(bool drained){assert(drained&&!handler_active);takeovers++;return handler_calls>=2;}
static int esp_timer_stop(int t){(void)t;return 0;}
static void vTaskPrioritySet(void *t,unsigned p){(void)t;assert(!handler_active&&p==3&&handler_calls==2);priority=p;}
static unsigned uxTaskPriorityGet(void *t){(void)t;return priority;}
static void doom_ui_native_step(void){assert(priority==3&&!handler_active);native_calls++;}
static void cym_display_diag_report(void){}
static void esp_task_wdt_reset(void){}
static void vTaskDelay(unsigned ticks){assert(ticks>0);blocks++;pcm_steps++;engine_steps++;if(blocks==20)longjmp(finish,1);}
static void run(void){
"""+loop+r"""
}
int main(void){if(!setjmp(finish))run();assert(handler_calls==2&&native_calls==18&&priority==3&&engine_steps==20&&pcm_steps==20);puts("actual isolated loop: safe-boundary local priority3, PCM unchanged, positive blocking on no-frame/cleanup loops PASS");}
"""
  out=Path('/home/dev/ws-c5-35-fixes/cycle90/host');(out/'native-loop.c').write_text(code)
  r=subprocess.run(['cc','-std=c11','-O1','-I'+str(ROOT/'ESP32C5/components/cym_doom/include'),str(out/'native-loop.c'),'-o',str(out/'native-loop')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(out/'native-loop')],capture_output=True,text=True);(out/'native-loop.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_actual_native_board_poll_no_frame_two_points_fault_and_boot(self):
  source=(ROOT/'ESP32C5/main/main.c').read_text();start=source.index('static uint32_t s_native_input_ms;');end=source.index('#include "isolated_native_panel.h"',start)
  poll=source[start:end]
  code=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "doom_contracts.h"
#define CONFIG_BOARD_WS_C5_35 1
#define LCD_H_RES 320
#define LCD_V_RES 480
#define BOOT_BTN_GPIO 0
static uint32_t ms;static unsigned keys,reads,boots;static bool fault,boot_down,exit_requested;
static unsigned contacts=2;static bool touch_exit;
static uint32_t esp_timer_get_time(void){return ms*1000;}
static int gpio_get_level(int pin){(void)pin;return !boot_down;}
static bool ws_c5_35_touch_read_points(uint16_t *x,uint16_t *y,uint8_t *n,uint8_t cap){
 assert(cap==2);reads++;if(fault)return false;*n=contacts;
 /* native -> logical (480x320): (50,90) pad and (410,100) Fire */
 x[0]=touch_exit?5:229;y[0]=touch_exit?420:50;x[1]=219;y[1]=410;return true;
}
static bool doom_ui_touch_snapshot(const int *x,const int *y,unsigned n){keys=doom_game_touch_keys(doom_game_layout_make(480,320),x,y,n);if(keys&DOOM_KEY_EXIT)exit_requested=true;return true;}
static void doom_ui_boot_fire(bool b){boots++;assert(b==boot_down);}
static bool doom_ui_native_accepting(void){return !exit_requested;}
"""+poll+r"""
int main(void){ms=10;assert(game_native_poll(NULL));assert(reads==1&&boots==1&&(keys&DOOM_KEY_FORWARD)&&(keys&DOOM_KEY_FIRE));
 ms=11;game_native_poll(NULL);assert(reads==1);contacts=1;ms=20;game_native_poll(NULL);assert(!(keys&DOOM_KEY_FIRE)&&(keys&DOOM_KEY_FORWARD));
 fault=true;boot_down=true;ms=30;game_native_poll(NULL);assert(keys==0&&boots==3);
 fault=false;touch_exit=true;ms=40;assert(!game_native_poll(NULL));assert(keys&DOOM_KEY_EXIT);puts("actual native board input: independent timed poll/270 mapping/two contacts/partial releases/fault/BOOT PASS");}
"""
  out=Path('/home/dev/ws-c5-35-fixes/cycle90/host');(out/'native-input.c').write_text(code)
  r=subprocess.run(['cc','-std=c11','-O1','-fsanitize=undefined','-I'+str(ROOT/'ESP32C5/components/cym_doom/include'),str(out/'native-input.c'),str(ROOT/'ESP32C5/components/cym_doom/doom_contracts.c'),'-o',str(out/'native-input')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(out/'native-input')],capture_output=True,text=True);(out/'native-input.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  ws28=(code.replace('#define CONFIG_BOARD_WS_C5_35 1','#define CONFIG_BOARD_WS_C5_35 0')
   .replace('#define LCD_H_RES 320','#define LCD_H_RES 240')
   .replace('#define LCD_V_RES 480','#define LCD_V_RES 320')
   .replace('doom_game_layout_make(480,320)','doom_game_layout_make(320,240)')
   .replace('x[0]=touch_exit?5:229;y[0]=touch_exit?420:50;x[1]=219;y[1]=410;','x[0]=touch_exit?5:179;y[0]=touch_exit?280:50;x[1]=159;y[1]=280;'))
  inject='static void *touch_handle;\n#define ESP_OK 0\nstatic int esp_lcd_touch_read_data(void *p){(void)p;return fault?1:0;}\nstatic bool esp_lcd_touch_get_coordinates(void *p,uint16_t *x,uint16_t *y,void *z,uint8_t *n,uint8_t cap){(void)p;(void)z;return ws_c5_35_touch_read_points(x,y,n,cap); }\n'
  idx=ws28.index('static uint32_t s_native_input_ms;');ws28=ws28[:idx]+inject+ws28[idx:]
  (out/'native-input-ws28.c').write_text(ws28)
  r=subprocess.run(['cc','-std=c11','-O1','-I'+str(ROOT/'ESP32C5/components/cym_doom/include'),str(out/'native-input-ws28.c'),str(ROOT/'ESP32C5/components/cym_doom/doom_contracts.c'),'-o',str(out/'native-input-ws28')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(out/'native-input-ws28')],capture_output=True,text=True);(out/'native-input-ws28.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
