from pathlib import Path
import unittest
import test_revision91 as helpers
ROOT=helpers.ROOT
class Targeted92(unittest.TestCase):
 extract=helpers.Revision91.extract
 run_c=helpers.Revision91.run_c
 def test_ws35_init_output_direction(self):
  s=(ROOT/'ESP32C5/main/ws_c5_35_port.c').read_text()
  a=s.index('    uint16_t mode =');b=s.index('    ESP_RETURN_ON_ERROR(ws35_exio_write16',a)
  self.run_c('init-direction92',r"""#include <stdint.h>
#include <assert.h>
#define BOARD_TOUCH_RESET_EXIO 0
#define BOARD_LCD_RESET_EXIO 1
#define BOARD_POWER_ENABLE_EXIO 5
int main(void){
"""+s[a:b]+r"""assert(mode==0x23);assert(!(mode&(1u<<6)));return 0;}""")
 def test_ws35_exact_protocol_and_drive(self):
  fn=self.extract((ROOT/'ESP32C5/main/ws_c5_35_port.c').read_text(),'bool ws_c5_35_audio_amp(bool on)')
  self.run_c('amp-protocol92',r"""#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stddef.h>
#define ESP_OK 0
#define ESP_LOGI(...) ((void)0)
#define WS35_EXIO_REG_OUTPUT 3
#define BOARD_POWER_ENABLE_EXIO 5
typedef int esp_err_t;
static void*s_exio_dev=(void*)1;static uint16_t mode_shadow=0x23,output_shadow=0xa5c3;
static int write_fail,read_fail,mismatch,writes,reads;static uint16_t hardware;
int i2c_master_transmit(void*h,const uint8_t*p,size_t n,int timeout){assert(h&&n==3&&p[0]==3&&timeout==100);writes++;if(write_fail)return -1;hardware=p[1]|(p[2]<<8);return 0;}
int i2c_master_transmit_receive(void*h,const uint8_t*p,size_t n,uint8_t*out,size_t len,int timeout){assert(h&&n==1&&p[0]==4&&len==2&&timeout==100);reads++;if(read_fail)return -1;uint16_t sensed=(hardware&mode_shadow)^(mismatch?32:0);out[0]=sensed&255;out[1]=sensed>>8;return 0;}
"""+fn+r"""
int main(void){uint16_t keep=output_shadow&~32;assert(ws_c5_35_audio_amp(false));assert((output_shadow&~32)==keep);assert(ws_c5_35_audio_amp(true));assert((output_shadow&~32)==keep&&(hardware&32));uint16_t before=output_shadow;int rc=reads;write_fail=1;assert(!ws_c5_35_audio_amp(false)&&output_shadow==before&&reads==rc);write_fail=0;read_fail=1;assert(!ws_c5_35_audio_amp(false)&&!(output_shadow&32));read_fail=0;mismatch=1;assert(!ws_c5_35_audio_amp(true));mismatch=0;assert(ws_c5_35_audio_amp(false));int count=writes;mode_shadow&=~32;assert(!ws_c5_35_audio_amp(true)&&writes==count);mode_shadow|=32;s_exio_dev=0;assert(!ws_c5_35_audio_amp(true)&&writes==count);return 0;}
""")
 def test_home_does_not_write_gps_uart(self):
  fn=self.extract((ROOT/'ESP32C5/main/main.c').read_text(),'static void home_btn_event_cb(lv_event_t *e)\n{')
  for board in ['CONFIG_BOARD_WS_C5_35','CONFIG_BOARD_WS_C5_28','CONFIG_BOARD_CYD2USB','CONFIG_BOARD_NM_CYD_C5','CONFIG_BOARD_HOSYOND_S3_35','CONFIG_BOARD_PANCAKE_C5','CONFIG_BOARD_HACKERBOX_CYD','CONFIG_BOARD_WS_S3_5B']:
   self.run_c('home-'+board,r"""#include <stdbool.h>
#include <assert.h>
#include <string.h>
#define ESP_LOGI(...) ((void)0)
#define GPS_UART_NUM 1
#define """+board+r""" 1
typedef int lv_event_t;static bool nav_to_menu_flag;static unsigned writes;
int uart_write_bytes(int port,const char*p,unsigned n){(void)port;(void)p;(void)n;writes++;return -1;}
"""+fn+r"""
int main(void){home_btn_event_cb(0);assert(nav_to_menu_flag&&writes==0);return 0;}
""")
 def test_ui_work_units_and_window_reset(self):
  code='#include "'+str(ROOT/'ESP32C5/main/ui_diagnostics.h')+'"\n'
  code+=r"""#include <assert.h>
int main(void){cym_ui_diag d={0};cym_ui_diag_work_add(@d,CYM_UI_INVALIDATE,4800);cym_ui_diag_work_add(@d,CYM_UI_INVALIDATE,21);cym_ui_diag_work_add(@d,CYM_UI_COVER_VISIT,1);cym_ui_diag_work_add(@d,CYM_UI_DRAW_VISIT,1);
assert(d.work_window[0].count==2@@d.work_window[0].units==4821@@d.work_window[0].max_units==4800);assert(d.work_total[0].units==4821);cym_ui_diag_reset_window(@d);assert(!d.work_window[0].count@@d.work_total[0].count==2);cym_ui_diag_work_add(@d,CYM_UI_INVALIDATE,7);assert(d.work_window[0].max_units==7@@d.work_total[0].max_units==4800);cym_ui_diag_work_add(@d,CYM_UI_WORK_KINDS,999);assert(!d.window[0].count);return 0;}
""".replace('@',chr(38))
  self.run_c('ui-work92',code)
 def test_production_reporter_work_names_and_elapsed(self):
  fn=self.extract((ROOT/'ESP32C5/main/main.c').read_text(),'static void cym_ui_diag_report(void)')
  code='#include "'+str(ROOT/'ESP32C5/main/ui_diagnostics.h')+'"\n'
  code+=r"""#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <inttypes.h>
#include <stdarg.h>
static cym_ui_diag s_ui_diag;static uint64_t now_us;static unsigned lines;
static bool cym_debug_enabled(void){return true;}
static uint32_t cym_debug_generation(void){return 0;}
static void cym_ui_diag_transition(void){}
#define TAG "test"
static uint64_t esp_timer_get_time(void){return now_us;}
static void log_line(const char*tag,const char*fmt,...){(void)tag;char b[1000];va_list ap;va_start(ap,fmt);vsnprintf(b,sizeof(b),fmt,ap);va_end(ap);assert(!strstr(b,"(null)"));lines++;}
#define ESP_LOGI log_line
"""+fn+r"""
int main(void){for(unsigned i=0;i<CYM_UI_KINDS;i++)cym_ui_diag_add(@s_ui_diag,i,1);for(unsigned i=0;i<CYM_UI_WORK_KINDS;i++)cym_ui_diag_work_add(@s_ui_diag,i,7);now_us=9000000;cym_ui_diag_report();assert(lines==CYM_UI_KINDS+CYM_UI_WORK_KINDS);assert(!s_ui_diag.work_window[0].count);now_us+=1000;cym_ui_diag_report();assert(lines==CYM_UI_KINDS+CYM_UI_WORK_KINDS);return 0;}
""".replace('@',chr(38))
  self.run_c('report92',code)
if __name__=='__main__':unittest.main()
