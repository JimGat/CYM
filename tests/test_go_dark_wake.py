"""Compile the actual Go Dark polling/copy snippets for every touch backend."""
from pathlib import Path
import os, re, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'ESP32C5/main/main.c'

def block(text,start):
    a=text.index('{',start); depth=1; i=a+1
    while depth:
        depth+=(text[i]=='{')-(text[i]=='}'); i+=1
    return text[a:i]

def run_c(src,defines=()):
    with tempfile.TemporaryDirectory(dir=os.environ.get('CYM_WD_TEST_TMPDIR')) as d:
        p=Path(d);(p/'test.c').write_text(src)
        result=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable',*[f'-D{x}' for x in defines],str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stderr[-5000:])
        result=subprocess.run([str(p/'test')],capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stderr[-3000:])

STUBS=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
static int64_t clock_ms;
static bool finger,read_ok=true,ignore_touch_until_release;
static int wakes,reads;
static void *touch_handle;
static int64_t esp_timer_get_time(void){return clock_ms*1000;}
static void go_dark_disable(void){wakes++;}
static bool read_point(uint16_t *x,uint16_t *y,bool *touched){reads++;*x=123;*y=234;*touched=read_ok&&finger;return read_ok;}
static bool ws_c5_35_touch_read(uint16_t*x,uint16_t*y,bool*t){return read_point(x,y,t);}
static bool pancake_c5_touch_read(uint16_t*x,uint16_t*y,bool*t){return read_point(x,y,t);}
static bool ws_s3_5b_touch_read(uint16_t*x,uint16_t*y,bool*t){return read_point(x,y,t);}
static bool hosyond_s3_35_touch_read(uint16_t*x,uint16_t*y,bool*t){return read_point(x,y,t);}
typedef struct {bool touched;} xpt2046_touch_point_t;
static bool xpt2046_read_touch(void *h,xpt2046_touch_point_t*p){(void)h;reads++;p->touched=read_ok&&finger;return read_ok;}
static int esp_lcd_touch_read_data(void *h){(void)h;reads++;return read_ok?0:-1;}
static bool esp_lcd_touch_get_coordinates(void*h,uint16_t*x,uint16_t*y,void*z,uint8_t*n,int max){(void)h;(void)z;(void)max;*x=123;*y=234;*n=read_ok&&finger;return *n>0;}
"""
HOLD=r"""
int main(void){
 finger=false;clock_ms=100;poll_touch();assert(wakes==0);
 finger=true;clock_ms=200;poll_touch();clock_ms=5199;poll_touch();assert(wakes==0);
 clock_ms=5200;poll_touch();assert(wakes==1);assert(reads==4);
 /* A fresh session requires a fresh five-second hold. */
 finger=false;clock_ms=5300;poll_touch();finger=true;clock_ms=5400;poll_touch();
 clock_ms=10399;poll_touch();assert(wakes==1);clock_ms=10400;poll_touch();assert(wakes==2);
 /* Releasing or failing a read resets an incomplete hold. */
 finger=false;clock_ms=10500;poll_touch();finger=true;clock_ms=10600;poll_touch();
 clock_ms=15000;poll_touch();read_ok=false;clock_ms=15100;poll_touch();
 read_ok=true;clock_ms=15200;poll_touch();clock_ms=20199;poll_touch();assert(wakes==2);
 finger=false;clock_ms=20200;poll_touch();finger=true;clock_ms=20300;poll_touch();
 clock_ms=25299;poll_touch();assert(wakes==2);clock_ms=25300;poll_touch();assert(wakes==3);
 return 0;
}
"""
class GoDarkWake(unittest.TestCase):
    def touch(self):
        t=MAIN.read_text();return block(t,t.index('/* Touch-to-wake:'))
    def test_ws35_real_polling_continuous_hold_release_and_read_failure(self):
        run_c(STUBS+'\nstatic void poll_touch(void)'+self.touch()+HOLD,['CONFIG_BOARD_WS_C5_35=1'])
    def test_other_touch_backends_keep_five_second_wake(self):
        for flag in ['CONFIG_BOARD_TOUCH_XPT2046','CONFIG_BOARD_PANCAKE_C5','CONFIG_BOARD_WS_S3_5B','CONFIG_BOARD_HOSYOND_S3_35','CONFIG_BOARD_TOUCH_CST3530']:
            with self.subTest(flag=flag):run_c(STUBS+'\nstatic void poll_touch(void)'+self.touch()+HOLD,[flag+'=1'])
    def test_ws35_wake_finger_cannot_activate_underlying_control(self):
        t=MAIN.read_text();i=t.index('if (ignore_touch_until_release)',t.index('void lvgl_touch_read_cb(lv_indev_drv_t *indev_drv, lv_indev_data_t *data)\n{'))
        guard='if (ignore_touch_until_release)'+block(t,i)
        src=STUBS+'\nstatic void poll_touch(void)'+self.touch()+r"""
#define LV_INDEV_STATE_RELEASED 0
static bool touch_pressed_flag;
struct data_t {int state;};
static void input(bool touched,struct data_t *data){
"""+guard+r"""
 data->state=touched?1:0;
}
int main(void){finger=true;clock_ms=100;poll_touch();clock_ms=5100;poll_touch();assert(wakes==1);assert(ignore_touch_until_release);
 struct data_t d={1};input(true,&d);assert(d.state==0&&ignore_touch_until_release);
 input(false,&d);assert(d.state==0&&!ignore_touch_until_release);input(true,&d);assert(d.state==1);return 0;}
"""
        run_c(src,['CONFIG_BOARD_WS_C5_35=1'])
    def test_wake_copy_follows_actual_boot_availability(self):
        t=MAIN.read_text();a=t.index('lv_obj_t *hint = lv_label_create(card);',t.index('static void show_go_dark_confirm(void)\n{'));b=t.index('lv_obj_set_style_text_color(hint',a)
        snippet=t[a:b]
        for pin in [-1,0,28]:
            with self.subTest(pin=pin):
                run_c('#include <assert.h>\n#include <string.h>\ntypedef int lv_obj_t;static int obj;static const char *copy;static lv_obj_t *lv_label_create(void*p){(void)p;return &obj;}static void lv_label_set_text(lv_obj_t*p,const char*s){(void)p;copy=s;}\nint main(void){void *card=0;'+snippet+'assert(strstr(copy,"Hold screen 5 seconds"));assert((strstr(copy,"BOOT")!=0)==(BOOT_BTN_GPIO>=0));return 0;}',[f'BOOT_BTN_GPIO={pin}'])
    def test_ws35_gps_ownership_and_no_boot_gpio_configuration(self):
        t=(ROOT/'ESP32C5/components/board_hal/include/boards/ws_c5_35.h').read_text()
        self.assertRegex(t,r'#define BOARD_BOOT_BTN_GPIO\s+-1\b');self.assertRegex(t,r'#define BOARD_GPS_RX_GPIO\s+28\b');self.assertRegex(t,r'#define BOARD_GPS_TX_GPIO\s+-1\b')
        t=MAIN.read_text();a=t.index('static void init_boot_button(void)\n{');b=t.index('void go_dark_enable(void)\n{',a)
        self.assertIn('#if BOOT_BTN_GPIO >= 0',t[a:b]);self.assertIn('gpio_config(&cfg);',t[a:b])
    def test_both_menu_layouts_reuse_confirmation(self):
        t=MAIN.read_text();self.assertIn('lv_obj_add_event_cb(home_dark_btn, go_dark_mini_btn_cb',t);self.assertIn('lv_obj_add_event_cb(dark_btn, go_dark_mini_btn_cb',t)
        self.assertRegex(t,re.compile(r'static void go_dark_mini_btn_cb\([^)]*\)\s*\{.*?show_go_dark_confirm\(\);',re.S))
        self.assertRegex(t,re.compile(r'strcmp\(tile_name, "Go Dark"\).*?show_go_dark_confirm\(\);',re.S))
if __name__=='__main__':unittest.main()
