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
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
typedef void *i2s_chan_handle_t;
typedef struct {int dma_desc_num,dma_frame_num;bool auto_clear;} i2s_chan_config_t;
#define I2S_CHANNEL_DEFAULT_CONFIG(a,b) {0}
typedef struct {int rate;} mock_clk;
typedef struct {int bits,mode;} mock_slot;
#define I2S_STD_CLK_DEFAULT_CONFIG(r) {r}
#define I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(b,m) {b,m}
typedef struct {mock_clk clk_cfg;mock_slot slot_cfg;struct {int mclk,bclk,ws,dout,din;} gpio_cfg;} i2s_std_config_t;
typedef struct {int port,addr;void *bus_handle;} audio_codec_i2c_cfg_t;
typedef struct {int unused;} audio_codec_ctrl_if_t;
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
#include <assert.h>
#include <stdio.h>
static int seq,fail_at=-1,tx_live,tx_on,ctrl_live,codec_live,amp_on,short_write;
static audio_codec_ctrl_if_t ci;
static int op(void){return seq++==fail_at?-1:0;}
void *cym_game_audio_bus(void){return &ci;}
bool cym_game_audio_amp(bool on){if(op())return false;amp_on=on;return true;}
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
int i2s_channel_write(i2s_chan_handle_t t,const void *p,size_t n,size_t *out,unsigned timeout){assert(t&&tx_on&&p);assert(n<=2206&&timeout==50);*out=short_write?n-2:n;return op();}
const audio_codec_ctrl_if_t *audio_codec_new_i2c_ctrl(audio_codec_i2c_cfg_t*c){assert(c->port==0&&c->addr==0x30&&c->bus_handle==&ci);if(op())return NULL;ctrl_live=1;return &ci;}
static int mute(const audio_codec_if_t*c,bool v){(void)c;(void)v;return op();}
static int enable(const audio_codec_if_t*c,bool v){(void)c;(void)v;return op();}
static int fs(const audio_codec_if_t*c,esp_codec_dev_sample_info_t*f){(void)c;assert(f->sample_rate==22050&&f->bits_per_sample==16&&f->channel==1);return op();}
static int vol(const audio_codec_if_t*c,float db){(void)c;assert(db==-30.0f);return op();}
static const audio_codec_if_t co={mute,enable,fs,vol};
const audio_codec_if_t *es8311_codec_new(es8311_codec_cfg_t*c){assert(c->ctrl_if==&ci&&!c->master_mode&&!c->use_mclk&&c->pa_pin==-1&&c->codec_mode==1);if(op())return NULL;codec_live=1;return &co;}
int audio_codec_delete_codec_if(const audio_codec_if_t*c){assert(c==&co);codec_live=0;return 0;}
int audio_codec_delete_ctrl_if(const audio_codec_ctrl_if_t*c){assert(c==&ci);ctrl_live=0;return 0;}
int main(void){int16_t pcm[1103]={0};assert(!doom_audio_write(pcm,1));
for(int fail=0;fail<20;fail++){seq=0;fail_at=fail;(void)doom_audio_begin();fail_at=-1;assert(doom_audio_end()==0);assert(!tx_live&&!tx_on&&!codec_live&&!ctrl_live&&!amp_on);}
seq=0;fail_at=-1;assert(doom_audio_begin());assert(amp_on);assert(doom_audio_write(pcm,1103));assert(!doom_audio_write(pcm,1104));short_write=1;assert(!doom_audio_write(pcm,2));short_write=0;
fail_at=seq+3;assert(doom_audio_end()!=0);assert(tx_live);fail_at=-1;assert(doom_audio_end()==0);assert(!tx_live&&!tx_on&&!codec_live&&!ctrl_live&&!amp_on);
puts("PRODUCTION_AUDIO_BACKEND routing, DMA bounds, init/stop failures, retry retention PASS (mock driver, not hardware)");return 0;}
"""
class Backend(unittest.TestCase):
 def test_both_production_backends(self):
  OUT.mkdir(parents=True,exist_ok=True);(OUT/'driver').mkdir(exist_ok=True)
  (OUT/'backend_stub.h').write_text(STUB)
  for p in [OUT/'driver/i2s_std.h',OUT/'esp_codec_dev_defaults.h',OUT/'esp_log.h']:p.write_text('#include "backend_stub.h"\n')
  (OUT/'harness.c').write_text(HARNESS)
  for board in ['28','35']:
   exe=OUT/('backend-'+board)
   cmd=['cc','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-g','-DCONFIG_BOARD_WS_C5_'+board+'=1','-I'+str(OUT),'-I'+str(COMP/'include'),str(OUT/'harness.c'),str(COMP/'doom_audio.c'),'-o',str(exe)]
   r=subprocess.run(cmd,capture_output=True,text=True);(OUT/('compile-'+board+'.log')).write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   r=subprocess.run([str(exe)],capture_output=True,text=True);(OUT/('runtime-'+board+'.log')).write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
