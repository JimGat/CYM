"""GPIO28-only WS-C5-35 receive route and exclusive pin ownership."""
from pathlib import Path
import subprocess,tempfile,unittest,re
ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'ESP32C5/main/main.c'
BASE='0ae3ce22081d2ddf85e78dc6ec1c425977348cf3'
def function(source,signature):
 start=re.search(re.escape(signature)+r'\s*\{',source).start(); a=source.index('{',start); depth=0
 for i in range(a,len(source)):
  if source[i]=='{':depth+=1
  elif source[i]=='}':
   depth-=1
   if not depth:return source[start:i+1]
 raise AssertionError(signature)
class Cycle99Gps(unittest.TestCase):
 def test_compiled_profile_and_uart_init_only_touch_gpio28(self):
  source=MAIN.read_text(); init=function(source,'static esp_err_t init_gps_uart(void)')
  boot=function(source,'static void init_boot_button(void)')
  button=function(source,'static bool game_boot_button_pressed(void)')
  header=ROOT/'ESP32C5/components/board_hal/include'
  prelude=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "board_hal.h"
_Static_assert(BOARD_GPS_RX_GPIO==28 && BOARD_GPS_TX_GPIO==-1,"GPIO28 RX-only");
_Static_assert(BOARD_BOOT_BTN_GPIO==-1,"no BOOT/GPS pin sharing");
#define CONFIG_BOARD_HAS_GPS 1
#define BOOT_BTN_GPIO BOARD_BOOT_BTN_GPIO
#define GPS_TX_PIN BOARD_GPS_TX_GPIO
#define GPS_RX_PIN BOARD_GPS_RX_GPIO
#define GPS_UART_NUM BOARD_GPS_UART_NUM
#define ESP_OK 0
#define ESP_ERR_INVALID_ARG 0x102
#define UART_PIN_NO_CHANGE -1
#define GPIO_MODE_INPUT 1
#define UART_DATA_8_BITS 8
#define UART_PARITY_DISABLE 0
#define UART_STOP_BITS_1 1
#define UART_HW_FLOWCTRL_DISABLE 0
#define UART_SCLK_DEFAULT 0
#define GPS_BUF_SIZE 4096
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
typedef int esp_err_t;
typedef struct {int baud_rate,data_bits,parity,stop_bits,flow_ctrl,source_clk;} uart_config_t;
typedef struct {uint64_t pin_bit_mask;int mode,pull_up_en,pull_down_en,intr_type;} gpio_config_t;
static const char *TAG="test";
static int deletes;
static int g_wd_gps_baud=9600,s_gps_applied_baud,call,fail_at,gpio_reads;
static void gps_load_baud_setting(void){if(g_wd_gps_baud!=9600 && g_wd_gps_baud!=115200)g_wd_gps_baud=9600;}
static int uart_driver_delete(int n){assert(n==1);deletes++;return ESP_OK;}
static int rc(void){return ++call==fail_at?ESP_ERR_INVALID_ARG:ESP_OK;}
static int gpio_reset_pin(int pin){assert(pin==28);return rc();}
static int gpio_set_direction(int pin,int mode){assert(pin==28 && mode==GPIO_MODE_INPUT);return rc();}
static int gpio_get_level(int pin){assert(pin==28);gpio_reads++;return 0;}
static int gpio_config(const gpio_config_t *p){(void)p;assert(0);return ESP_OK;}
static int gpio_hold_dis(int pin){(void)pin;assert(0);return ESP_OK;}
static int gpio_sleep_sel_dis(int pin){(void)pin;assert(0);return ESP_OK;}
static int uart_param_config(int n,const uart_config_t *p){assert(n==1 && p->baud_rate==g_wd_gps_baud && p->data_bits==8 && p->flow_ctrl==0);return rc();}
static int uart_set_pin(int n,int tx,int rx,int rts,int cts){assert(n==1 && tx==-1 && rx==28 && rts==-1 && cts==-1);return rc();}
static int uart_driver_install(int n,int rx,int tx,int q,void *h,int flags){assert(n==1 && rx>0 && tx==0 && q==0 && h==NULL && flags==0);return rc();}
"""
  exercise=r"""
int main(void){
 init_boot_button();assert(gpio_reads==0 && call==0);
 assert(!game_boot_button_pressed());assert(gpio_reads==0);
 for(int b=0;b<3;b++){
  g_wd_gps_baud=(int[]){9600,115200,1234}[b];fail_at=0;call=0;deletes=0;
  assert(init_gps_uart()==ESP_OK);assert(call==5 && deletes==0);
  assert(s_gps_applied_baud==(b==1?115200:9600));
 }
 for(fail_at=1;fail_at<=5;fail_at++){
  call=0;deletes=0;
  assert(init_gps_uart()==ESP_ERR_INVALID_ARG);assert(call==fail_at && deletes==(fail_at>=4));
 }
 puts("PRODUCTION_WS35_GPIO28_ONLY_PASS success/five-error-stages/cleanup/BOOT-inactive");
 return 0;
}
"""
  with tempfile.TemporaryDirectory() as d:
   tmp=Path(d);(tmp/'sdkconfig.h').write_text('#define CONFIG_BOARD_WS_C5_35 1\n')
   c=tmp/'probe.c';c.write_text(prelude+'\n'+boot+'\n'+button+'\n'+init+'\n'+exercise)
   p=subprocess.run(['cc','-std=c11','-I'+d,'-I'+str(header),str(c),'-o',str(tmp/'probe')],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
   p=subprocess.run([str(tmp/'probe')],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr);self.assertIn('PRODUCTION_WS35_GPIO28_ONLY_PASS',p.stdout)
 def test_ws35_has_no_alternate_pin_or_transmit_probe(self):
  init=function(MAIN.read_text(),'static esp_err_t init_gps_uart(void)')
  ws=init[init.index('#if defined(CONFIG_BOARD_WS_C5_35)'):init.index('#elif defined(CONFIG_BOARD_CYD2USB)')]
  self.assertNotIn('routes[]',ws);self.assertNotIn('gps_classic_attach_rx',ws)
  self.assertNotIn('gpio_reset_pin(GPS_TX_PIN)',ws);self.assertNotIn('gpio_set_direction(GPS_TX_PIN',ws)
  self.assertEqual(ws.count('gpio_reset_pin('),1);self.assertEqual(ws.count('uart_set_pin('),1)
  self.assertNotIn('uart_write_bytes',ws)
 def test_non_ws35_gps_initialization_unchanged(self):
  old=subprocess.check_output(['git','show',BASE+':ESP32C5/main/main.c'],cwd=ROOT,text=True)
  def other(s):
   f=function(s,'static esp_err_t init_gps_uart(void)');a=f.index('#if defined(CONFIG_BOARD_WS_C5_35)');b=f.index('#elif defined(CONFIG_BOARD_CYD2USB)',a)
   # The sole Classic addition is an early ownership guard; other init code stays byte-identical.
   guard='#if defined(CONFIG_BOARD_CYD2USB)\n    if (cym_classic_usb_gps_blocked()) return ESP_ERR_INVALID_STATE;\n#endif\n'
   return (f[:a]+f[b:]).replace(guard,'')
  self.assertEqual(other(old),other(MAIN.read_text()))
  for name in ['ws_c5_28','nm_cyd_c5','pancake_c5','cyd2usb','hosyond_s3_35','ws_s3_5b']:
   rel=f'ESP32C5/components/board_hal/include/boards/{name}.h'
   self.assertEqual(subprocess.check_output(['git','show',BASE+':'+rel],cwd=ROOT),(ROOT/rel).read_bytes(),rel)
 def test_game_paths_use_guarded_button_not_gpio28_nmea(self):
  m=MAIN.read_text();game=m[m.index('static game_read game_nvs_read'):m.index('static void app_main',m.index('static game_read game_nvs_read'))] if 'static void app_main' in m else m[m.index('static game_read game_nvs_read'):m.index('void app_main',m.index('static game_read game_nvs_read'))]
  self.assertNotIn('gpio_get_level(BOOT_BTN_GPIO)',game)
  self.assertEqual(m.count('doom_ui_boot_fire(game_boot_button_pressed())'),2)
  self.assertIn('bool held=game_boot_button_pressed();',m)
if __name__=='__main__':unittest.main()
