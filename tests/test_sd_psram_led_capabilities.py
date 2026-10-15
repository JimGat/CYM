"""Capability gates and real Classic RGB backend host regression checks."""
from pathlib import Path
import os, re, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'ESP32C5/main/main.c'

def body(text, name):
    m = re.search(r'\b' + re.escape(name) + r'\([^;{}]*\)\s*\{', text)
    if not m: raise AssertionError('missing production function: ' + name)
    start = m.end(); depth = 1; i = start
    while depth:
        if text[i] == '{': depth += 1
        elif text[i] == '}': depth -= 1
        i += 1
    return text[start:i-1]

class SdPsramCapabilities(unittest.TestCase):
    def test_runtime_psram_not_board_name_or_free_heap(self):
        b = body(MAIN.read_text(), 'sd_auto_provision_available')
        self.assertNotIn('CONFIG_BOARD_', b)
        self.assertNotIn('get_free_size', b)
        with tempfile.TemporaryDirectory(dir=os.environ.get('CYM_WD_TEST_TMPDIR')) as d:
            p=Path(d); (p/'test.c').write_text('#include <assert.h>\n#include <stdbool.h>\n#include <stddef.h>\n#define MALLOC_CAP_SPIRAM 1\nstatic size_t total;\nstatic size_t heap_caps_get_total_size(int caps){assert(caps==1);return total;}\nstatic bool available(void){'+b+'}\nint main(void){total=0;assert(!available());total=1;assert(available());total=8388608;assert(available());return 0;}')
            subprocess.run(['cc','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)
    def test_settings_and_shared_worker_guard_before_side_effects(self):
        text=MAIN.read_text()
        for name, effect in [('show_sd_provision_confirm','create_function_page_base'),('show_sd_provision_running_screen','sd_provision_active = true'),('show_sd_format_confirm1','create_function_page_base')]:
            b=body(text,name)
            self.assertIn('if (!sd_auto_provision_available())',b)
            self.assertLess(b.index('if (!sd_auto_provision_available())'),b.index(effect))
            self.assertIn('show_sd_manual_setup_popup();',b[:b.index(effect)])
            self.assertIn('return;',b[:b.index(effect)])
    def test_startup_ok_never_requests_no_psram_provision(self):
        b=body(MAIN.read_text(),'show_sd_startup_provision_prompt')
        self.assertIn('sd_auto_provision_available()',b)
        self.assertIn('SD_MANUAL_SETUP_TEXT',b)
        self.assertIn('"OK"',b)
        self.assertIn('return can_provision && s_sd_startup_choice == 2;',b)
    def test_manual_modal_lifetime_and_truthful_copy_instructions(self):
        text=MAIN.read_text();b=body(text,'show_sd_manual_setup_popup')
        self.assertIn('static const char *',b)
        self.assertIn('"OK", ""',b)
        self.assertIn('lv_msgbox_create',b)
        self.assertIn('lv_msgbox_close_async',body(text,'sd_manual_setup_ok_cb'))
        for word in ['CYM-SD-Assets','no PSRAM','sdcard/'] : self.assertIn(word,text)
        for forbidden in ['xTaskCreate','xQueueCreate','f_mkfs','sd_provision_active = true']: self.assertNotIn(forbidden,b)
    def test_waveshare_has_no_onboard_rgb(self):
        for name in ['ws_c5_28','ws_c5_35','ws_s3_5b']:
            text=(ROOT/f'ESP32C5/components/board_hal/include/boards/{name}.h').read_text()
            self.assertRegex(text,r'#define BOARD_RGB_LED_GPIO\s+-1')
            self.assertRegex(text,r'#define BOARD_RGB_LED_COUNT\s+0')

class ClassicRgbCapabilities(unittest.TestCase):
    def test_classic_route_before_ws2812_guard(self):
        b=body((ROOT/'ESP32C5/components/wifi_cli/wifi_cli.c').read_text(),'init_led')
        self.assertIn('classic_rgb_led_init(&g_led_strip)',b)
        self.assertLess(b.index('classic_rgb_led_init'),b.index('led_strip_new_rmt_device'))
        self.assertIn('#if defined(CONFIG_BOARD_CYD2USB)',b)
    def test_real_backend_colors_off_idempotence_faults_and_board_gate(self):
        src=ROOT/'ESP32C5/components/wifi_cli/classic_rgb_led.c'
        self.assertTrue(src.exists(),'missing discrete RGB production backend')
        stub=r"""
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_ERR_INVALID_ARG 1
#define ESP_ERR_NOT_SUPPORTED 2
#define ESP_FAIL 3
typedef struct led_strip_t *led_strip_handle_t;
typedef struct led_strip_t {
esp_err_t (*set_pixel)(led_strip_handle_t,uint32_t,uint32_t,uint32_t,uint32_t);
esp_err_t (*set_pixel_rgbw)(led_strip_handle_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
esp_err_t (*refresh)(led_strip_handle_t);
esp_err_t (*clear)(led_strip_handle_t);
esp_err_t (*del)(led_strip_handle_t);
} led_strip_t;
#define BOARD_LED_R_GPIO 4
#define BOARD_LED_G_GPIO 16
#define BOARD_LED_B_GPIO 17
#define LEDC_LOW_SPEED_MODE 0
#define LEDC_TIMER_1 1
#define LEDC_TIMER_8_BIT 8
#define LEDC_CHANNEL_0 0
#define LEDC_CHANNEL_1 1
#define LEDC_CHANNEL_2 2
#define LEDC_AUTO_CLK 0
#define LEDC_INTR_DISABLE 0
#define GPIO_MODE_OUTPUT 1
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_DISABLE 0
typedef struct {int speed_mode,duty_resolution,timer_num,freq_hz,clk_cfg;} ledc_timer_config_t;
typedef struct {int gpio_num,speed_mode,channel,intr_type,timer_sel,duty,hpoint;struct {unsigned output_invert:1;} flags;} ledc_channel_config_t;
typedef struct {uint64_t pin_bit_mask;int mode,pull_up_en,pull_down_en,intr_type;} gpio_config_t;
static int fault=-2,configured,duties[3],levels[40],timer_calls;
static inline esp_err_t gpio_set_level(int pin,int level){levels[pin]=level;return ESP_OK;}
static inline esp_err_t gpio_config(const gpio_config_t *cfg){(void)cfg;return ESP_OK;}
static inline esp_err_t ledc_timer_config(const ledc_timer_config_t *c){timer_calls++;return c->timer_num==1 && c->duty_resolution==8 && fault!=-1?ESP_OK:ESP_FAIL;}
static inline esp_err_t ledc_channel_config(const ledc_channel_config_t *c){if(c->channel==fault)return ESP_FAIL;if(!c->flags.output_invert || c->duty!=0 || c->timer_sel!=1)return ESP_FAIL;configured++;duties[c->channel]=c->duty;return ESP_OK;}
static inline esp_err_t ledc_set_duty(int mode,int ch,uint32_t duty){(void)mode;duties[ch]=duty;return ESP_OK;}
static inline esp_err_t ledc_update_duty(int mode,int ch){(void)mode;(void)ch;return ESP_OK;}
static inline esp_err_t ledc_stop(int mode,int ch,int idle){(void)mode;(void)ch;return idle==1?ESP_OK:ESP_FAIL;}
"""
        harness=r"""
#include <assert.h>
int main(void){
 led_strip_handle_t h=NULL;
#ifdef CONFIG_BOARD_CYD2USB
 assert(classic_rgb_led_init(NULL)==ESP_ERR_INVALID_ARG);
 for(fault=-1;fault<3;fault++){h=NULL;assert(classic_rgb_led_init(&h)!=ESP_OK);assert(h==NULL);assert(levels[4]==1&&levels[16]==1&&levels[17]==1);}
 fault=-2;assert(classic_rgb_led_init(&h)==ESP_OK);assert(h);int old=timer_calls;
 led_strip_handle_t again=NULL;assert(classic_rgb_led_init(&again)==ESP_OK);assert(again==h&&timer_calls==old);
 assert(h->set_pixel(h,1,1,2,3)==ESP_ERR_INVALID_ARG);
 for(int i=0;i<3;i++){uint32_t rgb[3]={0};rgb[i]=255;assert(h->set_pixel(h,0,rgb[0],rgb[1],rgb[2])==ESP_OK);assert(h->refresh(h)==ESP_OK);for(int j=0;j<3;j++)assert(duties[j]==(int)rgb[j]);}
 assert(h->set_pixel(h,0,25,80,128)==ESP_OK);assert(h->refresh(h)==ESP_OK);assert(duties[0]==25&&duties[1]==80&&duties[2]==128);
 assert(h->clear(h)==ESP_OK);assert(!duties[0]&&!duties[1]&&!duties[2]);assert(h->del(h)==ESP_OK);
#else
 assert(classic_rgb_led_init(&h)==ESP_ERR_NOT_SUPPORTED);assert(h==NULL&&timer_calls==0&&configured==0);
#endif
 return 0;
}
"""
        with tempfile.TemporaryDirectory(dir=os.environ.get('CYM_WD_TEST_TMPDIR')) as d:
            p=Path(d);(p/'stub.h').write_text('#pragma once\n'+stub)
            for name in ['classic_rgb_led.h','board_hal.h','sdkconfig.h','led_strip.h','esp_err.h','driver/ledc.h','driver/gpio.h']:
                f=p/name;f.parent.mkdir(exist_ok=True);f.write_text('#include "stub.h"\n')
            # Include authentic production source after the host SDK boundary stubs.
            (p/'test.c').write_text('#include "stub.h"\n#include "'+str(src)+'"\n'+harness)
            for flags in [[],['-DCONFIG_BOARD_CYD2USB=1'],['-DCONFIG_BOARD_CYD2USB=1','-DCONFIG_BOARD_HACKERBOX_CYD=1']]:
                subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(p),*flags,str(p/'test.c'),'-o',str(p/'test')],check=True)
                subprocess.run([str(p/'test')],check=True)

if __name__=='__main__':unittest.main()
