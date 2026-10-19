"""Execute production Classic controller with injected I/O failures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "ESP32C5/main"
HARNESS = r"""
#include <assert.h>
#include <stdio.h>
#include "classic_usb_debug.h"
static int stage, fail, starts, stops;
static esp_err_t quiesce(void) {
    assert(cym_classic_usb_gps_blocked());
    assert(stage == 0); stage = 1;
    return fail == 1 ? ESP_FAIL : ESP_OK;
}
esp_err_t cym_classic_usb_uart_start(void) {
    assert(cym_classic_usb_gps_blocked());
    assert(stage == 1); stage = 2; starts++;
    return fail == 2 ? ESP_FAIL : ESP_OK;
}
esp_err_t cym_classic_usb_uart_stop(void) { stops++; return fail == 3 ? ESP_FAIL : ESP_OK; }
int main(int argc, char **argv) {
    (void)argc; fail = argv[1][0] - '0';
    assert(!cym_classic_usb_active());
    assert(!cym_classic_usb_gps_blocked());
    assert(cym_classic_usb_enable(false, quiesce) != ESP_OK);
    assert(stage == 0 && starts == 0 && stops == 0);
    assert(!cym_classic_usb_gps_blocked());
#ifdef CONFIG_BOARD_CYD2USB
    assert(cym_classic_usb_enable(true, NULL) != ESP_OK);
    assert(!cym_classic_usb_gps_blocked());
    esp_err_t rc = cym_classic_usb_enable(true, quiesce);
    assert(cym_classic_usb_gps_blocked());
    if (fail == 1 || fail == 2) {
        assert(rc != ESP_OK && !cym_classic_usb_active());
        assert(starts == (fail == 2));
        assert(cym_classic_usb_enable(true, quiesce) != ESP_OK);
    } else {
        assert(rc == ESP_OK && cym_classic_usb_active());
        assert(cym_classic_usb_enable(true, quiesce) == ESP_OK);
        assert(starts == 1);
    }
    rc = cym_classic_usb_disable();
    assert(rc == (fail == 3 ? ESP_FAIL : ESP_OK));
    assert(!cym_classic_usb_active() && cym_classic_usb_gps_blocked());
    assert(cym_classic_usb_enable(true, quiesce) != ESP_OK);
    if (fail != 3) assert(cym_classic_usb_disable() == ESP_OK);
#else
    assert(cym_classic_usb_enable(true, quiesce) == ESP_ERR_NOT_SUPPORTED);
    assert(cym_classic_usb_disable() == ESP_ERR_NOT_SUPPORTED);
    assert(!cym_classic_usb_gps_blocked() && stage == 0 && starts == 0 && stops == 0);
#endif
    puts("controller safety passed");
}
"""
class ClassicUsbRuntime(unittest.TestCase):
    def test_controller_error_injection(self):
        with tempfile.TemporaryDirectory(prefix="classic-usb-", dir=os.environ["TMPDIR"]) as tmp:
            d = Path(tmp)
            (d / "sdkconfig.h").write_text("")
            (d / "esp_err.h").write_text("#pragma once\ntypedef int esp_err_t;\n#define ESP_OK 0\n#define ESP_FAIL -1\n#define ESP_ERR_NOT_SUPPORTED 0x106\n#define ESP_ERR_INVALID_STATE 0x103\n#define ESP_ERR_INVALID_ARG 0x102\n")
            (d / "host.c").write_text(HARNESS)
            for supported in (True, False):
                cmd = ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I"+str(d), "-I"+str(MAIN)]
                if supported: cmd += ["-DCONFIG_BOARD_CYD2USB=1"]
                subprocess.run(cmd + [str(MAIN / "classic_usb_debug.c"), str(d / "host.c"), "-o", str(d / "host")], check=True)
                for fault in range(4):
                    with self.subTest(supported=supported, fault=fault):
                        subprocess.run([str(d / "host"), str(fault)], check=True)
    def test_normal_console_contract_unchanged(self):
        cfg = (ROOT / "ESP32/sdkconfig.defaults.cyd2usb").read_text()
        self.assertIn("CONFIG_ESP_CONSOLE_NONE=y", cfg)
        self.assertIn("CONFIG_BOOTLOADER_LOG_LEVEL_NONE=y", cfg)
        self.assertIn("# CONFIG_ESP_CONSOLE_UART_DEFAULT is not set", cfg)
        hb = (ROOT / "scripts/build.sh").read_text().split("hackerbox-cyd)")[1].split(";;")[0]
        self.assertIn("sdkconfig.defaults.cyd2usb;sdkconfig.defaults.hackerbox-cyd", hb)
    def test_gps_guards_and_ui(self):
        import re
        s = (MAIN / "main.c").read_text()
        for signature in ("gps_classic_attach_rx(int rx)", "gps_classic_poll(void)", "init_gps_uart(void)", "gps_probe_nmea(int baud, int window_ms)", "gps_autodetect_and_sync(void)", "gps_uart_consumer_read(void *data, uint32_t size, TickType_t wait)"):
            m = re.search(re.escape(signature) + r"\s*\{", s)
            self.assertIsNotNone(m, signature)
            self.assertIn("cym_classic_usb_gps_blocked()", s[m.end():m.end()+300], signature)
        self.assertIn('"Classic USB Debug"', s)
        self.assertIn("GPS unavailable - Classic USB Debug", s)
        self.assertIn("I disconnected GPS - Enable", s)
        stop = s.split("static void hardware_debug_stop(void)", 1)[1].split("static void hardware_debug_event", 1)[0]
        self.assertIn("classic_usb_popup_close", stop)
        self.assertIn("LV_SCROLLBAR_MODE_AUTO", s.split("static void show_classic_usb_popup(void)",1)[1][:4500])

TRANSPORT_STUB = r"""#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stddef.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NOT_SUPPORTED 0x106
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_INVALID_ARG 0x102
#define ESP_ERR_TIMEOUT 0x107
#define ESP_ERR_NO_MEM 0x101
#define UART_NUM_0 0
#define UART_DATA_8_BITS 8
#define UART_PARITY_DISABLE 0
#define UART_STOP_BITS_1 1
#define UART_HW_FLOWCTRL_DISABLE 0
#define UART_SCLK_DEFAULT 0
#define UART_PIN_NO_CHANGE -1
#define GPIO_NUM_1 1
#define GPIO_MODE_INPUT 1
#define pdTRUE 1
#define pdMS_TO_TICKS(n) (n)
typedef int StaticSemaphore_t;
typedef void *SemaphoreHandle_t;
typedef int (*vprintf_like_t)(const char *, va_list);
typedef struct {int baud_rate, data_bits, parity, stop_bits, flow_ctrl, source_clk;} uart_config_t;
SemaphoreHandle_t xSemaphoreCreateMutexStatic(StaticSemaphore_t *);
int xSemaphoreTake(SemaphoreHandle_t, unsigned);
void xSemaphoreGive(SemaphoreHandle_t);
bool uart_is_driver_installed(int);
int uart_driver_install(int,int,int,int,void *,int);
int uart_driver_delete(int);
int uart_param_config(int,const uart_config_t *);
int uart_set_pin(int,int,int,int,int);
int uart_tx_chars(int,const char *,uint32_t);
int gpio_reset_pin(int);
int gpio_set_direction(int,int);
vprintf_like_t esp_log_set_vprintf(vprintf_like_t);
void test_log(const char *,...);
#define ESP_LOGI(tag,fmt,...) test_log(fmt,##__VA_ARGS__)
"""
TRANSPORT_HARNESS = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "classic_usb_debug.h"
#include "mock.h"
static int failure, installed, drive, locked, quiesced, stage, writes, stop_calls;
static int seen_bytes, lock_fail, previous_calls;
static int old_sink(const char *f, va_list a) {(void)f;(void)a;previous_calls++;return 0;}
static vprintf_like_t current_sink=old_sink, captured;
static int injected(int n) { return failure==n?ESP_FAIL:ESP_OK; }
static esp_err_t gps_stop(void) {
 assert(cym_classic_usb_gps_blocked() && !drive);stage=1;quiesced=1;return ESP_OK;
}
SemaphoreHandle_t xSemaphoreCreateMutexStatic(StaticSemaphore_t *p) {return failure==1?NULL:p;}
int xSemaphoreTake(SemaphoreHandle_t h,unsigned ticks) {assert(h && (ticks==0||ticks==100));if(locked||lock_fail)return 0;locked=1;return 1;}
void xSemaphoreGive(SemaphoreHandle_t h){assert(h&&locked);locked=0;}
bool uart_is_driver_installed(int n){assert(n==0);return installed;}
int uart_driver_install(int n,int rx,int tx,int q,void *h,int flags){assert(n==0&&rx==256&&tx==0&&q==0&&!h&&!flags&&quiesced&&!drive);stage=2;if(failure==2)return ESP_FAIL;installed=1;return 0;}
int uart_param_config(int n,const uart_config_t *p){assert(n==0&&stage==2&&!drive&&p->baud_rate==115200&&p->data_bits==8&&p->stop_bits==1&&p->flow_ctrl==0);stage=3;return injected(3);}
int uart_set_pin(int n,int tx,int rx,int rts,int cts){assert(n==0&&stage==3&&tx==1&&rx==-1&&rts==-1&&cts==-1&&quiesced);stage=4;drive=1;return injected(4);}
int uart_driver_delete(int n){assert(n==0&&!drive);stop_calls++;if(failure==6)return ESP_FAIL;installed=0;return 0;}
int gpio_reset_pin(int n){assert(n==1);drive=0;return injected(5);}
int gpio_set_direction(int n,int mode){assert(n==1&&mode==GPIO_MODE_INPUT);return 0;}
int uart_tx_chars(int n,const char *data,uint32_t bytes){assert(n==0&&drive&&locked&&data&&bytes<=127);writes++;seen_bytes=bytes;return failure==7?-1:(int)bytes;}
vprintf_like_t esp_log_set_vprintf(vprintf_like_t f){vprintf_like_t old=current_sink;current_sink=f;if(f!=old_sink){assert(stage==4&&drive);captured=f;}return old;}
void test_log(const char *fmt,...){va_list args;va_start(args,fmt);current_sink(fmt,args);va_end(args);}
static void late_callback(const char *fmt,...){va_list args;va_start(args,fmt);captured(fmt,args);va_end(args);}
int main(int argc,char **argv) {
 (void)argc;failure=argv[1][0]-'0';
 assert(!cym_classic_usb_active()&&!drive&&!installed);
 assert(cym_classic_usb_enable(false,gps_stop)!=0&&!drive&&!quiesced);
 esp_err_t rc=cym_classic_usb_enable(true,gps_stop);
 if(failure>=1 && failure<=4){
  assert(rc!=0&&!drive&&!cym_classic_usb_active());assert(current_sink==old_sink);
  assert(!installed);assert(cym_classic_usb_gps_blocked());
 }else{
  assert(rc==0&&drive&&installed&&cym_classic_usb_active());
  assert(cym_classic_usb_enable(true,gps_stop)==0); /* idempotent, no reallocation */
  test_log("%0200d",1);assert(seen_bytes==127);
  int before=writes;locked=1;test_log("drop busy");locked=0;assert(writes==before);
  if(failure==8){
   lock_fail=1;assert(cym_classic_usb_disable()==ESP_ERR_TIMEOUT);
   lock_fail=0; before=writes; test_log("disabled after timeout"); assert(writes==before);
   /* retry cleanup may proceed, but GPS must remain inhibited */
  }
  rc=cym_classic_usb_disable();
  assert(rc==((failure==5||failure==6)?ESP_FAIL:ESP_OK));
  assert(!drive && current_sink==old_sink && cym_classic_usb_gps_blocked());
  before=writes;late_callback("callback captured before teardown");assert(writes==before);
  assert(cym_classic_usb_enable(true,gps_stop)!=0);
  failure=0;assert(cym_classic_usb_disable()==0&&!installed);
  test_log("restored");assert(previous_calls==1);
 }
 puts("transport safety passed");
}
"""

class ClassicUsbTransport(unittest.TestCase):
    def test_unsupported_transport_has_no_sdk_uart_dependency(self):
        with tempfile.TemporaryDirectory(prefix="classic-unsupported-",dir=os.environ["TMPDIR"]) as tmp:
            d=Path(tmp);(d/'sdkconfig.h').write_text('')
            (d/'esp_err.h').write_text(TRANSPORT_STUB)
            (d/'host.c').write_text('#include <assert.h>\n#include "classic_usb_debug.h"\nint main(void){assert(!cym_classic_usb_active()&&!cym_classic_usb_gps_blocked());assert(cym_classic_usb_uart_start()==0x106);assert(cym_classic_usb_uart_stop()==0x106);return 0;}\n')
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(d),'-I'+str(MAIN),str(d/'host.c'),str(MAIN/'classic_usb_debug.c'),str(MAIN/'classic_usb_debug_uart.c'),'-o',str(d/'host')],check=True)
            subprocess.run([str(d/'host')],check=True)

    def test_production_uart_faults_and_bounded_logging(self):
        with tempfile.TemporaryDirectory(prefix="classic-uart-", dir=os.environ["TMPDIR"]) as tmp:
            d=Path(tmp)
            (d/'sdkconfig.h').write_text('#define CONFIG_BOARD_CYD2USB 1\n')
            (d/'mock.h').write_text(TRANSPORT_STUB)
            for h in ['esp_err.h','driver/uart.h','driver/gpio.h','esp_log.h','freertos/FreeRTOS.h','freertos/semphr.h']:
                p=d/h;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#include "mock.h"\n')
            (d/'host.c').write_text(TRANSPORT_HARNESS)
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-I'+str(d),'-I'+str(MAIN),str(d/'host.c'),str(MAIN/'classic_usb_debug.c'),str(MAIN/'classic_usb_debug_uart.c'),'-o',str(d/'host')],check=True)
            for fault in range(9):
                with self.subTest(fault=fault):subprocess.run([str(d/'host'),str(fault)],check=True)

if __name__ == "__main__": unittest.main()
