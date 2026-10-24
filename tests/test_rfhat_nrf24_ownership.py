from pathlib import Path
import os,re,subprocess,tempfile,unittest
R=Path(__file__).resolve().parents[1]
def function(s,name):
 m=re.search(r'^[^\n;]*\b'+re.escape(name)+r'\([^;\n]*\)\s*\{',s,re.M)
 if not m:raise AssertionError('missing production function '+name)
 a=m.start();i=s.index('{',a)+1;depth=1
 while depth:
  depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
class RFHatOwnership(unittest.TestCase):
 def setUp(self):
  self.main=(R/'ESP32C5/main/main.c').read_text();self.driver=(R/'ESP32C5/components/nrf24/src/nrf24.c').read_text()
 def native(self,src):
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as d:
   p=Path(d)/'case.c';p.write_text(src);exe=p.with_suffix('')
   c=subprocess.run(['cc','-std=c11','-O1','-Wall','-Wextra','-Werror=implicit-function-declaration','-fsanitize=undefined','-fno-sanitize-recover=all',str(p),'-o',str(exe)],capture_output=True,text=True)
   self.assertEqual(c.returncode,0,c.stdout+c.stderr)
   c=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
 def test_quiesce_all_five_owners_and_timeout(self):
  pre='''#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
typedef unsigned TickType_t;typedef void *TaskHandle_t;
typedef struct {volatile bool active,cancel;TaskHandle_t task;} ctx_t;
static ctx_t a,b,c;static ctx_t *s_ncs=&a,*s_nsniff=&b,*s_nfut=&c;
static bool s_n24_jam_active,s_blaster_nrf_active;
static TaskHandle_t s_n24_jam_task,s_blaster_nrf_task;
static unsigned now,delays,release_at;static TaskHandle_t *owner;
#define pdMS_TO_TICKS(x) ((x)/10)
static TickType_t xTaskGetTickCount(void){return now;}
static void vTaskDelay(TickType_t n){assert(n>0);now+=n;delays++;if(release_at&&delays==release_at)*owner=NULL;}
'''
  post='''static void reset(void){a=(ctx_t){.active=true};b=a;c=a;s_n24_jam_active=s_blaster_nrf_active=true;s_n24_jam_task=s_blaster_nrf_task=NULL;now=delays=release_at=0;}
static void cancelled(void){assert(!a.active&&a.cancel&&!b.active&&b.cancel&&!c.active&&c.cancel);assert(!s_n24_jam_active&&!s_blaster_nrf_active);}
int main(void){reset();assert(nrf24_hat_quiesce());assert(delays==0);cancelled();TaskHandle_t *owners[]={&a.task,&b.task,&c.task,&s_n24_jam_task,&s_blaster_nrf_task};
for(unsigned i=0;i<5;i++){reset();owner=owners[i];*owner=(void*)1;release_at=3;assert(nrf24_hat_quiesce());assert(delays==3);cancelled();reset();owner=owners[i];*owner=(void*)1;assert(!nrf24_hat_quiesce());assert(*owner==(void*)1);assert(now>=pdMS_TO_TICKS(1500));assert(now<=pdMS_TO_TICKS(1510));cancelled();*owner=NULL;assert(nrf24_hat_quiesce());}reset();s_ncs=s_nsniff=s_nfut=NULL;assert(nrf24_hat_quiesce());return 0;}
'''
  self.native(pre+function(self.main,'nrf24_hat_quiesce')+post)
 def test_claims_gate_before_teardown(self):
  for name in ['ir_hat_claim','rf433_hat_claim','rfid_hat_claim','cc1101_hat_claim','nrf24_hat_claim']:
   f=function(self.main,name);self.assertIn('static bool '+name,f);self.assertIn('if (!nrf24_hat_ready()) return false;',f);self.assertLess(f.index('if (!nrf24_hat_ready())'),f.index('_deinit('));self.assertIn('return true;',f)
   if name!='nrf24_hat_claim':self.assertIn('nrf24_deinit();',f)
 def test_every_claim_caller_checks_refusal(self):
  self.assertEqual(re.findall(r'(?m)^\s*(?:ir_hat_claim|rf433_hat_claim|rfid_hat_claim|cc1101_hat_claim|nrf24_hat_claim)\(\);',self.main),[])
  self.assertIn('if (!ir_hat_claim()) return IR_HAT_ERR_BUSY;',function(self.main,'ur_try_signal'))
  f=function(self.main,'s_blaster_start_cb');self.assertLess(f.index('if (!nrf24_hat_ready()) return;'),f.index('ensure_ble_mode()'))
  f=function(self.main,'rf433_lbk_run');self.assertLess(f.index('if (!nrf24_hat_ready()) return;'),f.index('nrf24_deinit();'))
 def test_hardware_test_probes_fresh(self):
  f=function(self.main,'show_nrf24_hw_test_screen');self.assertLess(f.index('if (!nrf24_hat_claim()) return;'),f.index('nrf24_deinit();'));self.assertLess(f.index('nrf24_deinit();'),f.index('nrf24_init();'))
 def test_entry_points_join_before_reusing_context(self):
  for n in ['show_nrf24_ch_scan_screen','show_nrf24_sniffer_screen','show_nrf24_jammer_screen','show_nrf24_futaba_screen','show_nrf24_foxhunt_screen']:
   f=function(self.main,n);self.assertTrue(f[f.index('{')+1:].lstrip().startswith('if (!nrf24_hat_claim()) return;'));self.assertLess(f.index('if (!nrf24_hat_claim()) return;'),f.index('nrf24_init()'))
 def test_failed_init_releases_both_board_adapted_pins(self):
  f=function(self.driver,'nrf24_init')
  for anchor,end in [('if (err != ESP_OK)', 'return err;'),('if (st == 0x00 || st == 0xFF)','return ESP_ERR_NOT_FOUND;')]:
   branch=f[f.index(anchor):];branch=branch[:branch.index(end)]
   for pin in ['RF_HAT_NRF24_CE_GPIO','RF_HAT_NRF24_CS_GPIO']:self.assertIn('gpio_reset_pin('+pin+');',branch)
if __name__=='__main__':unittest.main()
