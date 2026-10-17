from pathlib import Path
import unittest,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[1]
class Observer95(unittest.TestCase):
 def test_production_memory_policy(self):
  header=ROOT/'ESP32C5/components/wifi_sniffer/include/observer_memory.h'
  for psram in [0,1]:
   src='#include <assert.h>\n#include "'+str(header)+'"\nint main(void){assert(observer_heap_caps()=='+('MALLOC_CAP_SPIRAM' if psram else '(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)')+');assert(observer_stack_bytes(16384)=='+'16384'+');assert(observer_stack_bytes(8192)==8192);assert(observer_waterfall_rows(148)=='+('148' if psram else '16')+');return 0;}\n'
   with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'esp_heap_caps.h').write_text('#define MALLOC_CAP_SPIRAM 1\n#define MALLOC_CAP_INTERNAL 2\n#define MALLOC_CAP_8BIT 4\n');(p/'t.c').write_text(src)
    q=subprocess.run(['cc','-DCONFIG_BOARD_HAS_PSRAM='+str(psram),'-I'+d,str(p/'t.c'),'-o',str(p/'t')],capture_output=True,text=True)
    self.assertEqual(q.returncode,0,q.stderr);subprocess.run([str(p/'t')],check=True)
 def test_all_observer_entry_points_use_policy(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text()
  self.assertNotIn('sniffer_task_stack = (StackType_t *)heap_caps_malloc(16384 * sizeof(StackType_t), MALLOC_CAP_SPIRAM)',s)
  self.assertNotIn('sniffer_task_stack = (StackType_t *)heap_caps_malloc(8192 * sizeof(StackType_t), MALLOC_CAP_SPIRAM)',s)
  self.assertIn('wscope_active = false;',s[s.index('static void show_wscope_screen(void) {'):s.index('// BLE BAND SCOPE')])


class ObserverStartupBuffers95(unittest.TestCase):
 def test_actual_production_buffer_admission_with_faults(self):
  s=(ROOT/'ESP32C5/components/wifi_sniffer/wifi_sniffer.c').read_text()
  start=s.index('esp_err_t wifi_sniffer_start(void) {');end=s.index('    // Clear previous data',start)
  body='esp_err_t wifi_sniffer_start(void) {\n'+s[s.index('    if (sniffer_active)',start):end]+'return ESP_OK;\n}\n'
  common=(ROOT/'ESP32C5/components/wifi_cli/include/wifi_common.h').read_text()
  macros=common[common.index('#if CONFIG_BOARD_HAS_PSRAM\n#define MAX_CLIENTS_PER_AP'):common.index('#define MAX_TARGET_BSSIDS')]
  structs=common[common.index('// Probe request structure'):common.index('// GPS data structure')]
  for psram in [0,1]:
   source='#include <assert.h>\n#include <stdlib.h>\n#include <stdbool.h>\n#include <stdint.h>\n#include "observer_memory.h"\n'+macros+'typedef int wifi_auth_mode_t;\n'+structs+r'''
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_ERR_NO_MEM 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
static bool sniffer_active;static sniffer_ap_t* sniffer_aps;static probe_request_t* probe_requests;
static int calls,fail_call;static unsigned last_caps;
static void* heap_caps_calloc(unsigned n,unsigned size,unsigned caps){last_caps=caps;calls++;return calls==fail_call?NULL:calloc(n,size);}
#define heap_caps_free free
'''+body+r'''
int main(void){
 fail_call=1;assert(wifi_sniffer_start()==ESP_ERR_NO_MEM);assert(!sniffer_aps&&!probe_requests);
 calls=0;fail_call=2;assert(wifi_sniffer_start()==ESP_ERR_NO_MEM);assert(!sniffer_aps&&!probe_requests);
 calls=0;fail_call=0;assert(wifi_sniffer_start()==ESP_OK);assert(sniffer_aps&&probe_requests);assert(calls==2);assert(last_caps==observer_heap_caps());
 assert(wifi_sniffer_start()==ESP_OK);assert(calls==2);free(sniffer_aps);free(probe_requests);return 0;}
'''
   with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'esp_heap_caps.h').write_text('#define MALLOC_CAP_SPIRAM 1\n#define MALLOC_CAP_INTERNAL 2\n#define MALLOC_CAP_8BIT 4\n');(p/'t.c').write_text(source)
    inc=ROOT/'ESP32C5/components/wifi_sniffer/include'
    q=subprocess.run(['cc','-DCONFIG_BOARD_HAS_PSRAM='+str(psram),'-I'+str(inc),'-I'+d,str(p/'t.c'),'-o',str(p/'t')],capture_output=True,text=True)
    self.assertEqual(q.returncode,0,q.stderr);subprocess.run([str(p/'t')],check=True)
