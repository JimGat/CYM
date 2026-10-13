#include "debug_gate.h"
/* Routing verified against Waveshare vendor BSPs, not guessed from WS35.
 * ES8311 slave DAC, BCLK-derived clock, no microphone or second I2C bus.
 * Engine owns mixer/WAD; a finite copied-PCM worker owns writes. Stop joins it.
 */
#include "doom_audio.h"
#include "doom_metrics.h"
#include "esp_timer.h"
#include "driver/i2s_std.h"
#include "esp_codec_dev_defaults.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include <string.h>
static i2s_chan_handle_t tx;
static const audio_codec_ctrl_if_t *ctrl;
static const audio_codec_if_t *codec;
static bool enabled;
#define RATE 22050
static const float GAME_AUDIO_VOLUME_DB = -3.0f;
#define QUEUE_TARGET 6u
static QueueHandle_t audio_queue;
static TaskHandle_t audio_task;
static bool audio_stop,audio_done,audio_failed;
typedef struct {int16_t pcm[DOOM_AUDIO_BLOCK];} audio_block;
/* One bounded write, called only by the copied-buffer owner. Empty queue emits
 * measured silence rather than replaying stale sound or changing sample rate. */
static bool audio_step(void){
 audio_block b;
 if(xQueueReceive(audio_queue,&b,0)!=pdTRUE){memset(&b,0,sizeof(b));DM_ADD(audio_starved,1);}
 size_t written=0;uint32_t before=cym_debug_enabled()?(uint32_t)esp_timer_get_time():0;
 bool ok=i2s_channel_write(tx,b.pcm,sizeof(b.pcm),&written,50)==ESP_OK&&written==sizeof(b.pcm);
 uint32_t elapsed=before&&cym_debug_enabled()?(uint32_t)esp_timer_get_time()-before:0;
 DM_ADD(audio_writes,1);DM_ADD(audio_us,elapsed);
 if(elapsed>=1000)DM_ADD(audio_waits,1);
 if(ok){unsigned nonzero=0;bool measure=cym_debug_enabled();for(unsigned i=0;measure&&i<DOOM_AUDIO_BLOCK;i++)nonzero+=b.pcm[i]!=0;DM_ADD(audio_samples,DOOM_AUDIO_BLOCK);DM_ADD(audio_nonzero,nonzero);}
 else{ESP_LOGE("CYM_DOOM","AUDIO_WRITE_FAILED driver/short write; output stopped");DM_ADD(audio_faults,1);__atomic_store_n(&audio_failed,true,__ATOMIC_RELEASE);}
 return ok;
}
static void audio_worker(void *unused){(void)unused;
 while(!__atomic_load_n(&audio_stop,__ATOMIC_ACQUIRE)&&audio_step()){}
 __atomic_store_n(&audio_done,true,__ATOMIC_RELEASE);vTaskSuspend(NULL);
}
unsigned doom_audio_demand(void){
 if(!audio_queue||!enabled||__atomic_load_n(&audio_failed,__ATOMIC_ACQUIRE)||__atomic_load_n(&audio_stop,__ATOMIC_ACQUIRE))return 0;
 unsigned n=uxQueueMessagesWaiting(audio_queue);return n<QUEUE_TARGET?QUEUE_TARGET-n:0;
}
bool doom_audio_healthy(void){return enabled&&!__atomic_load_n(&audio_failed,__ATOMIC_ACQUIRE);}

#if CONFIG_BOARD_WS_C5_28
#define AUDIO_BOARD "WS28"
#define BCLK 24
#define LRCLK 25
#define DOUT 26
#elif CONFIG_BOARD_WS_C5_35
#define AUDIO_BOARD "WS35"
#define BCLK 23
#define LRCLK 10
#define DOUT 25
#else
#error Audio only belongs to the two qualified vendor profiles
#endif
/* DMA owns copied PCM only. On disable/delete failure retain handles so the
 * UI cannot claim joined cleanup and free engine state underneath ownership. */
int doom_audio_end(void){
 __atomic_store_n(&audio_stop,true,__ATOMIC_RELEASE);
 if(audio_task){
  for(unsigned waited=0;waited<100;waited++){
   if(__atomic_load_n(&audio_done,__ATOMIC_ACQUIRE)&&eTaskGetState(audio_task)==eSuspended)break;
   vTaskDelay(pdMS_TO_TICKS(10));
  }
  if(!__atomic_load_n(&audio_done,__ATOMIC_ACQUIRE)||eTaskGetState(audio_task)!=eSuspended)return -1;
  vTaskDelete(audio_task);audio_task=NULL;
 }
 if(audio_queue){vQueueDelete(audio_queue);audio_queue=NULL;}

 bool ok=cym_game_audio_amp(false);
 if(codec){
  if(codec->mute(codec,true)!=0)ok=false;
  if(codec->enable(codec,false)!=0)ok=false;
  uint8_t r12=0,r14=0,r31=0;unsigned mask=0;
  if(ctrl&&ctrl->read_reg){
   if(ctrl->read_reg(ctrl,0x12,1,&r12,1)==0)mask|=1;
   if(ctrl->read_reg(ctrl,0x14,1,&r14,1)==0)mask|=2;
   if(ctrl->read_reg(ctrl,0x31,1,&r31,1)==0)mask|=4;
  }
  bool off_verified=mask==7&&r12==2&&r14==0&&(r31&0x60)==0x60;
  if(!off_verified){ESP_LOGE("CYM_DOOM","AUDIO_STOP_FAILED codec powerdown readback");ok=false;}
  if(cym_debug_enabled())ESP_LOGI("CYM_DOOM","CODEC_STOP_DIAG board=%s read_mask=%x reg12=%02x reg14=%02x reg31=%02x muted_powerdown_verified=%d",AUDIO_BOARD,mask,r12,r14,r31,off_verified);
 }
 if(enabled){if(i2s_channel_disable(tx)!=ESP_OK)return -1;enabled=false;}
 if(tx){if(i2s_del_channel(tx)!=ESP_OK)return -1;tx=NULL;}
 if(codec){audio_codec_delete_codec_if(codec);codec=NULL;}
 if(ctrl){audio_codec_delete_ctrl_if(ctrl);ctrl=NULL;}
 ESP_LOGI("CYM_DOOM","AUDIO_STOPPED synchronous_owner DMA_released=%d",tx==NULL);
 return ok?0:-1;
}
bool doom_audio_begin(void){
 if(tx||codec||ctrl||audio_task||audio_queue)return false;
 audio_stop=audio_done=audio_failed=false;
 void *bus=cym_game_audio_bus();if(!bus||!cym_game_audio_amp(false))return false;
 i2s_chan_config_t ch=I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0,I2S_ROLE_MASTER);
 ch.dma_desc_num=4;ch.dma_frame_num=256;ch.auto_clear=true;
 if(i2s_new_channel(&ch,&tx,NULL)!=ESP_OK)goto fail;
 i2s_std_config_t cfg={.clk_cfg=I2S_STD_CLK_DEFAULT_CONFIG(RATE),
  .slot_cfg=I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,I2S_SLOT_MODE_MONO),
  .gpio_cfg={.mclk=I2S_GPIO_UNUSED,.bclk=BCLK,.ws=LRCLK,.dout=DOUT,.din=I2S_GPIO_UNUSED}};
 if(i2s_channel_init_std_mode(tx,&cfg)!=ESP_OK)goto fail;
 audio_codec_i2c_cfg_t ic={.port=0,.addr=ES8311_CODEC_DEFAULT_ADDR,.bus_handle=bus};
 ctrl=audio_codec_new_i2c_ctrl(&ic);if(!ctrl)goto fail;
 es8311_codec_cfg_t ec={.ctrl_if=ctrl,.codec_mode=ESP_CODEC_DEV_WORK_MODE_DAC,
  .pa_pin=-1,.master_mode=false,.use_mclk=false,.hw_gain={.pa_voltage=3.3,.codec_dac_voltage=3.3}};
 codec=es8311_codec_new(&ec);if(!codec)goto fail;
 esp_codec_dev_sample_info_t fs={.sample_rate=RATE,.channel=1,.bits_per_sample=16};
 if(codec->set_fs(codec,&fs)!=0||codec->mute(codec,true)!=0||codec->set_vol(codec,GAME_AUDIO_VOLUME_DB)!=0)goto fail;
 if(i2s_channel_enable(tx)!=ESP_OK)goto fail;enabled=true;
 if(codec->enable(codec,true)!=0||codec->mute(codec,false)!=0)goto fail;
 /* Read the actual DAC input09, not only ADC output0a. Driver can report
  * success after internal write failures; counters cannot prove audibility. */
 uint8_t regs[12]={0};const int addresses[]={0x00,0x01,0x02,0x06,0x09,0x0a,0x0d,0x12,0x14,0x31,0x32,0x37};unsigned read_mask=0;
 for(unsigned i=0;i<12;i++)if(ctrl->read_reg&&ctrl->read_reg(ctrl,addresses[i],1,&regs[i],1)==0)read_mask|=1u<<i;
 bool verified=read_mask==0xfff && !(regs[0]&0x40) && regs[1]==0xbf && regs[2]==0x18 && regs[3]==0x03 && (regs[4]&0x7f)==0x0c && regs[6]==0x01 && regs[7]==0 && regs[8]==0x1a && !(regs[9]&0x60) && regs[10]!=0 && regs[11]==0x08;
 if(cym_debug_enabled())ESP_LOGI("CYM_DOOM","CODEC_DIAG board=%s read_mask=%03x reg00=%02x reg01=%02x reg02=%02x reg06=%02x reg09=%02x reg0a=%02x reg0d=%02x reg12=%02x reg14=%02x reg31=%02x reg32=%02x reg37=%02x configuration_verified=%d audible=unconfirmed",AUDIO_BOARD,read_mask,regs[0],regs[1],regs[2],regs[3],regs[4],regs[5],regs[6],regs[7],regs[8],regs[9],regs[10],regs[11],verified);
 if(!verified){ESP_LOGE("CYM_DOOM","AUDIO_NOT_READY board=%s reason=codec_readback",AUDIO_BOARD);goto fail;}
 if(!cym_game_audio_amp(true)){ESP_LOGE("CYM_DOOM","AUDIO_NOT_READY board=%s reason=amp_pin_readback",AUDIO_BOARD);goto fail;}
 if(cym_debug_enabled())ESP_LOGI("CYM_DOOM","I2S_DIAG board=%s TX_ONLY no_mclk rate=%d bits=%d slot_bits=%d slot_mask=%d mono=%d bclk=%d lrclk=%d dout=%d pa_supply=3.3 dac_supply=3.3 configured_clocks_not_wire_measurement",AUDIO_BOARD,RATE,(int)cfg.slot_cfg.data_bit_width,(int)cfg.slot_cfg.slot_bit_width,(int)cfg.slot_cfg.slot_mask,(int)cfg.slot_cfg.slot_mode,BCLK,LRCLK,DOUT);
 audio_queue=xQueueCreate(8,sizeof(audio_block));if(!audio_queue)goto fail;
 if(xTaskCreate(audio_worker,"cym_pcm",4096,NULL,3,&audio_task)!=pdPASS){audio_task=NULL;goto fail;}
 ESP_LOGI("CYM_DOOM","AUDIO_STARTED configuration_verified audible=unconfirmed ES8311 rate=%d BCLK=%d LRCLK=%d DOUT=%d volume_db=%.0f SFX_ONLY",RATE,BCLK,LRCLK,DOUT,(double)GAME_AUDIO_VOLUME_DB);
 return true;
fail:
 ESP_LOGE("CYM_DOOM","AUDIO_INIT_FAILED ES8311/I2S/PA - exit and reboot");
 (void)doom_audio_end();return false;
}
bool doom_audio_write(const int16_t *pcm,size_t count){
 if(!doom_audio_healthy()||!audio_queue||!pcm||count!=DOOM_AUDIO_BLOCK||__atomic_load_n(&audio_stop,__ATOMIC_ACQUIRE))return false;
 audio_block b;memcpy(b.pcm,pcm,sizeof(b.pcm));
 bool ok=xQueueSend(audio_queue,&b,0)==pdTRUE;
 if(!ok)DM_ADD(audio_overruns,1);return ok;
}
