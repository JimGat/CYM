"""Execute WS-C5-28 production monitor: unknown visible, contention retry."""
from pathlib import Path
import unittest
from test_cycle84_dma_timekeeper import exercise,function
ROOT=Path(__file__).resolve().parents[1]
class BatteryVisibility(unittest.TestCase):
 def test_ws28_unknown_and_contended_publication(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text()
  body=function(s,'static void battery_monitor_task(void *arg)\n{')
  pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <setjmp.h>
#define CONFIG_BOARD_WS_C5_28 1
#define BOARD_BATTERY_VIA_EXPANDER 1
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
#define BATTERY_TIMER_INIT_RETRIES 5
#define BATTERY_TIMER_RETRY_DELAY_MS 200
#define BATTERY_UPDATE_INTERVAL_MS 10000
#define BATTERY_VOLTAGE_CRITICAL 2.0f
#define BATTERY_VOLTAGE_FULL 4.15f
#define BATTERY_PCT_LOW 25
#define BATTERY_PCT_MID 65
#define BATTERY_PCT_CRITICAL 10
#define BATTERY_COLOR_FULL 1
#define BATTERY_COLOR_MID 2
#define BATTERY_COLOR_LOW 3
#define LV_SYMBOL_BATTERY_EMPTY "E"
#define LV_SYMBOL_BATTERY_1 "1"
#define LV_SYMBOL_BATTERY_2 "2"
#define LV_SYMBOL_BATTERY_3 "3"
#define LV_SYMBOL_BATTERY_FULL "F"
#define LV_OBJ_FLAG_HIDDEN 1
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
typedef int lv_color_t;
static char last_voltage_str[32];static lv_color_t last_batt_color;
static bool batt_color_valid,batt_is_critical,batt_blink_phase,hidden;
static void *lvgl_mutex=(void*)1,*battery_label=(void*)2;
static int locks,failures;static bool sampling;static float sample;
static jmp_buf done;
static void vTaskDelay(int ms){if(ms==BATTERY_UPDATE_INTERVAL_MS)longjmp(done,1);}
static bool battery_ensure_blink_timer_locked(void){return true;}
static int xSemaphoreTake(void*m,int t){(void)m;(void)t;if(sampling){locks++;if(failures){failures--;return 0;}}return 1;}
static void xSemaphoreGive(void*m){(void)m;}
static float read_battery_voltage(void){sampling=true;return sample;}
static int battery_pct_from_voltage(float v){(void)v;return 80;}
static bool lv_obj_is_valid(void*p){return p!=NULL;}
static void lv_obj_add_flag(void*p,int f){(void)p;(void)f;hidden=true;}
static void lv_obj_clear_flag(void*p,int f){(void)p;(void)f;hidden=false;}
static void lv_label_set_text(void*p,const char*s){(void)p;assert(*s);}
static void lv_obj_set_style_text_color(void*p,int c,int sel){(void)p;(void)c;(void)sel;}
"""
  post=r"""
int main(void){
 for(int mode=0;mode<3;mode++){
  sample=mode==0?0.0f:4.0f;sampling=false;locks=0;failures=mode==2?10:0;last_voltage_str[0]=0;hidden=true;
  if(!setjmp(done))battery_monitor_task(NULL);
  assert(!hidden&&batt_color_valid&&last_voltage_str[0]);
  if(mode==0)assert(!strcmp(last_voltage_str,"BAT ?")&&!batt_is_critical);
  else assert(strstr(last_voltage_str,"80%"));
  if(mode==2)assert(locks>=11);
 }
 puts("WS28 production monitor: unknown stays visible, valid estimate, contended publication retries PASS");}
"""
  exercise('cycle85-battery',pre+body+post)
if __name__=='__main__':unittest.main()
