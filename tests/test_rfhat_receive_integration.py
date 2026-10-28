"""Production-extracted receive tests; synthetic SDK/edges, never RF proof."""
from pathlib import Path
import os,re,subprocess,unittest
R=Path(__file__).resolve().parents[1]
def fn(s,n):
 m=re.search(r'^[^\n;]*\b'+n+r'\([^;]*?\)\s*\{',s,re.M)
 if not m:raise AssertionError('missing production function '+n)
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 f=s[m.start():i]
 if n in ['rf433_rx_prepare','rf433_ook_rx_begin'] and 'static void '+n in f:
  f=f.replace(n+'(',n+'_legacy(',1)+'\nstatic int '+n+'(void){'+n+'_legacy();return 0;}'
 return f
PRE='#include <assert.h>\n#include <stdbool.h>\n#include <stdint.h>\n#include <stddef.h>\n#include <string.h>\n#include <limits.h>\n#include <stdio.h>\n'
class ReceiveIntegration(unittest.TestCase):
 def setUp(self):
  self.m=(R/'ESP32C5/main/main.c').read_text();self.ir=(R/'ESP32C5/components/rf_hat/src/ir_hat.c').read_text()
  if os.environ.get('RFHAT_IR_BASELINE'):self.ir=subprocess.check_output(['git','show','HEAD:ESP32C5/components/rf_hat/src/ir_hat.c'],cwd=R,text=True)
 def native(self,name,s):
  # Run legacy signatures red without masking the destination-capacity assertion.
  if "rf433_ook_snapshot(int32_t *out, int capacity" in s:
   s=s.replace("rf433_ook_snapshot(out,&n)","rf433_ook_snapshot(out,256,&n)")
  out=Path(os.environ['CYM_TEST_OUT'])/'rfhat-receive';out.mkdir(parents=True,exist_ok=True)
  p=out/(name+'.c');p.write_text(PRE+s);exe=p.with_suffix('')
  c=subprocess.run(['cc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror=implicit-function-declaration','-fsanitize=undefined','-fno-sanitize-recover=all',str(p),'-o',str(exe)],capture_output=True,text=True)
  self.assertEqual(c.returncode,0,c.stdout+c.stderr)
  c=subprocess.run([str(exe)],capture_output=True,text=True,timeout=15);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
 def test_decoder_and_both_consumers(self):
  decoder=fn(self.m,'ook_decode_ev1527');call='ook_decode_ev1527(p,n,a,d,&used)' if 'consumed_out' in decoder else 'ook_decode_ev1527(p,n,a,d)'
  loops=[]
  for name in ['s_alm_task_fn','s_rf433_scan_task_fn']:
   f=fn(self.m,name);a=f.index('for (int start');i=f.index('{',a)+1;depth=1
   while depth:depth+=(f[i]=='{')-(f[i]=='}');i+=1
   loop=f[a:i]
   loop=re.sub(r'int8_t rssi = cc1101_get_rssi_dbm\(\);','int8_t rssi = -1;',loop)
   loop=re.sub(r'wx_update_t \*u = malloc\(sizeof\(wx_update_t\)\);\s*if \(u\) \{.*?\}','',loop,flags=re.S)
   loop=re.sub(r'lv_async_call\([^;]*;','',loop)
   loops.append('static int consumer%d(const int32_t *buf,int count){struct{const int32_t *timings;int count;}raw={buf,count};bool s_alm_stop=false,s_rf433_scan_stop=false;uint32_t addr;uint8_t data;int consumed=0;hits=0;'%len(loops)+loop+'return hits;}')
  self.native('decoder','static int hits;static void ook_alarm_update(uint32_t a,uint8_t d,int r){(void)r;assert(a==0xABCDE&&d==5);hits++;}\n'+decoder+'\n'+'\n'.join(loops)+r'''
static void frame(int32_t*p){p[0]=-400;p[1]=12000;for(int i=0;i<24;i++){int one=(0xABCDE5>>(23-i))&1;p[2+i*2]=one?-1200:-400;p[3+i*2]=one?400:1200;}}
static bool decode(int32_t*p,int n,uint32_t*a,uint8_t*d){int used=0;return CALL;}
int main(void){int32_t p[160]={0};uint32_t a=0;uint8_t d=0;frame(p);
assert(decode(p,50,&a,&d)&&"exact sync+24 bits must decode");assert(a==0xABCDE&&d==5);
for(int n=0;n<50;n++)assert(!decode(p,n,&a,&d));
assert(consumer0(p,50)==1&&consumer1(p,50)==1);frame(p+50);assert(consumer0(p,100)==2&&consumer1(p,100)==2);
for(int i=100;i>=0;i--)p[i+7]=p[i];for(int i=0;i<7;i++)p[i]=99;
assert(consumer0(p,107)==2&&consumer1(p,107)==2);
frame(p);p[2]=INT32_MIN;assert(!decode(p,50,&a,&d));frame(p);p[3]=100000;assert(!decode(p,50,&a,&d));
frame(p);p[2]=-10;p[3]=900;assert(!decode(p,50,&a,&d));
frame(p);for(int i=0;i<50;i++)p[i]=-p[i];assert(!decode(p,50,&a,&d));
for(int i=0;i<160;i++)p[i]=(i&1)?300:-300;assert(!decode(p,160,&a,&d));}
'''.replace('CALL',call))
 def test_preparation_refuses_before_teardown(self):
  self.native('prepare',r'''
#define ESP_OK 0
#define ESP_ERR_INVALID_STATE 1
#define RF_HAT_RF433_TX_GPIO 8
#define GPIO_MODE_OUTPUT 1
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_DISABLE 0
typedef int esp_err_t;typedef int gpio_num_t;
typedef struct{uint64_t pin_bit_mask;int mode,pull_up_en,pull_down_en,intr_type;}gpio_config_t;
static int refuse,changes;static bool jam=true;
static bool nrf24_hat_ready(void){return refuse!=1;}
static bool rf433_ook_quiesce(void){return refuse!=2;}
static bool rf433_rx_owners_ready(void){return refuse!=3;}
static bool ir_hat_quiesce(void){return refuse!=4;}
static bool rf433_hat_quiesce(void){return refuse!=5;}
static bool cc1101_is_init(void){return true;}static bool nrf24_is_init(void){return true;}static bool rfid_manager_is_init(void){return true;}
static bool ir_hat_is_init(void){return false;}static bool ir_hat_is_jamming(void){return jam;}
static void cc1101_deinit(void){changes++;}static void nrf24_deinit(void){changes++;}static void rfid_manager_deinit(void){changes++;}
static bool ir_hat_release(void){changes++;jam=false;return refuse!=8;}static void rf433_hat_deinit(void){changes++;}
static int gpio_config(const gpio_config_t*p){(void)p;changes++;return refuse==6?6:0;}
static int gpio_set_level(int p,int v){(void)p;assert(!v);changes++;return refuse==7?7:0;}
'''+fn(self.m,'rf433_rx_prepare')+r'''
int main(void){for(refuse=1;refuse<=5;refuse++){changes=0;assert(rf433_rx_prepare()!=ESP_OK);assert(!changes&&jam);}refuse=0;assert(rf433_rx_prepare()==0&&!jam&&changes==7);refuse=8;changes=0;assert(rf433_rx_prepare()!=ESP_OK&&changes==1);refuse=6;assert(rf433_rx_prepare()==6);refuse=7;assert(rf433_rx_prepare()==7);}
''')
 def test_session_snapshot_stop(self):
  self.native('session',r'''
#define IRAM_ATTR
#define ESP_OK 0
#define ESP_ERR_INVALID_STATE 1
#define RF_HAT_RF433_RX_GPIO 9
#define GPIO_MODE_INPUT 0
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_ANYEDGE 3
#define portENTER_CRITICAL(p) do{(void)(p);assert(!locked);locked=1;}while(0)
#define portEXIT_CRITICAL(p) do{(void)(p);assert(locked);locked=0;}while(0)
#define portENTER_CRITICAL_ISR portENTER_CRITICAL
#define portEXIT_CRITICAL_ISR portEXIT_CRITICAL
typedef int esp_err_t;typedef int gpio_num_t;
typedef struct{uint64_t pin_bit_mask;int mode,pull_up_en,pull_down_en,intr_type;}gpio_config_t;
static int s_rf433_ook_mux,locked,fail,installed;static int64_t now;
static volatile bool s_rf433_ook_cap_active;static bool s_rf433_ook_isr_installed;
static volatile int32_t s_rf433_ook_buf[2048];static volatile int s_rf433_ook_wr;static volatile int64_t s_rf433_ook_last;
static volatile bool s_rf433_scan_stop;static uint32_t s_rf433_scan_epoch;
static int rf433_rx_prepare(void){return fail==1?1:0;}
static int gpio_config(const gpio_config_t*p){(void)p;return fail==2?2:0;}
static int gpio_install_isr_service(int x){(void)x;return fail==3?3:ESP_ERR_INVALID_STATE;}
static int gpio_isr_handler_add(int p,void(*f)(void*),void*a){(void)p;(void)f;(void)a;if(fail==4)return 4;installed++;return 0;}
static int gpio_isr_handler_remove(int p){(void)p;assert(installed);installed--;return 0;}
static int64_t esp_timer_get_time(void){return now+=400;}static int gpio_get_level(int p){(void)p;return now/400%2;}
static void rf433_ook_rx_end(void);static bool interrupt_copy;
static void *copy(void*d,const void*s,size_t n){assert(!locked);if(interrupt_copy)rf433_ook_rx_end();return memcpy(d,s,n);}
#define memcpy copy
'''+ '\n'.join(fn(self.m,n) for n in ['s_rf433_ook_cap_isr','rf433_ook_rx_end','rf433_ook_rx_begin','rf433_ook_snapshot'])+r'''
#undef memcpy
int main(void){for(fail=1;fail<=4;fail++){assert(rf433_ook_rx_begin()!=ESP_OK);assert(!installed&&!s_rf433_ook_isr_installed&&!s_rf433_ook_cap_active);}fail=0;
s_rf433_scan_stop=false;assert(rf433_ook_rx_begin()==0&&installed==1);for(int i=0;i<4000;i++)s_rf433_ook_cap_isr(NULL);assert(s_rf433_ook_wr==2048);
int32_t out[2050]={0};out[256]=12345;int n=0;rf433_ook_snapshot(out,&n);assert(n==256&&out[256]==12345&&s_rf433_ook_cap_active&&s_rf433_ook_wr==0);
for(int i=0;i<60;i++)s_rf433_ook_cap_isr(NULL);interrupt_copy=true;rf433_ook_snapshot(out,&n);assert(!s_rf433_ook_cap_active&&!installed);
interrupt_copy=false;assert(rf433_ook_rx_begin()==0);rf433_ook_rx_end();rf433_ook_rx_end();assert(!installed);}
''')
 def test_ir_rearm_drains_after_disable(self):
  self.native('ir-rearm',r'''
#define ESP_OK 0
#define ESP_FAIL 8
#define ESP_LOGE(...) ((void)0)
typedef int esp_err_t;
static void *s_rx_chan=(void*)1,*s_rx_queue=(void*)2;
static bool s_rx_enabled=true,s_rx_healthy;static int state=2,queued,fail;
static int rmt_disable(void*p){(void)p;if(fail==1)return ESP_FAIL;assert(state==1||state==2);queued++;state=0;return ESP_OK;}
static int rmt_enable(void*p){(void)p;assert(state==0&&!queued);if(fail==2)return ESP_FAIL;state=1;return ESP_OK;}
static int xQueueReset(void*p){(void)p;assert(state==0);queued=0;return 1;}
'''+fn(self.ir,'s_rx_rearm')+r'''
int main(void){assert(s_rx_rearm()==0&&state==1&&s_rx_healthy&&!queued);assert(s_rx_rearm()==0&&state==1);state=2;queued=2;assert(s_rx_rearm()==0&&!queued);fail=1;assert(s_rx_rearm()!=0&&!s_rx_healthy&&state==1);fail=0;assert(s_rx_rearm()==0);fail=2;assert(s_rx_rearm()!=0&&!s_rx_healthy&&state==0&&!s_rx_enabled);fail=0;assert(s_rx_rearm()==0&&s_rx_enabled&&state==1);}
''')

 def test_ir_capture_sequences(self):
  helper=fn(self.ir,'s_rx_rearm') if 'static esp_err_t s_rx_rearm' in self.ir else ''
  self.native('ir-capture',r'''
#define ESP_OK 0
#define ESP_FAIL 8
#define IR_HAT_OK 0
#define IR_HAT_ERR_TIMEOUT 2
#define IR_HAT_ERR_HW 4
#define IR_HAT_MAX_TIMINGS 128
#define IR_HAT_NAME_LEN 32
#define IR_CARRIER_HZ 38000
#define IR_CARRIER_DUTY 0.33f
#define IR_MIN_PULSE_NS 1250
#define IR_FRAME_GAP_NS 12000000
#define ESP_LOGE(...) ((void)0)
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
typedef int esp_err_t;typedef int ir_hat_err_t;typedef unsigned TickType_t;
typedef struct{unsigned duration0,duration1;}rmt_symbol_word_t;
typedef struct{unsigned signal_range_min_ns,signal_range_max_ns;}rmt_receive_config_t;
typedef struct{unsigned num_symbols;rmt_symbol_word_t*received_symbols;}rmt_rx_done_event_data_t;
static rmt_symbol_word_t s_rx_buf[64]={{400,1200}};
static struct{unsigned count,freq_hz;float duty_cycle;char name[32];unsigned times_us[128];}s_cap_signal;
static void*s_rx_chan=(void*)1,*s_rx_queue=(void*)2,*s_cap_task=(void*)3,*s_cap_ctx;
static bool s_cap_cancel,s_rx_enabled=true,s_rx_healthy=true;
static unsigned s_cap_tmo_ms=40,now;static int state=1,queued,mode,callbacks,result,disables;
static int rmt_disable(void*p){(void)p;disables++;assert(state==1||state==2);if(mode==2)queued++;state=0;return 0;}
static int rmt_enable(void*p){(void)p;assert(state==0);state=1;return 0;}
static int xQueueReset(void*p){(void)p;assert(state==0);queued=0;return 1;}
static int rmt_receive(void*p,void*b,size_t n,void*c){(void)p;(void)b;(void)n;(void)c;if(state!=1)return 8;state=2;return 0;}
static unsigned xTaskGetTickCount(void){return now;}
static void vTaskDelay(unsigned t){now+=t;}
static int xQueueReceive(void*q,rmt_rx_done_event_data_t*d,unsigned t){(void)q;now+=t;if(mode==3)s_cap_cancel=true;if(mode==0||queued){queued=0;state=1;*d=(rmt_rx_done_event_data_t){1,s_rx_buf};return 1;}return 0;}
static void callback(int r,const void*s,void*c){(void)c;callbacks++;result=r;if(r==0)assert(s&&s_cap_signal.count==2);}
static void(*s_cap_cb)(int,const void*,void*)=callback;
static void vTaskDelete(void*p){assert(!p);}
'''+helper+fn(self.ir,'s_capture_task')+r'''
static void capture(int m){mode=m;now=0;s_cap_task=(void*)3;s_cap_cancel=false;s_capture_task(NULL);assert(!s_cap_task);}
int main(void){capture(0);capture(0);assert(callbacks==2&&result==0&&disables==0);capture(1);assert(result==2&&state==1);capture(0);assert(result==0);capture(2);assert(result==2&&state==1&&!queued&&"late timeout completion must be drained after disable");capture(0);assert(result==0);int before=callbacks;capture(3);assert(callbacks==before&&state==1);capture(0);assert(callbacks==before+1&&result==0);}
''')
 def test_bounded_worker_joins_and_retry(self):
  for name,src,task,flag in [('ir_hat_quiesce',self.ir,'s_cap_task','s_cap_cancel'),('rf433_hat_quiesce',(R/'ESP32C5/components/rf_hat/src/rf433_hat.c').read_text(),'s_cap_task','s_cap_cancel'),('rf433_ook_quiesce',self.m,'s_rf433_scan_task','s_rf433_scan_stop')]:
   self.native('join-'+name,r'''
#define pdMS_TO_TICKS(x) (x)
typedef unsigned TickType_t;static unsigned now,release_at;static void *TASK;static bool FLAG;
static unsigned xTaskGetTickCount(void){return now;}
static void vTaskDelay(unsigned n){now+=n;if(release_at&&now>=release_at)TASK=NULL;}
static void rf433_ook_rx_end(void){}
'''.replace('TASK',task).replace('FLAG',flag)+fn(src,name)+r'''
int main(void){TASK=(void*)1;assert(!JOIN());assert(TASK&&FLAG&&now==1500);now=0;release_at=700;assert(JOIN());assert(!TASK&&now==700);TASK=(void*)1;now=0;release_at=20;assert(JOIN()&&!TASK);}
'''.replace('TASK',task).replace('FLAG',flag).replace('JOIN',name))
 def test_source_admission_and_placement_contracts(self):
  start=fn(self.m,'show_rf433_ook_scan_screen');self.assertIn('!= pdPASS',start);self.assertIn('rf433_ook_rx_end();',start)
  self.assertNotIn('vTaskDelete(s_',fn(self.ir,'ir_hat_capture_cancel'))
  self.assertIn('xTaskCreatePinnedToCore',fn(self.ir,'ir_hat_capture_start'))
  self.assertIn('s_rx_core = xPortGetCoreID()',fn(self.ir,'ir_hat_init'))
  self.assertIn('IR_TASK_DATA_ATTR static ir_signal_t    s_cap_signal;',self.ir)
  self.assertIn('static rmt_symbol_word_t s_rx_buf[',self.ir)
  self.assertIn('static volatile int32_t  s_rf433_ook_buf[2048]',self.m)
  cb=fn(self.m,'s_rf433_scan_lvgl_cb');self.assertIn('s_rf433_scan_epoch',cb)
  fox=fn(self.m,'show_rf433_foxhunt_screen');self.assertLess(fox.index('rf433_rx_prepare()'),fox.index('gpio_config('));self.assertIn('if (rx_err != ESP_OK)',fox)

 def test_all_active_owner_guards(self):
  self.native('owners',r'''
static bool poll,emulate,s_cc1101_jamming;
static bool rfid_manager_is_polling(void){return poll;}static bool rfid_manager_is_emulating(void){return emulate;}
static void *s_cc1101_cap_task,*s_cc1101_rep_task,*s_wx_task,*s_alm_task;
static struct ctx{void*task;}bs,zw,tp;static struct ctx*s_bs=&bs,*s_zwave=&zw,*s_tpms=&tp;
'''+fn(self.m,'rf433_rx_owners_ready')+r'''
int main(void){assert(rf433_rx_owners_ready());bool*flags[]={&poll,&emulate,&s_cc1101_jamming};for(unsigned i=0;i<3;i++){*flags[i]=true;assert(!rf433_rx_owners_ready());*flags[i]=false;}void**owners[]={&s_cc1101_cap_task,&s_cc1101_rep_task,&s_wx_task,&s_alm_task,&bs.task,&zw.task,&tp.task};for(unsigned i=0;i<7;i++){*owners[i]=(void*)1;assert(!rf433_rx_owners_ready());*owners[i]=NULL;assert(rf433_rx_owners_ready());}}
''')
 def test_task_create_failure_unwinds_real_startup(self):
  f=fn(self.m,'show_rf433_ook_scan_screen');a=f.index('    esp_err_t err = rf433_ook_rx_begin();');tail=f[a:]
  self.native('task-startup',r'''
#define ESP_OK 0
#define pdPASS 1
#define tskIDLE_PRIORITY 0
#define __ATOMIC_RELEASE 3
typedef int esp_err_t;static int fail,handler,labels;static void*s_rf433_scan_task,*s_rf433_scan_status;
static unsigned s_rf433_scan_epoch=8;static bool s_rf433_scan_stop=true;
static void s_rf433_scan_task_fn(void*a){(void)a;}
static int rf433_ook_rx_begin(void){if(fail==1)return 9;handler++;return 0;}
static void rf433_ook_rx_end(void){assert(handler);handler--;}
static void lv_label_set_text(void*p,const char*t){(void)p;(void)t;labels++;}
static int xTaskCreate(void(*fn)(void*),const char*n,int sz,void*a,int pri,void**t){(void)fn;(void)n;assert(sz==6144&&(uintptr_t)a==8&&pri==2);if(fail==2)return 0;*t=(void*)1;return 1;}
static void start(void){
'''+tail+r'''
int main(void){fail=1;start();assert(!handler&&!s_rf433_scan_task&&s_rf433_scan_stop);fail=2;start();assert(!handler&&!s_rf433_scan_task&&s_rf433_scan_stop);fail=0;start();assert(handler&&s_rf433_scan_task&&!s_rf433_scan_stop&&labels==2);}
''')

 def test_fox_refusal_restores_current_vibration(self):
  f=fn(self.m,'show_rf433_foxhunt_screen');prefix=f[:f.index('    gpio_config_t io_cfg')]
  self.native('fox-refusal',r'''
#define ESP_OK 0
#define RF_HAT_RF433_RX_GPIO 9
typedef int esp_err_t;static void*s_rf433_fox_tmr,*s_rf433_fox_bar,*s_rf433_fox_lbl,*s_rf433_fox_hbtn,*s_rf433_fox_status;
static bool s_rf433_fox_isr_installed;static int s_rf433_fox_edges,s_rf433_fox_rate;
static int g_vibtest_strength_pct=17,s_rf433_fox_saved_vib_pct=100;static void(*g_screen_stop_fn)(void);
static void lv_timer_del(void*t){(void)t;}static void gpio_isr_handler_remove(int n){(void)n;}
static void create_function_page_base(const char*t){(void)t;}
static void rf433_foxhunt_screen_stop(void){g_vibtest_strength_pct=s_rf433_fox_saved_vib_pct;}
static int rf433_rx_prepare(void){return 1;}
static void s_cc1101_stub_screen(const char*t,const char*m){(void)t;(void)m;assert(g_screen_stop_fn);g_screen_stop_fn();}
'''+prefix+'}\n'+r'''
int main(void){show_rf433_foxhunt_screen();assert(g_vibtest_strength_pct==17&&"failed receiver admission must preserve current vibration setting");}
''')

 def test_ir_release_prepare_integrated(self):
  # Compile actual production teardown + prepare together, not a status-only stub.
  release = fn(self.ir,'ir_hat_release') if 'bool ir_hat_release(void)' in self.ir else ''
  self.native('ir-release-prepare',r'''
#define ESP_OK 0
#define ESP_FAIL 8
#define ESP_ERR_INVALID_STATE 1
#define ESP_LOGE(...) ((void)0)
#define RF_HAT_IR_TX_GPIO 8
#define RF_HAT_IR_RX_GPIO 9
#define RF_HAT_RF433_TX_GPIO 8
#define GPIO_MODE_OUTPUT 1
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_DISABLE 0
#define LEDC_LOW_SPEED_MODE 0
#define IR_JAM_LEDC_CHANNEL 5
#define pdMS_TO_TICKS(x) (x)
typedef int esp_err_t;typedef int gpio_num_t;typedef unsigned TickType_t;
typedef struct{uint64_t pin_bit_mask;int mode,pull_up_en,pull_down_en,intr_type;}gpio_config_t;
static void *s_tx_chan,*s_rx_chan,*s_tx_enc,*s_rx_queue,*s_cap_task;
static bool s_init,s_jamming,s_jam_configured,s_tx_enabled,s_rx_enabled,s_rx_healthy,s_cap_cancel;
static int fail,configs,resets,queue_deletes,encoder_deletes,tx_disables,rx_disables;
static unsigned now,release_at;static int tx_state,rx_state;
static unsigned xTaskGetTickCount(void){return now;}
static void vTaskDelay(unsigned n){now+=n;if(release_at&&now>=release_at)s_cap_task=NULL;}
static bool nrf24_hat_ready(void){return true;}static bool rf433_ook_quiesce(void){return true;}
static bool rf433_rx_owners_ready(void){return true;}static bool rf433_hat_quiesce(void){return true;}
static bool cc1101_is_init(void){return false;}static bool nrf24_is_init(void){return false;}static bool rfid_manager_is_init(void){return false;}
static void cc1101_deinit(void){}static void nrf24_deinit(void){}static void rfid_manager_deinit(void){}static void rf433_hat_deinit(void){}
static bool ir_hat_is_init(void){return s_init;}static bool ir_hat_is_jamming(void){return s_jamming;}
static int ledc_stop(int m,int c,int v){(void)m;(void)c;(void)v;return fail==1?8:0;}
static int rmt_disable(void*p){int *state=p==(void*)1?&tx_state:&rx_state;if(p==(void*)1)tx_disables++;else rx_disables++;if(fail==(p==(void*)1?2:5))return 8;assert(*state==1||*state==2);*state=0;return 0;}
static int rmt_del_channel(void*p){int *state=p==(void*)1?&tx_state:&rx_state;if(fail==(p==(void*)1?3:6))return 8;assert(*state==0);*state=-1;return 0;}
static int rmt_del_encoder(void*p){assert(p==(void*)3);if(fail==4)return 8;encoder_deletes++;return 0;}
static void vQueueDelete(void*p){assert(p==(void*)4&&rx_state==-1&&!s_rx_chan&&!s_cap_task);queue_deletes++;}
static int gpio_reset_pin(int p){(void)p;resets++;return fail==7?8:0;}
static int gpio_config(const gpio_config_t*p){(void)p;configs++;return 0;}
static int gpio_set_level(int p,int v){(void)p;(void)v;return 0;}
''' + fn(self.ir,'ir_hat_quiesce') + release + fn(self.ir,'ir_hat_deinit') + fn(self.m,'rf433_rx_prepare') + r'''
static void setup(bool jam){s_tx_chan=(void*)1;s_rx_chan=(void*)2;s_tx_enc=(void*)3;s_rx_queue=(void*)4;s_cap_task=NULL;s_tx_enabled=s_rx_enabled=s_rx_healthy=true;s_init=!jam;s_jamming=jam;tx_state=rx_state=1;configs=resets=queue_deletes=encoder_deletes=tx_disables=rx_disables=0;now=release_at=0;}
int main(void){
/* Parent repro: jammer reports init=false; successful LEDC stop + failed RX disable must still refuse. */
setup(true);fail=5;assert(rf433_rx_prepare()!=ESP_OK&&"actual IR release must refuse retained RX after stopping jammer");assert(!configs&&!resets&&s_rx_chan&&s_rx_queue);
fail=0;assert(rf433_rx_prepare()==ESP_OK&&!s_tx_chan&&!s_rx_chan&&!s_tx_enc&&!s_rx_queue&&configs==1);
/* Both status flags false must not bypass resource inspection. */
for(int f=1;f<=6;f++){setup(f==1);if(f!=1)s_init=false;fail=f;assert(rf433_rx_prepare()!=ESP_OK);assert(!configs&&!resets);if(f<=3)assert(s_tx_chan);if(f==4)assert(s_tx_enc);if(f>=5)assert(s_rx_chan&&s_rx_queue);fail=0;assert(rf433_rx_prepare()==ESP_OK&&!s_tx_chan&&!s_rx_chan&&!s_tx_enc&&!s_rx_queue);}
/* Successful disable followed by failed delete retries delete, not disable INIT state. */
setup(false);fail=3;assert(rf433_rx_prepare()!=0&&tx_disables==1&&tx_state==0);fail=0;assert(rf433_rx_prepare()==0&&tx_disables==1);
setup(false);fail=6;assert(rf433_rx_prepare()!=0&&rx_disables==1&&rx_state==0);fail=0;assert(rf433_rx_prepare()==0&&rx_disables==1);
/* Capture join refusal cannot touch channels or pins; bounded eventual retry works. */
setup(false);s_cap_task=(void*)5;fail=0;assert(rf433_rx_prepare()!=0&&!configs&&!resets&&tx_disables==0&&rx_disables==0);release_at=now+20;assert(rf433_rx_prepare()==0&&!s_cap_task);
setup(false);fail=7;assert(rf433_rx_prepare()!=0&&!configs);fail=0;assert(rf433_rx_prepare()==0);
setup(false);fail=0;assert(rf433_rx_prepare()==0&&queue_deletes==1&&encoder_deletes==1);assert(rf433_rx_prepare()==0&&queue_deletes==1&&encoder_deletes==1);
}
''')


 def test_ir_init_jammer_partial_cleanup_reentry(self):
  self.native('ir-init-jammer',r'''
#define ESP_OK 0
#define ESP_FAIL 8
#define IR_HAT_OK 0
#define IR_HAT_ERR_HW 4
#define IR_HAT_ERR_BUSY 6
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
#define RF_HAT_IR_TX_GPIO 8
#define RF_HAT_IR_RX_GPIO 9
#define IR_RMT_RES_HZ 1000000
#define IR_CARRIER_HZ 38000
#define IR_CARRIER_DUTY 0.33f
#define RMT_CLK_SRC_DEFAULT 0
#define LEDC_LOW_SPEED_MODE 0
#define IR_JAM_LEDC_CHANNEL 5
#define IR_JAM_LEDC_TIMER 3
#define LEDC_TIMER_8_BIT 8
#define LEDC_AUTO_CLK 0
#define LEDC_INTR_DISABLE 0
#define pdMS_TO_TICKS(x) (x)
typedef int ir_hat_err_t;typedef int esp_err_t;typedef unsigned TickType_t;
typedef struct{int clk_src,gpio_num,mem_block_symbols,resolution_hz,trans_queue_depth;struct{bool invert_out,invert_in,with_dma;}flags;}rmt_tx_channel_config_t;
typedef rmt_tx_channel_config_t rmt_rx_channel_config_t;
typedef struct{int frequency_hz;float duty_cycle;}rmt_carrier_config_t;
typedef struct{int unused;}rmt_copy_encoder_config_t;
typedef struct{int unused;}rmt_rx_done_event_data_t;
static bool s_rx_done_cb(void){return false;}
typedef struct{bool(*on_recv_done)(void);}rmt_rx_event_callbacks_t;
typedef struct{int speed_mode,duty_resolution,timer_num,freq_hz,clk_cfg;}ledc_timer_config_t;
typedef struct{int gpio_num,speed_mode,channel,timer_sel,duty,hpoint,intr_type;}ledc_channel_config_t;
static void*s_tx_chan,*s_rx_chan,*s_tx_enc,*s_rx_queue,*s_cap_task;
static bool s_init,s_jamming,s_jam_configured,s_tx_enabled,s_rx_enabled,s_rx_healthy,s_cap_cancel;
static int s_rx_core,fail,release_fail,tx_state=-1,rx_state=-1,queues,encoders,allocs,ledc_active;
static unsigned now;
static unsigned xTaskGetTickCount(void){return now;}static void vTaskDelay(unsigned t){now+=t;}
static int xPortGetCoreID(void){return 1;}
static void*xQueueCreate(int n,size_t b){(void)n;(void)b;if(fail==1)return NULL;assert(!queues);queues++;allocs++;return(void*)4;}
static void vQueueDelete(void*p){assert(p==(void*)4&&!s_rx_chan&&!s_cap_task);assert(queues==1);queues--;}
static int rmt_new_tx_channel(const void*c,void**p){(void)c;if(fail==2)return 8;assert(tx_state==-1&&!*p);tx_state=0;*p=(void*)1;allocs++;return 0;}
static int rmt_new_rx_channel(const void*c,void**p){(void)c;if(fail==6)return 8;assert(rx_state==-1&&!*p);rx_state=0;*p=(void*)2;allocs++;return 0;}
static int rmt_apply_carrier(void*p,const void*c){(void)p;(void)c;return fail==3?8:0;}
static int rmt_new_copy_encoder(const void*c,void**p){(void)c;if(fail==4)return 8;assert(!encoders&&!*p);encoders++;*p=(void*)3;allocs++;return 0;}
static int rmt_rx_register_event_callbacks(void*p,const void*c,void*q){(void)p;(void)c;(void)q;return fail==7?8:0;}
static int rmt_enable(void*p){int*t=p==(void*)1?&tx_state:&rx_state;assert(*t==0);if(fail==(p==(void*)1?5:8))return 8;*t=1;return 0;}
static int rmt_disable(void*p){int*t=p==(void*)1?&tx_state:&rx_state;assert(*t==1||*t==2);if(release_fail==1)return 8;*t=0;return 0;}
static int rmt_del_channel(void*p){int*t=p==(void*)1?&tx_state:&rx_state;assert(*t==0);if(release_fail==2)return 8;*t=-1;return 0;}
static int rmt_del_encoder(void*p){assert(p==(void*)3&&encoders==1&&tx_state==-1);if(release_fail==3)return 8;encoders--;return 0;}
static int gpio_reset_pin(int p){(void)p;assert(!s_tx_chan&&!s_rx_chan&&!ledc_active);return 0;}
static int ledc_timer_config(const void*p){(void)p;return fail==9?8:0;}
static int ledc_channel_config(const void*p){(void)p;ledc_active=1;return fail==10?8:0;}
static int ledc_stop(int m,int c,int v){(void)m;(void)c;(void)v;if(release_fail==4)return 8;ledc_active=0;return 0;}
static bool ir_hat_release(void);
static void ir_hat_deinit(void);
static ir_hat_err_t ir_hat_init(void);
''' + '\n'.join(fn(self.ir,n) for n in ['ir_hat_quiesce','ir_hat_release','ir_hat_deinit','ir_hat_init','ir_hat_jam_start','ir_hat_jam_stop']) + r'''
static void empty(void){assert(!s_tx_chan&&!s_rx_chan&&!s_tx_enc&&!s_rx_queue&&!queues&&!encoders&&tx_state==-1&&rx_state==-1&&!s_jamming&&!ledc_active);}
int main(void){
/* Every allocation/config/enable failure unwinds, and a fresh init succeeds. */
for(int f=1;f<=8;f++){fail=f;assert(ir_hat_init()==IR_HAT_ERR_HW);empty();fail=0;assert(ir_hat_init()==0&&s_init);assert(ir_hat_release());empty();}
/* Retained partial-init handles cannot be overwritten on reentry. */
fail=6;release_fail=1;assert(ir_hat_init()!=0&&!s_init&&s_tx_chan&&s_rx_queue);int before=allocs;fail=0;assert(ir_hat_init()!=0&&allocs==before);release_fail=0;assert(ir_hat_init()==0&&s_init);assert(ir_hat_release());empty();
/* Jammer entry refusal and retries after partial cleanup; no status-flag bypass. */
for(int f=1;f<=3;f++){fail=0;assert(ir_hat_init()==0);release_fail=f;assert(ir_hat_jam_start(0)!=0&&!s_init&&!s_jamming);before=allocs;assert(ir_hat_init()!=0&&allocs==before);release_fail=0;assert(ir_hat_jam_start(0)==0&&s_jamming&&!s_init);assert(ir_hat_init()==IR_HAT_ERR_BUSY);ir_hat_jam_stop();assert(s_init&&!s_jamming);assert(ir_hat_release());empty();}
/* Channel config can fail after enabling LEDC. Failed stop retains ownership. */
fail=10;release_fail=4;assert(ir_hat_jam_start(0)!=0&&s_jamming&&ledc_active);assert(!ir_hat_release()&&s_jamming);assert(ir_hat_jam_start(0)!=0&&"failed configuration must not become successful repeat start");release_fail=0;assert(ir_hat_release());empty();
fail=9;assert(ir_hat_jam_start(0)!=0);empty();fail=0;assert(ir_hat_jam_start(0)==0);release_fail=4;ir_hat_jam_stop();assert(s_jamming&&ledc_active&&!s_init);release_fail=0;ir_hat_jam_stop();assert(s_init&&!s_jamming);ir_hat_deinit();empty();
}
''')

if __name__=='__main__':unittest.main(verbosity=2)
