#include "diag_core.h"
#include "esp_codec_dev_defaults.h"
#include "driver/i2c_master.h"
#include "driver/i2s_std.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdio.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>

/* All operations run synchronously in app_main. Bus/device handles persist;
 * only stopped DMA channels are deleted. No worker owns a live PCM buffer. */
static i2c_master_bus_handle_t bus;
static i2c_master_dev_handle_t ch32, esdev;
static i2s_chan_handle_t tx;
static const audio_codec_if_t *codec;
static bool enabled, locked;
static unsigned ctrl_faults;
static uint8_t requested=0x03;
static int status(const char *op, int rc) {
 printf("op=%s rc=%d elapsed_us=%" PRId64 "\n",op,rc,esp_timer_get_time());
 return rc;
}
/* A bounded raw I2C transport implements the installed codec interface.
 * Register sequences belong exclusively to the installed ES8311 driver.
 * Latch EVERY transport fault because upstream set_fs/close can hide errors. */
static bool ctrl_open(const audio_codec_ctrl_if_t *c) { (void)c;return esdev!=NULL; }
static int ctrl_read(const audio_codec_ctrl_if_t *c,int reg,int rl,void *data,int dl) {
 (void)c; int rc=ESP_ERR_INVALID_ARG;uint8_t r=(uint8_t)reg;
 if(rl==1&&dl==1) rc=i2c_master_transmit_receive(esdev,&r,1,data,1,100);
 if(rc) ctrl_faults++;
 printf("codec_i2c read reg=%02x rc=%d raw=%02x\n",reg,rc,rc?0:*(uint8_t*)data);
 return rc;
}
static int ctrl_write(const audio_codec_ctrl_if_t *c,int reg,int rl,void *data,int dl) {
 (void)c;int rc=ESP_ERR_INVALID_ARG;uint8_t b[2]={(uint8_t)reg,0};
 if(rl==1&&dl==1){b[1]=*(uint8_t*)data;rc=i2c_master_transmit(esdev,b,2,100);}
 if(rc) ctrl_faults++;
 printf("codec_i2c write reg=%02x requested=%02x rc=%d\n",reg,b[1],rc);
 return rc;
}
static const audio_codec_ctrl_if_t ctrl={.is_open=ctrl_open,.read_reg=ctrl_read,.write_reg=ctrl_write};
static int amp(bool on) {
 uint8_t b[2]={0x03,on?0x0b:0x03};requested=b[1];
 return status(on?"CH32_requested_ON_0b":"CH32_requested_OFF_03",ch32?i2c_master_transmit(ch32,b,2,100):ESP_ERR_INVALID_STATE);
}
static int samples(void) {
 int result=0;int64_t start=esp_timer_get_time();
 for(unsigned i=0;i<6;i++) {
  uint8_t reg=0x04,raw=0;int64_t t=esp_timer_get_time();
  int rc=i2c_master_transmit_receive(ch32,&reg,1,&raw,1,100);
  printf("CH32_input sample=%u rc=%d raw=%02x requested_output=%02x requested_direction=0b output_mode=1 amp_input_matches_request=%d electrical_verified=0 elapsed_us=%" PRId64 " read_us=%" PRId64 "\n",i,rc,raw,requested,rc==0&&((raw^requested)&8)==0,esp_timer_get_time()-start,esp_timer_get_time()-t);
  if(rc) result=rc;
  if(i<5) vTaskDelay(pdMS_TO_TICKS(20));
 }
 return result; /* mismatch alone is evidence, never a success claim or gate */
}
static int init_audio(void) {
 i2s_chan_config_t ch=I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0,I2S_ROLE_MASTER);
 ch.dma_desc_num=4;ch.dma_frame_num=256;ch.auto_clear=true;
 int rc=status("i2s_new",i2s_new_channel(&ch,&tx,NULL));if(rc)return rc;
 i2s_std_config_t cfg={.clk_cfg=I2S_STD_CLK_DEFAULT_CONFIG(DIAG_RATE),
  .slot_cfg=I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,I2S_SLOT_MODE_MONO),
  .gpio_cfg={.mclk=I2S_GPIO_UNUSED,.bclk=24,.ws=25,.dout=26,.din=I2S_GPIO_UNUSED}};
 rc=status("i2s_init",i2s_channel_init_std_mode(tx,&cfg));if(rc)return rc;
 es8311_codec_cfg_t ec={.ctrl_if=&ctrl,.codec_mode=ESP_CODEC_DEV_WORK_MODE_DAC,.pa_pin=-1,
  .master_mode=false,.use_mclk=false,.hw_gain={.pa_voltage=3.3,.codec_dac_voltage=3.3}};
 codec=es8311_codec_new(&ec);status("codec_new",codec?0:-1);if(!codec||ctrl_faults)return -1;
 esp_codec_dev_sample_info_t fs={.sample_rate=DIAG_RATE,.channel=1,.bits_per_sample=16};
 rc=status("codec_set_fs",codec->set_fs(codec,&fs));if(rc||ctrl_faults)return -1;
 rc=status("codec_mute",codec->mute(codec,true));if(rc||ctrl_faults)return -1;
 rc=status("codec_volume_minus18dB",codec->set_vol(codec,-18.0f));if(rc||ctrl_faults)return -1;
 rc=status("i2s_enable",i2s_channel_enable(tx));if(rc)return rc;enabled=true;
 rc=status("codec_enable",codec->enable(codec,true));if(rc||ctrl_faults)return -1;
 rc=status("codec_unmute",codec->mute(codec,false));if(rc||ctrl_faults)return -1;
 const uint8_t regs[]={0x00,0x01,0x02,0x06,0x09,0x0a,0x0d,0x12,0x14,0x31,0x32,0x37};
 for(unsigned i=0;i<sizeof(regs);i++){uint8_t raw=0;rc=ctrl_read(&ctrl,regs[i],1,&raw,1);if(rc)return rc;}
 printf("I2S configured rate=22050 bits=16 mono Philips BCLK24 LRCLK25 DOUT26 no_MCLK slave_DAC BCLK_clock volume_db=-18 not_wire_measurement audible=unconfirmed\n");
 return 0;
}
static int tone(void) {
 int16_t pcm[DIAG_BLOCK];unsigned nonzero=0,peak=0,writes=0;size_t bytes=0;
 int64_t start=esp_timer_get_time();int result=0;
 for(unsigned pos=0;pos<DIAG_SAMPLES;pos+=DIAG_BLOCK) {
  unsigned n=DIAG_SAMPLES-pos;if(n>DIAG_BLOCK)n=DIAG_BLOCK;
  diag_pcm(pcm,n,pos);
  for(unsigned i=0;i<n;i++){unsigned a=(unsigned)abs(pcm[i]);nonzero+=a!=0;if(a>peak)peak=a;}
  size_t written=0;int64_t t=esp_timer_get_time();
  int rc=i2s_channel_write(tx,pcm,n*sizeof(*pcm),&written,100);
  writes++;bytes+=written;
  printf("PCM write=%u rc=%d requested_bytes=%u actual_bytes=%u elapsed_us=%" PRId64 " first_raw=%d last_raw=%d\n",writes,rc,(unsigned)(n*sizeof(*pcm)),(unsigned)written,esp_timer_get_time()-t,pcm[0],pcm[n-1]);
  if(rc||written!=n*sizeof(*pcm)){result=-1;break;}
 }
 if(result==0) vTaskDelay(pdMS_TO_TICKS(60)); /* bounded drain: 4*256/22050 < 47ms */
 printf("PCM summary requested_samples=%u nonzero=%u peak=%u written_bytes=%u writes=%u elapsed_us=%" PRId64 " audible=unconfirmed rc=%d\n",DIAG_SAMPLES,nonzero,peak,(unsigned)bytes,writes,esp_timer_get_time()-start,result);
 return result;
}
static int cleanup(void) {
 int result=0;unsigned before=ctrl_faults;
 if(codec) {
  if(status("cleanup_codec_mute",codec->mute(codec,true)))result=-1;
  if(status("cleanup_codec_disable",codec->enable(codec,false)))result=-1;
  if(status("cleanup_codec_delete",audio_codec_delete_codec_if(codec)))result=-1;
  codec=NULL;
 }
 if(ctrl_faults!=before)result=-1;
 if(enabled) {
  int rc=status("cleanup_i2s_disable",i2s_channel_disable(tx));
  if(rc){locked=true;return -1;}enabled=false;
 }
 if(tx) {
  int rc=status("cleanup_i2s_delete",i2s_del_channel(tx));
  if(rc){locked=true;return -1;}tx=NULL;
 }
 if(result)locked=true;
 return result;
}
static int step(void *ctx,enum diag_op op) {
 (void)ctx;
 switch(op){
  case DIAG_OFF:{int rc=amp(false);if(rc)locked=true;return rc;}
  case DIAG_DIRECTION:{uint8_t b[]={0x02,0x0b};return status("CH32_requested_direction_0b",i2c_master_transmit(ch32,b,2,100));}
  case DIAG_SAMPLE:return samples();
  case DIAG_ON:return amp(true);
  case DIAG_INIT:return init_audio();
  case DIAG_TONE:return tone();
  case DIAG_CLEANUP:return cleanup();
 }
 return -1;
}
static void run(void) {
 if(locked){printf("repeat_locked cleanup_or_off_failure reboot_required audible=unconfirmed\n");return;}
 ctrl_faults=0;int64_t start=esp_timer_get_time();
 printf("WS28AudioDiag v0.1.1 BEGIN masks=requests_not_readback audible=unconfirmed\n");
 int rc=diag_run(step,NULL);
 printf("END rc=%d ctrl_faults=%u cleanup_locked=%d elapsed_us=%" PRId64 " audible=unconfirmed owner_listening_required\n",rc,ctrl_faults,locked,esp_timer_get_time()-start);
}
void app_main(void) {
 setvbuf(stdout,NULL,_IOLBF,0);
 printf("WS28AudioDiag v0.1.1 primary_USB_Serial_JTAG grace=4000ms audible=unconfirmed\n");
 vTaskDelay(pdMS_TO_TICKS(4000));
 i2c_master_bus_config_t bc={.i2c_port=0,.sda_io_num=0,.scl_io_num=1,.clk_source=I2C_CLK_SRC_DEFAULT,.glitch_ignore_cnt=7,.flags.enable_internal_pullup=true};
 int rc=status("i2c_bus_new",i2c_new_master_bus(&bc,&bus));if(rc)return;
 i2c_device_config_t dc={.dev_addr_length=I2C_ADDR_BIT_LEN_7,.device_address=0x24,.scl_speed_hz=100000};
 rc=status("CH32_add",i2c_master_bus_add_device(bus,&dc,&ch32));if(rc)return;
 /* Ensure off immediately, including codec-device setup failure. */
 if(amp(false)!=0){locked=true;(void)amp(false);return;}
 dc.device_address=ES8311_CODEC_DEFAULT_ADDR>>1;
 rc=status("ES8311_add",i2c_master_bus_add_device(bus,&dc,&esdev));
 if(rc){status("setup_failure_off",amp(false));return;}
 gpio_config_t boot={.pin_bit_mask=1ULL<<28,.mode=GPIO_MODE_INPUT,.pull_up_en=GPIO_PULLUP_ENABLE};
 rc=status("BOOT_gpio28",gpio_config(&boot));if(rc){status("setup_failure_off",amp(false));return;}
 run();
 /* Debounced press+release, 30..1500ms; no repeated sound while held. */
 bool down=false;int64_t pressed=0;
 for(;;){
  int level=gpio_get_level(28);int64_t now=esp_timer_get_time();
  if(!level&&!down){down=true;pressed=now;}
  if(level&&down){down=false;int64_t duration=now-pressed;if(duration>=30000&&duration<=1500000)run();}
  vTaskDelay(pdMS_TO_TICKS(10));
 }
}
