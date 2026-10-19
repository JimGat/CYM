#!/usr/bin/env python3
"""Production adapter/session/DSP plus extracted installed IDF I2S operations.

Synthetic DMA/RTOS clock is not physical audio qualification. SDK function bodies
are extracted at runtime rather than reimplementing their queue/current-pointer
policy. ISR dummy pointer storage is widened for the 64-bit host ABI; the read symbol
is renamed only to inject boundary faults around its unchanged body.
"""
from pathlib import Path
import ast, os, subprocess, hashlib, json
from audio_rta_sdk_slots import prepare
R=Path(__file__).resolve().parents[1]
D=Path(os.environ['CYM_TEST_OUT'])/'rta-input'; D.mkdir(parents=True,exist_ok=True)
M=R/'ESP32C5/managed_components/espressif__esp_codec_dev'
SDK=Path(os.environ.get('IDF_PATH','/home/dev/esp/esp-idf'))/'components/esp_driver_i2s/i2s_common.c'
sdk=SDK.read_text()
def extract(signature):
    start=sdk.index(signature); a=sdk.index('{',start); depth=1; b=a+1
    while depth:
        depth += (sdk[b]=='{')-(sdk[b]=='}'); b+=1
    return sdk[start:b]
functions=[extract(n) for n in ('static bool i2s_dma_rx_callback(', 'static bool i2s_dma_tx_callback(', 'esp_err_t i2s_channel_write(', 'esp_err_t i2s_channel_read(')]
(D/'sdk-functions.c').write_text('\n\n'.join(functions).replace('uint32_t dummy;', 'uintptr_t dummy;').replace('esp_err_t i2s_channel_read(', 'esp_err_t sdk_channel_read('))
(D/'sdk-provenance.json').write_text(json.dumps(dict(path=str(SDK),sha256=hashlib.sha256(sdk.encode()).hexdigest(),functions=[hashlib.sha256(f.encode()).hexdigest() for f in functions],host_adaptation='ISR dummy uint32_t -> uintptr_t; read symbol renamed for boundary fault wrapper; bodies otherwise unchanged'),indent=2))
def literals(file):
    tree=ast.parse((R/'tests'/file).read_text())
    return [n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='write_text' and n.args and isinstance(n.args[0],ast.Constant)]
board=literals('run_audio_rta_board_host.py'); life=literals('run_audio_rta_lifecycle_host.py')
for name,mark in [('esp_err.h','#pragma once\ntypedef int'),('esp_log.h','#define ESP_LOGE'),('sdkconfig.h','#define CONFIG_CODEC')]:
    text=next(s for s in board if s.startswith(mark))
    if name=='esp_err.h': text+='\n#define ESP_ERR_NO_MEM 1\n'
    (D/name).write_text(text)
(D/'driver').mkdir(exist_ok=True);(D/'freertos').mkdir(exist_ok=True)
(D/'driver/i2c_master.h').write_text(next(s for s in board if 'i2c_master_bus_add_device' in s and 'typedef void*' in s))
i2s=next(s for s in board if 'typedef struct channel' in s)
i2s=i2s.replace('typedef struct channel{int on;}*i2s_chan_handle_t;', 'typedef struct channel *i2s_chan_handle_t;')
i2s=i2s.replace('typedef struct{int dummy;}i2s_event_data_t;', 'typedef struct{void *dma_buf; size_t size;}i2s_event_data_t;')
i2s=i2s.replace('bool(*on_recv_q_ovf)(i2s_chan_handle_t,i2s_event_data_t*,void*);', 'bool(*on_recv_q_ovf)(i2s_chan_handle_t,i2s_event_data_t*,void*); bool(*on_recv)(i2s_chan_handle_t,i2s_event_data_t*,void*); bool(*on_sent)(i2s_chan_handle_t,i2s_event_data_t*,void*); bool(*on_send_q_ovf)(i2s_chan_handle_t,i2s_event_data_t*,void*);')
# Use installed HWv2 default macro (BOTH), not a mono-only stub.
macro=prepare(D, SDK.parents[2])
i2s=i2s.replace('struct{int bits,mode,slot_mask;}slot_cfg;', 'struct{int data_bit_width,slot_bit_width,slot_mode,slot_mask,ws_width;bool ws_pol,bit_shift,left_align,big_endian,bit_order_lsb;}slot_cfg;')
i2s=i2s.replace('#define I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(a,b) {a,b,I2S_STD_SLOT_BOTH}', '#define I2S_SLOT_BIT_WIDTH_AUTO 0\n#define I2S_SLOT_MODE_STEREO 2\n#define I2S_STD_SLOT_LEFT 1\n#define I2S_STD_SLOT_RIGHT 2\n#define I2S_STD_SLOT_BOTH 3\n'+macro)
(D/'driver/i2s_std.h').write_text(i2s)
port=next(s for s in life if '#define portMUX_TYPE' in s)
start=port.index('static int64_t esp_timer_get_time('); end=port.index('\n',start)
port=port[:start]+ 'static int64_t simulated_us; static void advance_to(int64_t); static void control_tick(void); static int64_t esp_timer_get_time(void){advance_to(simulated_us+30);control_tick();return simulated_us;}' +port[end:]
port=port.replace('static void vTaskDelay(unsigned n){usleep(n*1000);}', 'static void vTaskDelay(unsigned n){advance_to(simulated_us+n*10000);}')
(D/'audio_rta_host_port.h').write_text('#pragma once\n'+port)
(D/'freertos/FreeRTOS.h').write_text('#include "audio_rta_host_port.h"\n')
(D/'freertos/task.h').write_text('#include "audio_rta_host_port.h"\n')
(D/'host.c').write_text(r'''

#define AUDIO_RTA_HOST 1
#include "audio_rta.c"
#include "audio_rta_board.c"
#include <math.h>
#define SOC_CACHE_INTERNAL_MEM_VIA_L1CACHE 0
#define I2S_CHAN_STATE_RUNNING 1
#define I2S_DIR_TX 0
#define I2S_DIR_RX 1
#define pdFALSE 0
#define I2S_NULL_POINTER_CHECK(tag,p) do{if(!(p))return ESP_ERR_INVALID_ARG;}while(0)
#define ESP_RETURN_ON_FALSE(cond,err,...) do{if(!(cond))return err;}while(0)
typedef int BaseType_t;
typedef void *gdma_channel_handle_t;
typedef struct {uint8_t *buf;} lldesc_t;
typedef struct {uintptr_t rx_eof_desc_addr,tx_eof_desc_addr;} gdma_event_data_t;
typedef struct queue {void *items[3];int count;} queue_t;
struct channel {
 int dir,state,on,binary;queue_t queue,*msg_queue;
 struct {size_t buf_size,rw_pos;void*curr_ptr;bool auto_clear_before_cb,auto_clear_after_cb;} dma;
 i2s_event_callbacks_t callbacks;void *user_data;
 lldesc_t desc[4];uint8_t buffers[4][512];int eof,slots;int64_t next,epoch;
};
static i2s_chan_handle_t tx,rx;
static int mode,phase,live_channels,live_dev,reads,writes,overflow_events,stopped,fault_injected;
static int64_t start_us; static uint64_t pcm_index;
static int gap_stage,control_stage,observed_resets,held_checked;
static audio_rta_snapshot_t held;
static int fresh_high,fresh_bass;

static int xQueueReceive(queue_t*q,void*out,unsigned ticks);
static int xQueueReceiveFromISR(queue_t*q,void*out,BaseType_t*y){(void)y;assert(q->count);memcpy(out,&q->items[0],sizeof(void*));memmove(q->items,q->items+1,(--q->count)*sizeof(void*));return 1;}
static int xQueueSendFromISR(queue_t*q,const void*in,BaseType_t*y){(void)y;assert(q->count<3);memcpy(&q->items[q->count++],in,sizeof(void*));return 1;}
static int xQueueIsQueueFullFromISR(queue_t*q){return q->count==3;}
static int uxQueueSpacesAvailable(queue_t*q){return 3-q->count;}
static int xSemaphoreTake(int n,unsigned ticks){(void)ticks;return n;}
static void xSemaphoreGive(int n){(void)n;}
#include "sdk-functions.c"
#include "sdk-slots.c"
/* Faults are applied at the API boundary, without replacing queue operations. */
esp_err_t i2s_channel_read(i2s_chan_handle_t h,void*p,size_t n,size_t*out,unsigned timeout){
 reads++;
 if(reads==60&&mode>=8&&mode<=13){
  fault_injected=1;
  if(mode==8){assert(!sdk_channel_read(h,p,126,out,timeout));return ESP_ERR_TIMEOUT;}
  if(mode==9){*out=0;return ESP_OK;}
  if(mode==10)return sdk_channel_read(h,p,3,out,timeout);
  if(mode==11){*out=0;return ESP_ERR_TIMEOUT;}
  if(mode==12){assert(!sdk_channel_read(h,p,126,out,timeout));return ESP_FAIL;}
  if(mode==13){h->binary=0;h->callbacks.on_recv_q_ovf(h,NULL,h->user_data);}
 }
 return sdk_channel_read(h,p,n,out,timeout);
}

/* Deterministic 48k LRCLK, 16-bit DMA. Producer rate follows actual C5 HAL
 * slot selection and TRM 35.10.1.1, not the requested mono allocation size.
 * Queue/current-pointer/eviction policy executes SDK bodies above, not a model.
 * No per-read sleep. Clocking remains enabled even with no application TX writes.
 */
static void eof_event(i2s_chan_handle_t h){
 int slot=h->eof++%4;
 if(h->dir==I2S_DIR_RX){
  int16_t*p=(int16_t*)h->buffers[slot];
  for(int i=0;i<256;i++,pcm_index++)p[i]=(int16_t)(10000*sin(2*3.141592653589793*1000*pcm_index/48000));
 }
 gdma_event_data_t event={.rx_eof_desc_addr=(uintptr_t)&h->desc[slot],.tx_eof_desc_addr=(uintptr_t)&h->desc[slot]};
 if(h->dir==I2S_DIR_RX){if(h->queue.count==3)overflow_events++;i2s_dma_rx_callback(NULL,&event,h);}
 else i2s_dma_tx_callback(NULL,&event,h);
 h->next=h->epoch+(int64_t)(h->eof+1)*256000000/(48000*h->slots);
}
static void advance_to(int64_t target){
 for(;;){i2s_chan_handle_t h=NULL;
  if(tx&&tx->on&&tx->next<=target)h=tx;
  if(rx&&rx->on&&rx->next<=target&&(!h||rx->next<h->next))h=rx;
  if(!h)break;simulated_us=h->next;eof_event(h);
 }
 simulated_us=target;
}
static int xQueueReceive(queue_t*q,void*out,unsigned ticks){
 int64_t deadline=simulated_us+ticks*1000;bool blocked=!q->count;
 while(!q->count){
  int64_t next=deadline;
  if(tx&&tx->on&&tx->next<next)next=tx->next;
  if(rx&&rx->on&&rx->next<next)next=rx->next;
  advance_to(next);if(!q->count&&simulated_us>=deadline)return 0;
 }
 if(blocked&&mode==2)advance_to(simulated_us+6000);
 BaseType_t unused=0;return xQueueReceiveFromISR(q,out,&unused);
}
static uint8_t regs[256];static int startup_backlog;
int audio_codec_delete_codec_if(const audio_codec_if_t*c){int e=c->close(c);free((void*)c);return e;}
esp_err_t i2s_new_channel(const i2s_chan_config_t*c,i2s_chan_handle_t*t,i2s_chan_handle_t*r){
 assert(c->dma_desc_num==4&&c->dma_frame_num==256&&c->auto_clear&&!tx&&!rx);
 tx=calloc(1,sizeof(*tx));rx=calloc(1,sizeof(*rx));assert(tx&&rx);tx->dir=0;rx->dir=1;
 *t=tx;*r=rx;live_channels=2;
 for(int j=0;j<2;j++){i2s_chan_handle_t h=j?rx:tx;h->msg_queue=&h->queue;h->dma.buf_size=512;h->dma.auto_clear_after_cb=c->auto_clear;for(int i=0;i<4;i++)h->desc[i].buf=h->buffers[i];}
 return 0;
}
esp_err_t i2s_channel_init_std_mode(i2s_chan_handle_t h,const i2s_std_config_t*c){
 assert(h&&c->clk_cfg.sample_rate_hz==48000&&c->slot_cfg.data_bit_width==16&&c->slot_cfg.slot_mode==1);
 i2s_dev_t dev={0};i2s_hal_context_t hal={.dev=&dev};
 i2s_hal_slot_config_t slot={.data_bit_width=c->slot_cfg.data_bit_width,.slot_bit_width=c->slot_cfg.slot_bit_width,.slot_mode=c->slot_cfg.slot_mode,
 .std={.slot_mask=c->slot_cfg.slot_mask,.ws_width=c->slot_cfg.ws_width,.ws_pol=c->slot_cfg.ws_pol,.bit_shift=c->slot_cfg.bit_shift,.left_align=c->slot_cfg.left_align,.big_endian=c->slot_cfg.big_endian,.bit_order_lsb=c->slot_cfg.bit_order_lsb}};
 if(h==rx)i2s_hal_std_set_rx_slot(&hal,false,&slot);else i2s_hal_std_set_tx_slot(&hal,false,&slot);
 unsigned mask=h==rx?dev.rx_mask:dev.tx_mask;h->slots=__builtin_popcount(mask);assert(h->slots==1||h->slots==2);
 printf("slot_config dir=%s requested=%d effective_mask=%u dma_slots=%d\n",h==rx?"RX":"TX",c->slot_cfg.slot_mask,mask,h->slots);
 return 0;
}
esp_err_t i2s_channel_register_event_callback(i2s_chan_handle_t h,const i2s_event_callbacks_t*c,void*p){h->callbacks=*c;h->user_data=p;return 0;}
esp_err_t i2s_channel_enable(i2s_chan_handle_t h){h->on=h->state=h->binary=1;h->epoch=simulated_us+(h==rx?phase:0);h->next=h->epoch+256000000/(48000*h->slots);return 0;}
esp_err_t i2s_channel_disable(i2s_chan_handle_t h){h->on=h->state=h->binary=0;return 0;}
esp_err_t i2s_del_channel(i2s_chan_handle_t h){assert(!h->on);if(h==tx)tx=NULL;else rx=NULL;free(h);live_channels--;return 0;}
esp_err_t i2c_master_bus_add_device(void*b,const i2c_device_config_t*c,i2c_master_dev_handle_t*out){assert(b==(void*)1&&c->device_address==0x18);*out=(void*)2;live_dev++;return 0;}
esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t b){assert(b==(void*)2);live_dev--;return 0;}
esp_err_t i2c_master_transmit(i2c_master_dev_handle_t b,const uint8_t*p,size_t n,int timeout){assert(b==(void*)2&&n==2&&timeout==20);advance_to(simulated_us+300);regs[p[0]]=p[1];return 0;}
esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t b,const uint8_t*p,size_t n,void*out,size_t z,int timeout){assert(b==(void*)2&&n==1&&z==1&&timeout==20);advance_to(simulated_us+400);*(uint8_t*)out=regs[p[0]];if(p[0]==0x44&&rx&&rx->on&&!startup_backlog){startup_backlog=1;advance_to(simulated_us+100000);}return 0;}
static void control_tick(void){
 if(!rx||!rx->on||!owner)return;
 if(!start_us)start_us=simulated_us;
 int64_t elapsed=simulated_us-start_us;
 /* Check histories, not read-call counts: no valid stale windows after gaps. */
 if(latest.history_resets>(unsigned)observed_resets){
  observed_resets=latest.history_resets;
  if(latest.state!=RTA_FROZEN)assert(!latest.spectrum.valid);
 }
 if(latest.spectrum.valid&&latest.state==RTA_RUNNING){
  assert(latest.spectrum.samples>=4096);
  fresh_high++;
  if(latest.spectrum.valid==0xffffff){assert(latest.spectrum.samples>=32768);fresh_bass++;}
 }
 if((mode==3||mode==14)&&elapsed>1000000&&!fault_injected){fault_injected=1;if(mode==3)rx->binary=0;else tx->binary=0;}
 /* Real SDK ISR overflows from bounded scheduling gaps, then actual recovery. */
 if(mode==4&&gap_stage<6&&elapsed>(gap_stage+1)*400000LL){gap_stage++;advance_to(simulated_us+40000);}
 if(mode==5&&gap_stage<2&&elapsed>(gap_stage+1)*750000LL){gap_stage++;advance_to(simulated_us+40000);}
 if(mode==6){
  if(!control_stage&&elapsed>1000000){control_stage=1;audio_rta_controls(latest.generation,true,false,0,false);}
  if(control_stage==1&&latest.state==RTA_FROZEN){held=latest;control_stage=2;advance_to(simulated_us+40000);}
  if(control_stage==2&&elapsed>1300000){assert(latest.state==RTA_FROZEN&&latest.sequence==held.sequence&&!memcmp(&latest.spectrum,&held.spectrum,sizeof(held.spectrum)));held_checked=1;control_stage=3;audio_rta_controls(latest.generation,false,true,0,false);}
 }
 if(mode==7&&!control_stage&&elapsed>1000000){control_stage=1;audio_rta_controls(latest.generation,true,true,6,true);}
 if(elapsed>3000000&&!stopped){stopped=1;audio_rta_stop(latest.generation);}
}
int main(int argc,char**argv){assert(argc==3);mode=atoi(argv[1]);phase=atoi(argv[2]);uint32_t gen;
 assert(!audio_rta_start((void*)1,&gen));
 for(int i=0;i<10000;i++){if(audio_rta_closed()&&!live_tasks)break;usleep(1000);}
 assert(audio_rta_closed()&&!live_tasks&&!live_alloc&&!live_channels&&!live_dev);
 audio_rta_snapshot_t s;assert(audio_rta_snapshot(gen,&s));
 printf("mode=%d phase=%d simulated_us=%lld reads=%llu overrun_batches=%u ISR_overflows=%d resets=%u sequence=%u history=%llu frames=%u valid=%06x rms=%f peak=%f\n",mode,phase,(long long)simulated_us,(unsigned long long)s.read_calls,s.overruns,overflow_events,s.history_resets,s.sequence,(unsigned long long)s.spectrum.samples,s.spectrum.frames,s.spectrum.valid,s.spectrum.rms,s.spectrum.sample_peak);
 fflush(stdout);
 if(mode==3||mode==13||mode==14){assert(fault_injected&&s.state==RTA_ERROR&&s.error==ESP_ERR_INVALID_STATE&&"real SDK invalid-state must terminate, not masquerade as recoverable overflow");return 0;}
 if(mode>=10&&mode<=12){assert(fault_injected&&s.state==RTA_ERROR&&s.error==(mode==11?ESP_ERR_TIMEOUT:ESP_FAIL));return 0;}
 assert(s.sequence>50&&s.spectrum.samples>=4096&&s.spectrum.valid&&s.spectrum.frames>0&&s.spectrum.rms>-20&&s.spectrum.sample_peak>-15&&fresh_high&&"recover and process actual nonzero PCM, not fabricated bands");
 if(mode==4){assert(gap_stage==6&&s.overruns>=7&&s.history_resets==s.overruns&&s.spectrum.samples<32768&&s.spectrum.valid!=0xffffff&&"higher bands must progress independently during recurring bass warmup");}
 else assert(s.spectrum.samples>=32768&&s.spectrum.valid==0xffffff&&fresh_bass);
 if(mode==5)assert(gap_stage==2&&s.overruns>=3&&s.history_resets==s.overruns);
 if(mode==6)assert(held_checked&&control_stage==3&&s.history_resets>s.overruns);
 if(mode==7)assert(control_stage==1&&s.gain_db==6&&s.history_resets>s.overruns);
 if(mode==8||mode==9)assert(fault_injected&&s.state==RTA_CLOSED);
 assert(s.read_calls==(unsigned)reads);
 int best=-1;for(int i=0;i<24;i++)if((s.spectrum.valid&(1u<<i))&&(best<0||s.spectrum.band[i]>s.spectrum.band[best]))best=i;
 assert(best>=0&&audio_rta_dsp_edge(best)<=1000&&audio_rta_dsp_edge(best+1)>=1000&&s.spectrum.band[best]>-25&&"processed known PCM must populate the actual 1kHz band");
 return 0;
}

''')
incs=[D,R/'ESP32C5/main',M/'include',M/'interface',M/'device/include',M/'device/es8311',M/'device',M/'device/priv_include']
cmd=['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-pthread','-DCONFIG_CODEC_ES8311_SUPPORT=1','-include','stdlib.h',*['-I'+str(p) for p in incs],str(D/'host.c'),str(R/'ESP32C5/main/audio_rta_dsp.c'),str(M/'device/es8311/es8311.c'),str(M/'esp_codec_dev_vol.c'),'-lm','-o',str(D/'host')]
(D/'compile-command.json').write_text(json.dumps(cmd))
subprocess.run(cmd,check=True)
results=[subprocess.run([str(D/'host'),str(mode),str(phase)]).returncode for mode in range(1,15) for phase in (0,100,2600,5200)]
assert not any(results),results
