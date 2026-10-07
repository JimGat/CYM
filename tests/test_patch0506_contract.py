"""Source contracts and compiled UART framing harness; not hardware proof."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import re

ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'ESP32C5/main/main.c').read_text()

def function(name):
    m=re.search(r'static [^;\n]+\b'+name+r'\([^;]*?\)\s*\{',S)
    if not m: raise AssertionError('Missing function '+name)
    start=m.start(); opening=S.index('{',m.start()); depth=1; pos=opening+1
    # Functions tested here have no braces in strings/comments.
    while depth:
        depth+=(S[pos]=='{')-(S[pos]=='}'); pos+=1
    return S[start:pos]

class Patch0506Contract(unittest.TestCase):
    def test_ble_capacity_and_session_reset(self):
        self.assertIn('#define WDP_BLE_NOPSRAM_DEVICES 128',S)
        alloc=function('wdp_ble_session_begin')
        self.assertIn('WD_RADIO_BLE_ONLY',alloc)
        self.assertIn('wdp_ble_capacity = 0',alloc)
        self.assertIn('wdp_ble_full_logged = false',alloc)
        self.assertIn('#if !CONFIG_BOARD_HAS_PSRAM',alloc)
        self.assertIn('wdp_ble_bounded_count()',function('wdp_ble_gap_body'))
        self.assertNotIn('static bool wdp_ble_full_logged',function('wdp_ble_gap_body'))
    def test_callback_quiescence_before_table_free(self):
        end=function('wdp_ble_session_end')
        self.assertLess(end.index('wdp_ble_accepting, false'),end.index('heap_caps_free'))
        self.assertLess(end.index('wdp_ble_inflight'),end.index('heap_caps_free'))
        self.assertIn('lvgl_mutex',end)
        cb=function('wdp_ble_gap_cb')
        self.assertIn('__atomic_add_fetch',cb)
        self.assertIn('__atomic_sub_fetch',cb)
    def test_task_failure_and_cooperative_stop(self):
        self.assertIn('wd_stack_bytes',S)
        self.assertNotIn('wd_stack_words',S)
        self.assertIn('Wardrive stopped: task allocation failed',S)
        stop=function('wardrive_screen_stop')
        self.assertNotIn('vTaskDelete(wardrive_task_handle)',stop)
        self.assertIn('wardrive_reap_task()',stop)
        self.assertIn('eSuspended',function('wardrive_reap_task'))
    def test_nimble_sync_is_not_port_lifetime(self):
        init=function('bt_nimble_init')
        cleanup=function('bt_nimble_cleanup_bounded')
        self.assertIn('nimble_port_initialized',init)
        self.assertIn('xTaskCreatePinnedToCore',init)
        self.assertIn('!= pdPASS',init)
        self.assertIn('bt_nimble_cleanup_bounded()',init)
        self.assertNotIn('nimble_port_stop()',cleanup)
        self.assertIn('nimble_host_exited',cleanup)
        self.assertIn('i < 30',cleanup)
        host=function('nimble_host_task')
        self.assertIn('ble_hs_stop(',host)
        self.assertIn('ble_npl_eventq_get',host)
        self.assertIn('nimble_host_exited, true',host)
    def test_radio_restart_guards_unfinished_host(self):
        self.assertIn('bt_nimble_cleanup_bounded()',function('ensure_wifi_mode'))
        self.assertIn('return nimble_initialized',function('ensure_ble_mode'))
    def test_classic_deferred_single_reader(self):
        self.assertIn('#if BOARD_HAS_GPS && !defined(CONFIG_BOARD_CYD2USB)',S)
        ready=S.index('ESP_LOGI(TAG, "System ready!")')
        deferred=S.index('Classic: critical boot allocations are complete')
        self.assertGreater(deferred,ready)
        self.assertIn('gps_classic_poll();',S)
        self.assertNotIn('3072-word',S)
        self.assertIn('#if !defined(CONFIG_BOARD_CYD2USB)',function('wardrive_promisc_task'))
    def test_classic_rfhat_rx_only_and_rollback(self):
        route=function('gps_classic_attach_rx')
        self.assertIn('CONFIG_BOARD_HAS_RF_HAT',route)
        self.assertIn('rx == 22',route)
        self.assertIn('GPIO_MODE_INPUT',route)
        self.assertIn('UART_PIN_NO_CHANGE, rx',route)
        self.assertNotIn('uart_set_pin(GPS_UART_NUM, g_gps_tx_pin',S)
        self.assertIn('uart_driver_delete',function('init_gps_uart'))
        for name in ['gps_send_pcas','gps_send_ubx','gps_set_update_rate_hz','gps_apply_baud_live']:
            self.assertIn('CONFIG_BOARD_CYD2USB',function(name))
        self.assertIn('115200, 38400, 9600',S)
        self.assertIn('RX-only',S)
    def test_nimble_cleanup_executable(self):
        # Execute the production cleanup function with deterministic SDK/task mocks.
        # This verifies bounded state decisions, not controller/FreeRTOS timing.
        harness=r"""
#include <stdbool.h>
#include <assert.h>
#include <stddef.h>
#define ESP_OK 0
#define ESP_LOGE(...) ((void)0)
#define pdMS_TO_TICKS(x) (x)
typedef int esp_err_t;
static bool nimble_port_initialized, nimble_deinit_failed, nimble_cleanup_busy;
static bool bt_scan_active, nimble_initialized, nimble_stop_requested, nimble_host_exited;
static void *bt_scan_task_handle, *nimble_host_handle;
static int delays, deinits, deinit_result, exit_at;
static void bt_stop_scan(void) {}
static void vTaskDelay(int ticks) { ++delays; if(exit_at && delays>=exit_at) nimble_host_exited=true; }
static int nimble_port_deinit(void) { ++deinits; assert(nimble_host_exited); return deinit_result; }
"""+function('bt_nimble_cleanup_bounded')+r"""
static void reset(void) {
 nimble_port_initialized=true; nimble_deinit_failed=false; nimble_cleanup_busy=false;
 bt_scan_active=true; nimble_initialized=false; nimble_stop_requested=false;
 nimble_host_exited=false; bt_scan_task_handle=NULL; nimble_host_handle=(void*)1;
 delays=deinits=deinit_result=exit_at=0;
}
int main(void) {
 reset(); assert(!bt_nimble_cleanup_bounded()); assert(delays==30 && deinits==0);
 assert(nimble_port_initialized && nimble_stop_requested && !nimble_cleanup_busy);
 // Delayed completion of a never-synced host permits retry, then new ownership.
 nimble_host_exited=true; assert(bt_nimble_cleanup_bounded()); assert(deinits==1);
 assert(!nimble_port_initialized && nimble_host_handle==NULL);
 reset(); exit_at=3; assert(bt_nimble_cleanup_bounded()); assert(deinits==1 && delays==3);
 reset(); bt_scan_task_handle=(void*)1; assert(!bt_nimble_cleanup_bounded());
 assert(delays==20 && deinits==0 && !nimble_stop_requested);
 reset(); nimble_cleanup_busy=true; assert(!bt_nimble_cleanup_bounded()); assert(delays==0 && deinits==0);
 reset(); nimble_host_exited=true; deinit_result=-1; assert(!bt_nimble_cleanup_bounded());
 assert(nimble_deinit_failed && nimble_port_initialized && deinits==1);
 assert(!bt_nimble_cleanup_bounded()); assert(deinits==1);
 reset(); nimble_host_exited=true; assert(bt_nimble_cleanup_bounded());
 reset(); nimble_host_exited=true; assert(bt_nimble_cleanup_bounded()); // repeated lifetime
 return 0;
}
"""
        with tempfile.TemporaryDirectory(dir=ROOT/'.hermes/patch0506') as d:
            p=Path(d); (p/'cleanup.c').write_text(harness)
            subprocess.run(['cc','-std=c11','-Wall','-Werror',str(p/'cleanup.c'),'-o',str(p/'cleanup')],check=True)
            subprocess.run([str(p/'cleanup')],check=True)

    def test_nmea_probe_executable(self):
        probe=function('gps_probe_nmea'); checksum=function('nmea_checksum_valid')
        self.assertIn('nmea_checksum_valid',probe)
        harness=r'''
#include <stdio.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define CONFIG_BOARD_CYD2USB 1
#define GPS_UART_NUM 2
#define ESP_OK 0
#define pdMS_TO_TICKS(x) (x)
static int64_t clock_us;
static const char *input;
static int failed;
static int uart_set_baudrate(int u,int b) { return failed; }
static int uart_flush_input(int u) { return failed; }
static int64_t esp_timer_get_time(void) { return clock_us; }
static int uart_read_bytes(int u,uint8_t *b,int size,int wait) {
 clock_us+=100000; if(failed) return -1;
 if(!*input) return 0;
 *b=*input++; return 1;
}
'''+checksum+'\n'+probe+r'''
static bool run(const char *s) { input=s; clock_us=0; return gps_probe_nmea(9600,1300); }
int main(void) {
 assert(!run("noise$Gnoise"));
 assert(!run("$GPRMC*00\r\n"));
 input="";
 char valid[32]; unsigned char checksum=0;
 for (const char *p="GPRMC,0"; *p; ++p) checksum^=(unsigned char)*p;
 snprintf(valid,sizeof(valid),"$GPRMC,0*%02X\r\n",checksum);
 assert(run(valid));
 assert(!run("$GPRMC*4Bjunk\n"));
 failed=1; assert(!run("$GPRMC*4B\r\n"));
 return 0;
}
'''
        # One byte/read exercises all possible split boundaries in the short frame.
        with tempfile.TemporaryDirectory(dir=ROOT/'.hermes/patch0506') as d:
            p=Path(d); (p/'probe.c').write_text(harness)
            subprocess.run(['cc','-std=c11','-Wall','-Wno-unused-parameter',str(p/'probe.c'),'-o',str(p/'probe')],check=True)
            subprocess.run([str(p/'probe')],check=True)

if __name__=='__main__': unittest.main()
