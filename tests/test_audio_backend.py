from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'ESP32C5/components/cym_doom'
OUT=ROOT/'.hermes/doom-prototype/backend-host'
STUB=r"""#ifndef AUDIO_BACKEND_STUB_H
#define AUDIO_BACKEND_STUB_H
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#define ESP_OK 0
#define ESP_FAIL -1
#define I2S_NUM_0 0
#define I2S_ROLE_MASTER 1
#define I2S_GPIO_UNUSED -1
#define I2S_DATA_BIT_WIDTH_16BIT 16
#define I2S_SLOT_MODE_MONO 1
#define ESP_CODEC_DEV_WORK_MODE_DAC 1
#define ES8311_CODEC_DEFAULT_ADDR 0x30
void backend_log(const char *tag,const char *fmt,...);
#define ESP_LOGI backend_log
#define ESP_LOGE backend_log
#define ESP_LOGW backend_log
typedef void *i2s_chan_handle_t;
typedef struct {int dma_desc_num,dma_frame_num;bool auto_clear;} i2s_chan_config_t;
#define I2S_CHANNEL_DEFAULT_CONFIG(a,b) {0}
typedef struct {int rate;} mock_clk;
typedef struct {int bits,mode,data_bit_width,slot_bit_width,slot_mask,slot_mode;} mock_slot;
#define I2S_STD_CLK_DEFAULT_CONFIG(r) {r}
#define I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(b,m) {b,m,b,16,1,m}
typedef struct {mock_clk clk_cfg;mock_slot slot_cfg;struct {int mclk,bclk,ws,dout,din;} gpio_cfg;} i2s_std_config_t;
typedef struct {int port,addr;void *bus_handle;} audio_codec_i2c_cfg_t;
typedef struct audio_codec_ctrl_if_t {int (*read_reg)(const struct audio_codec_ctrl_if_t*,int,int,void*,int);} audio_codec_ctrl_if_t;
typedef struct {int sample_rate,channel,bits_per_sample;} esp_codec_dev_sample_info_t;
typedef struct audio_codec_if_t {int (*mute)(const struct audio_codec_if_t*,bool);int (*enable)(const struct audio_codec_if_t*,bool);int (*set_fs)(const struct audio_codec_if_t*,esp_codec_dev_sample_info_t*);int (*set_vol)(const struct audio_codec_if_t*,float);} audio_codec_if_t;
typedef struct {const audio_codec_ctrl_if_t *ctrl_if;int codec_mode,pa_pin;bool master_mode,use_mclk;struct {float pa_voltage,codec_dac_voltage;} hw_gain;} es8311_codec_cfg_t;
int i2s_new_channel(const i2s_chan_config_t*,i2s_chan_handle_t*,void*);
int i2s_channel_init_std_mode(i2s_chan_handle_t,const i2s_std_config_t*);
int i2s_channel_enable(i2s_chan_handle_t);
int i2s_channel_disable(i2s_chan_handle_t);
int i2s_del_channel(i2s_chan_handle_t);
int i2s_channel_write(i2s_chan_handle_t,const void*,size_t,size_t*,unsigned);
const audio_codec_ctrl_if_t *audio_codec_new_i2c_ctrl(audio_codec_i2c_cfg_t*);
const audio_codec_if_t *es8311_codec_new(es8311_codec_cfg_t*);
int audio_codec_delete_codec_if(const audio_codec_if_t*);
int audio_codec_delete_ctrl_if(const audio_codec_ctrl_if_t*);
#endif
"""
HARNESS=r"""#include "backend_stub.h"
#include "doom_audio.h"
#include "doom_metrics.h"
doom_metrics_t doom_metrics;
#include "doom_audio.c"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int seq,fail_at=-1,tx_live,tx_on,ctrl_live,codec_live,amp_on,short_write;
static int read_fail,bad_reg,muted,codec_enabled,amp_off_fail;
static float observed_volume;static unsigned started_logs;
#include <stdarg.h>
void backend_log(const char*tag,const char*fmt,...){(void)tag;char line[1024];va_list ap;va_start(ap,fmt);vsnprintf(line,sizeof(line),fmt,ap);va_end(ap);
if(strstr(line,"AUDIO_STARTED")){assert(strstr(line,"volume_db=9"));assert(!strstr(line,"volume_db=-30"));assert(strstr(line,"audible=unconfirmed"));assert(observed_volume==9.0f);assert(amp_on&&codec_enabled&&!muted&&tx_on&&audio_task&&audio_queue);started_logs++;}}
static int read_reg(const audio_codec_ctrl_if_t*c,int reg,int width,void*out,int len){(void)c;assert(width==1&&len==1);if(read_fail)return -1;
unsigned v=0;switch(reg){case 0x00:v=0x80;break;case 0x01:v=0xbf;break;case 0x02:v=0x18;break;case 0x06:v=3;break;case 0x09:case 0x0a:v=0x0c;break;case 0x0d:v=1;break;case 0x14:v=0x1a;break;case 0x32:v=0x8a;break;case 0x37:v=8;break;}if(reg==0x12)v=codec_enabled?0:2;if(reg==0x14)v=codec_enabled?0x1a:0;if(reg==0x31)v=muted?0x60:0;if(reg==bad_reg)v^=0x40;*(unsigned char*)out=v;return 0;}
static audio_codec_ctrl_if_t ci={read_reg};
static int op(void){return seq++==fail_at?-1:0;}
void *cym_game_audio_bus(void){return &ci;}
bool cym_game_audio_amp(bool on){if(op()||(!on&&amp_off_fail))return false;amp_on=on;return true;}
int i2s_new_channel(const i2s_chan_config_t *c,i2s_chan_handle_t *p,void *rx){assert(!rx);assert(c->dma_desc_num==4&&c->dma_frame_num==256&&c->auto_clear);if(op())return -1;*p=&tx_live;tx_live=1;return 0;}
int i2s_channel_init_std_mode(i2s_chan_handle_t t,const i2s_std_config_t*c){assert(t);assert(c->clk_cfg.rate==22050&&c->slot_cfg.bits==16&&c->slot_cfg.mode==1);assert(c->gpio_cfg.mclk==-1&&c->gpio_cfg.din==-1);
#if CONFIG_BOARD_WS_C5_28
assert(c->gpio_cfg.bclk==24&&c->gpio_cfg.ws==25&&c->gpio_cfg.dout==26);
#else
assert(c->gpio_cfg.bclk==23&&c->gpio_cfg.ws==10&&c->gpio_cfg.dout==25);
#endif
return op();}
int i2s_channel_enable(i2s_chan_handle_t t){assert(t);if(op())return -1;tx_on=1;return 0;}
int i2s_channel_disable(i2s_chan_handle_t t){assert(t);if(op())return -1;tx_on=0;return 0;}
int i2s_del_channel(i2s_chan_handle_t t){assert(t&&!tx_on);if(op())return -1;tx_live=0;return 0;}
int i2s_channel_write(i2s_chan_handle_t t,const void *p,size_t n,size_t *out,unsigned timeout){assert(t&&tx_on&&p);assert(n==512&&timeout==50);*out=short_write?n-2:n;return op();}
const audio_codec_ctrl_if_t *audio_codec_new_i2c_ctrl(audio_codec_i2c_cfg_t*c){assert(c->port==0&&c->addr==0x30&&c->bus_handle==&ci);if(op())return NULL;ctrl_live=1;return &ci;}
static int mute(const audio_codec_if_t*c,bool v){(void)c;if(op())return -1;muted=v;return 0;}
static int enable(const audio_codec_if_t*c,bool v){(void)c;if(op())return -1;codec_enabled=v;return 0;}
static int fs(const audio_codec_if_t*c,esp_codec_dev_sample_info_t*f){(void)c;assert(f->sample_rate==22050&&f->bits_per_sample==16&&f->channel==1);return op();}
static int vol(const audio_codec_if_t*c,float db){(void)c;assert(db==9.0f);assert(muted&&!codec_enabled&&!amp_on&&!tx_on);observed_volume=db;return op();}
static const audio_codec_if_t co={mute,enable,fs,vol};
const audio_codec_if_t *es8311_codec_new(es8311_codec_cfg_t*c){assert(c->hw_gain.pa_voltage==3.3f&&c->hw_gain.codec_dac_voltage==3.3f);assert(c->ctrl_if==&ci&&!c->master_mode&&!c->use_mclk&&c->pa_pin==-1&&c->codec_mode==1);if(op())return NULL;codec_live=1;codec_enabled=muted=0;return &co;}
int audio_codec_delete_codec_if(const audio_codec_if_t*c){assert(c==&co);if(op())return -1;codec_live=0;return 0;}
int audio_codec_delete_ctrl_if(const audio_codec_ctrl_if_t*c){assert(c==&ci);if(op())return -1;ctrl_live=0;return 0;}
static void (*task_fn)(void*);
static int task_state,task_deleted,queue_fail,task_fail,task_block;
typedef struct mock_queue {unsigned n,head,tail;size_t size;unsigned char data[8][520];} mock_queue;
QueueHandle_t xQueueCreate(unsigned n,size_t size){assert(n<=8&&size<=520);if(queue_fail)return NULL;mock_queue*q=calloc(1,sizeof(*q));q->size=size;return q;}
unsigned uxQueueMessagesWaiting(QueueHandle_t q){return q->n;}
int xQueueSend(QueueHandle_t q,const void*p,int ticks){assert(!ticks);if(q->n==8)return 0;memcpy(q->data[q->tail++%8],p,q->size);q->n++;return 1;}
int xQueueReceive(QueueHandle_t q,void*p,int ticks){assert(!ticks);if(!q->n)return 0;memcpy(p,q->data[q->head++%8],q->size);q->n--;return 1;}
void vQueueDelete(QueueHandle_t q){free(q);}
int xTaskCreate(void(*f)(void*),const char*n,unsigned st,void*a,int pri,TaskHandle_t*h){(void)n;(void)st;(void)a;(void)pri;if(task_fail)return 0;task_fn=f;*h=&task_state;task_state=eRunning;return 1;}
int eTaskGetState(TaskHandle_t h){assert(h);return task_state;}
void vTaskDelete(TaskHandle_t h){assert(h&&task_state==eSuspended);task_deleted++;}
void vTaskSuspend(void*h){(void)h;task_state=eSuspended;}
void vTaskDelay(int t){(void)t;if(!task_block&&audio_stop&&task_state!=eSuspended)task_fn(NULL);}
int main(void){bad_reg=-1;int16_t pcm[DOOM_AUDIO_BLOCK];for(unsigned i=0;i<DOOM_AUDIO_BLOCK;i++)pcm[i]=123;
assert(!doom_audio_write(pcm,DOOM_AUDIO_BLOCK));
for(int fail=0;fail<20;fail++){seq=0;fail_at=fail;(void)doom_audio_begin();fail_at=-1;assert(doom_audio_end()==0);
#if CONFIG_BOARD_WS_C5_28
assert(doom_audio_silent_ready());
#else
assert(!doom_audio_silent_ready());
#endif
assert(!tx_live&&!tx_on&&!codec_live&&!ctrl_live&&!amp_on&&!audio_task&&!audio_queue);}
read_fail=1;assert(!doom_audio_begin());assert(!amp_on&&!tx_live&&!audio_task);read_fail=0;
for(int reg=0;reg<=0x37;reg++){if(reg==0||reg==1||reg==2||reg==6||reg==9||reg==0x0d||reg==0x12||reg==0x14||reg==0x31||reg==0x37){bad_reg=reg;assert(!doom_audio_begin());assert(!amp_on&&!tx_live&&!audio_task);}}bad_reg=-1;
queue_fail=1;assert(!doom_audio_begin());queue_fail=0;task_fail=1;assert(!doom_audio_begin());task_fail=0;
seq=0;fail_at=-1;assert(doom_audio_begin());assert(amp_on&&doom_audio_demand()==6&&started_logs>0);
unsigned writes=DM_GET(audio_writes);for(unsigned i=0;i<6;i++)assert(doom_audio_write(pcm,DOOM_AUDIO_BLOCK));assert(!doom_audio_demand());assert(DM_GET(audio_writes)==writes);
pcm[0]=0;assert(audio_step());assert(DM_GET(audio_nonzero)==DOOM_AUDIO_BLOCK);assert(doom_audio_demand()==1);
assert(!doom_audio_write(pcm,DOOM_AUDIO_BLOCK+1));
for(unsigned i=0;i<5;i++)assert(audio_step());assert(audio_step());assert(DM_GET(audio_starved)==1);
assert(doom_audio_write(pcm,DOOM_AUDIO_BLOCK));short_write=1;assert(!audio_step());short_write=0;assert(!doom_audio_demand());
assert(doom_audio_end()==0);assert(!tx_live&&!tx_on&&!codec_live&&!ctrl_live&&!amp_on&&!audio_task&&!audio_queue);
assert(doom_audio_begin());
/* Ack alone is not a join: timeout preserves live task, queue and handles. */
audio_done=true;task_block=1;assert(doom_audio_end()!=0);assert(audio_task&&audio_queue&&tx_live&&tx_on);task_block=0;audio_done=false;assert(doom_audio_end()==0);
assert(doom_audio_begin());assert(!doom_audio_silent_ready());fail_at=seq+3;assert(doom_audio_end()!=0);assert(tx_live&&!doom_audio_silent_ready());fail_at=-1;assert(doom_audio_end()==0);assert(!tx_live);
/* Every PA/codec/I2S/delete cleanup fault forbids silent admission until a verified retry. */
for(int fail=0;fail<7;fail++){assert(doom_audio_begin());fail_at=seq+fail;assert(doom_audio_end()!=0);assert(!doom_audio_silent_ready());fail_at=-1;assert(doom_audio_end()==0);assert(!tx_live&&!codec_live&&!ctrl_live&&!audio_task&&!audio_queue);}
amp_off_fail=1;assert(!doom_audio_begin());assert(!doom_audio_silent_ready());amp_off_fail=0;assert(doom_audio_end()==0);
#if CONFIG_BOARD_WS_C5_28
assert(doom_audio_silent_ready());
#endif
puts("PRODUCTION_AUDIO_BACKEND both board routes, copied queue/demand, silence starvation, fault/stop/join retention PASS (mock driver, not hardware)");return 0;}

"""
class Backend(unittest.TestCase):
 def test_both_production_backends(self):
  OUT.mkdir(parents=True,exist_ok=True);(OUT/'driver').mkdir(exist_ok=True)
  (OUT/'backend_stub.h').write_text(STUB)
  for p in [OUT/'driver/i2s_std.h',OUT/'esp_codec_dev_defaults.h',OUT/'esp_log.h']:p.write_text('#include "backend_stub.h"\n')
  (OUT/'freertos').mkdir(exist_ok=True)
  (OUT/'freertos/FreeRTOS.h').write_text('#pragma once\n#define pdTRUE 1\n#define pdPASS 1\n#define pdMS_TO_TICKS(x) (x)\n')
  (OUT/'freertos/task.h').write_text('#pragma once\ntypedef void *TaskHandle_t;\nenum{eRunning,eSuspended};\nint xTaskCreate(void(*)(void*),const char*,unsigned,void*,int,TaskHandle_t*);\nint eTaskGetState(TaskHandle_t);\nvoid vTaskDelete(TaskHandle_t);\nvoid vTaskDelay(int);\nvoid vTaskSuspend(void*);\n')
  (OUT/'freertos/queue.h').write_text('#pragma once\ntypedef struct mock_queue *QueueHandle_t;\nQueueHandle_t xQueueCreate(unsigned,size_t);\nunsigned uxQueueMessagesWaiting(QueueHandle_t);\nint xQueueSend(QueueHandle_t,const void*,int);\nint xQueueReceive(QueueHandle_t,void*,int);\nvoid vQueueDelete(QueueHandle_t);\n')
  (OUT/'harness.c').write_text(HARNESS)
  (OUT/'esp_timer.h').write_text('#include <stdint.h>\nstatic inline int64_t esp_timer_get_time(void){static int64_t us;return us+=2000;}\n')
  for board in ['28','35']:
   exe=OUT/('backend-'+board)
   cmd=['cc','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-g','-DCONFIG_BOARD_WS_C5_'+board+'=1','-I'+str(OUT),'-I'+str(COMP/'include'),'-I'+str(COMP),str(OUT/'harness.c'),'-o',str(exe)]
   r=subprocess.run(cmd,capture_output=True,text=True);(OUT/('compile-'+board+'.log')).write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   r=subprocess.run([str(exe)],capture_output=True,text=True);(OUT/('runtime-'+board+'.log')).write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
