/* WS35 adapter: pinned vendor04e6134 wiring, installed ES8311 ADC API.
 * I2S0 duplex reservation precedes ALL codec access. Shared I2C bus is borrowed.
 * No amplifier GPIO operations: shared board power stays untouched. DAC digital
 * mute + powered-down DAC, owned zero TX, analog differential mic/bias enabled.
 * The vendor set_fs/mute can lose error returns: latch every control transaction
 * and verify actual registers before reporting a configured input.
 */
#include "audio_rta_board.h"
#include "driver/i2s_std.h"
#include "driver/i2c_master.h"
#include "esp_codec_dev_defaults.h"
#include <string.h>
struct audio_rta_board {
 audio_codec_ctrl_if_t ctrl; /* first member for codec callback cast */
 i2c_master_dev_handle_t dev;
 i2s_chan_handle_t tx,rx;
 const audio_codec_if_t *codec;
 bool tx_on,rx_on;
 int io_error;
 uint32_t overruns;
};
static const int16_t silence[512]={0}; /* flash, not a retained mutable PCM buffer */
size_t audio_rta_board_bytes(void){return sizeof(audio_rta_board_t);}
static bool ctrl_is_open(const audio_codec_ctrl_if_t*c){return ((const audio_rta_board_t*)c)->dev!=NULL;}
static int ctrl_read(const audio_codec_ctrl_if_t*c,int reg,int rl,void*data,int len){
 audio_rta_board_t*b=(void*)c;
 if(b->io_error)return b->io_error;
 uint8_t a=reg;
 int e=rl==1?i2c_master_transmit_receive(b->dev,&a,1,data,len,20):ESP_ERR_INVALID_ARG;
 if(e)b->io_error=e;
 return e;
}
static int ctrl_write(const audio_codec_ctrl_if_t*c,int reg,int rl,void*data,int len){
 audio_rta_board_t*b=(void*)c;
 if(b->io_error)return b->io_error;
 if(rl!=1||len!=1){b->io_error=ESP_ERR_INVALID_ARG;return b->io_error;}
 uint8_t a[2]={(uint8_t)reg,*(uint8_t*)data};
 int e=i2c_master_transmit(b->dev,a,2,20);if(e)b->io_error=e;
 return e;
}
static esp_err_t reg_set(audio_rta_board_t*b,int r,uint8_t v){return ctrl_write(&b->ctrl,r,1,&v,1);}
static bool reg_is(audio_rta_board_t*b,int r,uint8_t mask,uint8_t v){
 uint8_t x=0;return !ctrl_read(&b->ctrl,r,1,&x,1)&&(x&mask)==v;
}
static bool rx_overflow(i2s_chan_handle_t h,i2s_event_data_t*event,void*arg){
 (void)h;(void)event;audio_rta_board_t*b=arg;__atomic_fetch_add(&b->overruns,1,__ATOMIC_RELAXED);return false;
}
esp_err_t audio_rta_board_gain(audio_rta_board_t*b,int gain){
 if(!b->codec||gain<0||gain>42||gain%6)return ESP_ERR_INVALID_ARG;
 b->io_error=0;
 if(b->codec->set_mic_gain(b->codec,(float)gain)||b->io_error||!reg_is(b,0x16,0xff,gain/6))return ESP_FAIL;
 return ESP_OK;
}
esp_err_t audio_rta_board_open(audio_rta_board_t*b,void*bus,int gain){
 if(!b||!bus)return ESP_ERR_INVALID_ARG;
 memset(b,0,sizeof(*b));
 i2s_chan_config_t ch=I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0,I2S_ROLE_MASTER);
 ch.dma_desc_num=4;ch.dma_frame_num=256;ch.auto_clear=true;
 /* Request both channels atomically, never select another owner's live channel. */
 esp_err_t e=i2s_new_channel(&ch,&b->tx,&b->rx);if(e)return e;
 i2s_std_config_t cfg={.clk_cfg=I2S_STD_CLK_DEFAULT_CONFIG(48000),
 .slot_cfg=I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,I2S_SLOT_MODE_MONO),
 .gpio_cfg={.mclk=I2S_GPIO_UNUSED,.bclk=23,.ws=10,.dout=25,.din=24}};
 if((e=i2s_channel_init_std_mode(b->tx,&cfg)))return e;
 /* C5 HWv2 maps MONO+BOTH to one TX DMA slot, but RX enables both
  * slots. Select the ES8311 left ADC slot explicitly: one sample/LRCLK,
  * matching the mono DMA allocation and DSP's 48 kHz timebase. */
 cfg.slot_cfg.slot_mask=I2S_STD_SLOT_LEFT;
 if((e=i2s_channel_init_std_mode(b->rx,&cfg)))return e;
 i2s_event_callbacks_t cb={.on_recv_q_ovf=rx_overflow};
 if((e=i2s_channel_register_event_callback(b->rx,&cb,b)))return e;
 i2c_device_config_t dc={.dev_addr_length=I2C_ADDR_BIT_LEN_7,.device_address=ES8311_CODEC_DEFAULT_ADDR>>1,.scl_speed_hz=100000};
 if((e=i2c_master_bus_add_device(bus,&dc,&b->dev)))return e;
 b->ctrl.read_reg=ctrl_read;b->ctrl.write_reg=ctrl_write;b->ctrl.is_open=ctrl_is_open;
 es8311_codec_cfg_t ec={.ctrl_if=&b->ctrl,.codec_mode=ESP_CODEC_DEV_WORK_MODE_ADC,
 .pa_pin=-1,.master_mode=false,.use_mclk=false,.digital_mic=false,.no_dac_ref=true};
 b->codec=es8311_codec_new(&ec);if(!b->codec||b->io_error)return ESP_FAIL;
 esp_codec_dev_sample_info_t fs={.sample_rate=48000,.channel=1,.bits_per_sample=16};
 if(b->codec->set_fs(b->codec,&fs)||b->io_error)return ESP_FAIL;
 if((e=i2s_channel_enable(b->tx)))return e;
 b->tx_on=true;
 size_t written=0;if((e=i2s_channel_write(b->tx,silence,sizeof(silence),&written,20))||written!=sizeof(silence))return ESP_FAIL;
 if((e=i2s_channel_enable(b->rx)))return e;
 b->rx_on=true;
 if(b->codec->enable(b->codec,true)||b->io_error)return ESP_FAIL;
 if(b->codec->mute(b->codec,true)||b->io_error)return ESP_FAIL;
 if(reg_set(b,0x12,0x02)||audio_rta_board_gain(b,gain))return ESP_FAIL;
 if(!reg_is(b,0x00,0x40,0)||!reg_is(b,0x01,0xff,0xbf)||!reg_is(b,0x02,0xff,0x18)||
 !reg_is(b,0x06,0x1f,3)||!reg_is(b,0x07,0x3f,0)||!reg_is(b,0x08,0xff,0xff)||
 !reg_is(b,0x0a,0x7f,0x0c)||!reg_is(b,0x0d,0xff,1)||!reg_is(b,0x12,0xff,2)||
 !reg_is(b,0x14,0xff,0x1a)||!reg_is(b,0x17,0xff,0xbf)||!reg_is(b,0x31,0x60,0x60)||!reg_is(b,0x44,0xff,8))return ESP_FAIL;
 return ESP_OK;
}
esp_err_t audio_rta_board_read(audio_rta_board_t*b,int16_t*pcm,size_t cap,size_t*count,bool*discontinuity){
 *discontinuity=false;*count=0;size_t n=cap>512?512:cap,bytes=0,written=0;
 esp_err_t e=i2s_channel_write(b->tx,silence,n*2,&written,20);
 if(e)return e;
 if(written!=n*2)return ESP_FAIL;
 e=i2s_channel_read(b->rx,pcm,n*2,&bytes,20);
 if(bytes%2)return ESP_FAIL;
 *count=bytes/2;
 /* Preserve the real SDK error even when a queue overflow occurred too. */
 *discontinuity=__atomic_exchange_n(&b->overruns,0,__ATOMIC_RELAXED)!=0;
 return e;
}
/* Only the detached session worker calls close. Keep any failed handle live and
 * retry visibly; never release callback/context storage while DMA may use it. */
esp_err_t audio_rta_board_close(audio_rta_board_t*b){
 if(b->codec){b->io_error=0;b->codec->mute(b->codec,true);b->codec->enable(b->codec,false);
  /* Digital DMA stops even if physical control is temporarily unavailable.
   * Preserve the codec object for bounded detached retry after DMA shutdown. */
 }
 if(b->rx_on){if(i2s_channel_disable(b->rx))return ESP_FAIL;b->rx_on=false;}
 if(b->tx_on){if(i2s_channel_disable(b->tx))return ESP_FAIL;b->tx_on=false;}
 if(b->rx){if(i2s_del_channel(b->rx))return ESP_FAIL;b->rx=NULL;}
 if(b->tx){if(i2s_del_channel(b->tx))return ESP_FAIL;b->tx=NULL;}
 if(b->dev){
  /* A partial enable may leave the codec API's enabled flag false. Explicit
   * owned ADC/bias/DAC/clock power-down matches vendor suspend, without a
   * device/bus reset. Readback guards against codec APIs losing write errors. */
  b->io_error=0;
  reg_set(b,0x31,0x60);reg_set(b,0x12,0x02);reg_set(b,0x14,0x00);
  reg_set(b,0x0e,0xff);reg_set(b,0x0d,0xfc);reg_set(b,0x01,0x00);
  if(b->io_error||!reg_is(b,0x14,0xff,0)||!reg_is(b,0x0d,0xff,0xfc))return ESP_FAIL;
 }
 if(b->codec){
  if(b->io_error)return ESP_FAIL;
  audio_codec_delete_codec_if(b->codec);b->codec=NULL;
 }
 if(b->dev){if(i2c_master_bus_rm_device(b->dev))return ESP_FAIL;b->dev=NULL;}
 return ESP_OK;
}
