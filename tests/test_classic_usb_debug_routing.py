"""Real transport plus production main.c fallback/dual-hook routing."""
import os, re, subprocess, tempfile, unittest
from pathlib import Path
from test_classic_usb_debug_next import STUB, HARNESS, MAIN
class ClassicRouting(unittest.TestCase):
 def test_production_fallback_and_dual_hook(self):
  source=(MAIN/'main.c').read_text()
  def extract(name):
   start=re.search(r'^static (?:int|void|esp_err_t) '+name+r'\([^;]*?\)\s*\{',source,re.M).start();a=source.index('{',start);n=1;b=a+1
   while n:n+=(source[b]=='{')-(source[b]=='}');b+=1
   return source[start:b]
  dual=extract('dual_vprintf')
  flags=sorted(set(re.findall(r'\b\w+_log_capture_enabled\b',dual)))
  queues=sorted(set(re.findall(r'\b\w+_log_queue\b',dual)))
  code=HARNESS[:HARNESS.index('int main(int argc')]
  code+=r"""
static int rom_calls,captured_records;
static vprintf_like_t previous_vprintf;
static bool cym_log_retire(void **q,bool force){(void)force;*q=NULL;return true;}
static void *xQueueCreate(int n,size_t z){assert(n&&z);return (void *)1;}
static int esp_rom_printf(const char *f,...){(void)f;rom_calls++;return 0;}
static void cym_log_enter(void){} static void cym_log_leave(void){}
static void xQueueSend(void *q,void *m,int t){assert(q&&m&&!t);captured_records++;}
typedef struct{char text[256];}evil_log_msg_t;
"""
  code+='static bool '+','.join(flags)+';\nstatic void *'+',*'.join(queues)+';\n'
  code+=extract('rom_vprintf')+'\n'+dual+'\n'
  for name in ['evil_twin','blackout']:
   for action in ['enable','disable']:
    code+=extract(name+'_'+action+'_log_capture')+'\n'
  code+=r"""
int main(void){
 assert(!cym_classic_usb_uart_start());drain();used=0;
 char record[701];memset(record,'Q',700);record[700]=0;
 assert(!evil_twin_enable_log_capture());
 vprintf_like_t previous=previous_vprintf;assert(sink==dual_vprintf);
 assert(!blackout_enable_log_capture()&&previous_vprintf==previous);
 test_log("I (123) synthetic: %s\n",record);drain();
 assert(rom_calls==0);assert(used==721);assert(!memcmp(output+19,record,700));
 assert(!memcmp(output+719,"\r\n",2));
 used=0;test_log("prefix ");test_log("body");test_log("\n");drain();
 assert(used==13&&!memcmp(output,"prefix body\r\n",13));
 /* The production owner must not restore early with another capture active. */
 test_log("wifi_attacks: sanitized capture\n");drain();assert(captured_records==2);
 evil_twin_disable_log_capture();assert(sink==dual_vprintf);
 blackout_disable_log_capture();assert(sink==previous&&!previous_vprintf);
 /* Enter/leave capture again; no accidental fallback to ROM or old queue. */
 assert(!evil_twin_enable_log_capture());evil_twin_disable_log_capture();assert(sink==previous);
 used=0;quota=0;assert(!evil_twin_enable_log_capture());
 for(int i=0;i<100;i++){test_log("I (123) synthetic: ");test_log("%s",record);test_log("\n");}
 quota=127;drain();assert(used>0&&used%721==0);
 for(size_t i=0;i<used;i+=721){assert(!memcmp(output+i,"I (123) synthetic: ",19));assert(!memcmp(output+i+19,record,700));assert(!memcmp(output+i+719,"\r\n",2));}
 cym_classic_usb_uart_stats_t stats;cym_classic_usb_uart_stats(&stats);assert(stats.dropped_records>0&&stats.retry_writes>0);
 evil_twin_disable_log_capture();assert(!cym_classic_usb_uart_stop());
 used=13;
 esp_log_set_vprintf(rom_vprintf);test_log("OFF must stay silent\n");
 assert(!rom_calls&&used==13);puts("production fallback/dual ON/OFF routing PASS");return 0;
}
"""
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
   d=Path(tmp);(d/'sdkconfig.h').write_text('#define CONFIG_BOARD_CYD2USB 1\n' + ('#define CONFIG_BOARD_HACKERBOX_CYD 1\n' if os.environ.get('CYM_TEST_HACKERBOX') == '1' else ''));(d/'mock.h').write_text(STUB)
   for h in ['esp_err.h','esp_timer.h','driver/uart.h','driver/gpio.h','esp_log.h','freertos/FreeRTOS.h','freertos/semphr.h','freertos/task.h']:
    p=d/h;p.parent.mkdir(exist_ok=True,parents=True);p.write_text('#include "mock.h"\n')
   (d/'host.c').write_text(code)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Wno-unused-function','-Werror','-fsanitize=undefined','-I'+str(d),'-I'+str(MAIN),str(d/'host.c'),str(MAIN/'classic_usb_debug_uart.c'),'-o',str(d/'host')],check=True)
   subprocess.run([str(d/'host'),'0'],check=True)
if __name__=='__main__':unittest.main()
