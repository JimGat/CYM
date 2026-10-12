from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
class TouchDriver(unittest.TestCase):
 def test_production_ft6336_snapshot(self):
  out=ROOT/'.hermes/cycle81/touch';out.mkdir(parents=True,exist_ok=True)
  stub=r"""
#pragma once
#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#define CONFIG_ESP_LCD_TOUCH_MAX_POINTS 2
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NO_MEM -2
#define MALLOC_CAP_DEFAULT 0
#define GPIO_NUM_NC -1
#define GPIO_MODE_INPUT 0
#define GPIO_MODE_OUTPUT 1
#define GPIO_INTR_POSEDGE 1
#define GPIO_INTR_NEGEDGE 0
#define BIT64(x) (1ull<<(x))
#define portMUX_FREE_VAL 0
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
#define pdMS_TO_TICKS(x) (x)
#define ESP_LOGE(...) ((void)0)
#define ESP_RETURN_ON_FALSE(c,e,...) do{if(!(c))return e;}while(0)
#define ESP_RETURN_ON_ERROR(c,...) do{int e=(c);if(e)return e;}while(0)
#define ESP_GOTO_ON_ERROR(c,label,...) do{if(c)goto label;}while(0)
typedef int esp_err_t;
typedef void *esp_lcd_panel_io_handle_t;
typedef struct {int mode,intr_type;uint64_t pin_bit_mask;} gpio_config_t;
typedef struct {int int_gpio_num,rst_gpio_num;struct{int interrupt,reset;}levels;void(*interrupt_callback)(void*);} esp_lcd_touch_config_t;
typedef struct touch *esp_lcd_touch_handle_t;
typedef struct touch {void*io;esp_err_t(*read_data)(struct touch*);bool(*get_xy)(struct touch*,uint16_t*,uint16_t*,uint16_t*,uint8_t*,uint8_t);esp_err_t(*del)(struct touch*);esp_lcd_touch_config_t config;struct{struct{int owner;}lock;uint8_t points;struct{uint16_t x,y,strength;}coords[2];}data;} esp_lcd_touch_t;
static inline void*heap_caps_calloc(size_t n,size_t s,int caps){(void)caps;return calloc(n,s);}
static inline int gpio_config(const gpio_config_t*c){(void)c;return 0;}
static inline void gpio_set_level(int p,int v){(void)p;(void)v;}
static inline void gpio_reset_pin(int p){(void)p;}
static inline void vTaskDelay(int n){(void)n;}
static inline void esp_lcd_touch_register_interrupt_callback(void*t,void(*f)(void*)){(void)t;(void)f;}
int esp_lcd_panel_io_rx_param(void*,int,void*,size_t);
"""
  (out/'stub.h').write_text(stub)
  for n in ['esp_lcd_touch_ft6336.h','esp_err.h','esp_log.h','esp_check.h','esp_lcd_panel_io.h','esp_lcd_touch.h','freertos/FreeRTOS.h','freertos/task.h','driver/gpio.h']:
   p=out/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#include "stub.h"\n')
  (out/'case.c').write_text(r"""
#include "stub.h"
#include "esp_lcd_touch_ft6336.c"
static uint8_t count,packet[12];static int failed;
int esp_lcd_panel_io_rx_param(void*p,int reg,void*out,size_t n){(void)p;if(failed)return -1;if(reg==2){assert(n==1);*(uint8_t*)out=count;}else{assert(reg==3&&n<=12);memcpy(out,packet,n);}return 0;}
int main(void){esp_lcd_touch_t t={0};uint16_t x[2],y[2];uint8_t n;
count=2;packet[0]=0x00;packet[1]=21;packet[2]=0;packet[3]=42;packet[6]=0x80;packet[7]=99;packet[8]=0;packet[9]=88;
assert(!ft6336_read_data(&t));assert(ft6336_get_xy(&t,x,y,0,&n,2)&&n==2&&x[0]==21&&y[0]==42&&x[1]==99&&y[1]==88);
assert(!ft6336_get_xy(&t,x,y,0,&n,2)&&n==0);
assert(!ft6336_read_data(&t));assert(ft6336_get_xy(&t,x,y,0,&n,1)&&n==1&&x[0]==21);
assert(!ft6336_read_data(&t));count=0;assert(!ft6336_read_data(&t));assert(!ft6336_get_xy(&t,x,y,0,&n,2)&&n==0);
count=2;assert(!ft6336_read_data(&t));failed=1;assert(ft6336_read_data(&t));assert(!ft6336_get_xy(&t,x,y,0,&n,2));failed=0;
packet[0]=0x40;assert(!ft6336_read_data(&t));assert(ft6336_get_xy(&t,x,y,0,&n,2)&&n==1&&x[0]==99);
return 0;}
""")
  exe=out/'case';r=subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-unused-variable','-fsanitize=address,undefined','-I'+str(out),'-I'+str(ROOT/'ESP32C5/components/esp_lcd_touch_ft6336'),str(out/'case.c'),'-o',str(exe)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(exe)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)

 def test_non_ws35_production_adapter_stub(self):
  out=ROOT/'.hermes/cycle81/stub';out.mkdir(parents=True,exist_ok=True)
  (out/'sdkconfig.h').write_text('/* non-WS35 build */\n')
  (out/'esp_err.h').write_text('#include <stddef.h>\ntypedef int esp_err_t;\n#define ESP_ERR_NOT_SUPPORTED -1\n')
  (out/'esp_lcd_panel_io.h').write_text('typedef void* esp_lcd_panel_io_handle_t;\n')
  (out/'esp_lcd_panel_ops.h').write_text('typedef void* esp_lcd_panel_handle_t;\n')
  (out/'driver').mkdir(exist_ok=True)
  (out/'driver/i2c_master.h').write_text('typedef void* i2c_master_bus_handle_t;\n')
  (out/'case.c').write_text('#include "ws_c5_35_port.c"\n#include <assert.h>\nint main(void){uint16_t x[2]={0},y[2]={0};uint8_t n=9;assert(!ws_c5_35_touch_read_points(x,y,&n,2)&&n==0);return 0;}\n')
  exe=out/'case'
  r=subprocess.run(['cc','-Wall','-Wextra','-Werror','-I'+str(out),'-I'+str(ROOT/'ESP32C5/main'),str(out/'case.c'),'-o',str(exe)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(exe)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
