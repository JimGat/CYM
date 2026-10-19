#!/usr/bin/env python3
"""Production adapter + installed ES8311 driver; fault-injected synthetic I2C/I2S."""
from pathlib import Path
import subprocess,os
R=Path(__file__).resolve().parents[1];M=R/'ESP32C5/managed_components/espressif__esp_codec_dev';D=Path(os.environ['CYM_TEST_OUT'])/'rta-board';D.mkdir(parents=True,exist_ok=True)
(D/'driver').mkdir(exist_ok=True)
(D/'esp_err.h').write_text('#pragma once\ntypedef int esp_err_t;\n#define ESP_OK 0\n#define ESP_FAIL -1\n#define ESP_ERR_INVALID_ARG 2\n#define ESP_ERR_INVALID_STATE 3\n#define ESP_ERR_TIMEOUT 4\n#define ESP_ERR_NOT_FOUND -5\n#define ESP_ERR_NOT_SUPPORTED -6\n')
(D/'esp_log.h').write_text('#define ESP_LOGE(...) ((void)0)\n#define ESP_LOGD(...) ((void)0)\n#define ESP_LOGI(...) ((void)0)\n')
(D/'freertos').mkdir(exist_ok=True)
(D/'freertos/FreeRTOS.h').write_text('#define pdMS_TO_TICKS(n) (n)\n')
(D/'freertos/task.h').write_text('static void vTaskDelay(unsigned n){(void)n;}\n')
(D/'sdkconfig.h').write_text('#define CONFIG_CODEC_ES8311_SUPPORT 1\n')
(D/'driver/i2s_std.h').write_text(r"""
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "esp_err.h"
typedef struct channel{int on;}*i2s_chan_handle_t;
typedef struct{int dummy;}i2s_event_data_t;
typedef struct{bool(*on_recv_q_ovf)(i2s_chan_handle_t,i2s_event_data_t*,void*);}i2s_event_callbacks_t;
typedef struct{int dma_desc_num,dma_frame_num;bool auto_clear;}i2s_chan_config_t;
typedef struct{struct{int sample_rate_hz;}clk_cfg;struct{int bits,mode,slot_mask;}slot_cfg;struct{int mclk,bclk,ws,dout,din;}gpio_cfg;}i2s_std_config_t;
#define I2S_CHANNEL_DEFAULT_CONFIG(a,b) {0}
#define I2S_NUM_0 0
#define I2S_ROLE_MASTER 1
#define I2S_STD_CLK_DEFAULT_CONFIG(n) {n}
#define I2S_STD_SLOT_LEFT 1
#define I2S_STD_SLOT_BOTH 3
#define I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(a,b) {a,b,I2S_STD_SLOT_BOTH}
#define I2S_DATA_BIT_WIDTH_16BIT 16
#define I2S_SLOT_MODE_MONO 1
#define I2S_GPIO_UNUSED -1
esp_err_t i2s_new_channel(const i2s_chan_config_t*,i2s_chan_handle_t*,i2s_chan_handle_t*);
esp_err_t i2s_channel_init_std_mode(i2s_chan_handle_t,const i2s_std_config_t*);
esp_err_t i2s_channel_register_event_callback(i2s_chan_handle_t,const i2s_event_callbacks_t*,void*);
esp_err_t i2s_channel_enable(i2s_chan_handle_t);
esp_err_t i2s_channel_disable(i2s_chan_handle_t);
esp_err_t i2s_del_channel(i2s_chan_handle_t);
esp_err_t i2s_channel_write(i2s_chan_handle_t,const void*,size_t,size_t*,unsigned);
esp_err_t i2s_channel_read(i2s_chan_handle_t,void*,size_t,size_t*,unsigned);
""")
(D/'driver/i2c_master.h').write_text(r"""
#pragma once
#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>
typedef void*i2c_master_dev_handle_t;
typedef struct{int dev_addr_length,device_address,scl_speed_hz;}i2c_device_config_t;
#define I2C_ADDR_BIT_LEN_7 7
esp_err_t i2c_master_bus_add_device(void*,const i2c_device_config_t*,i2c_master_dev_handle_t*);
esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t);
esp_err_t i2c_master_transmit(i2c_master_dev_handle_t,const uint8_t*,size_t,int);
esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t,const uint8_t*,size_t,void*,size_t,int);
""")
(D/'host.c').write_text(r"""
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "audio_rta_board.c"
static int calls,fail_at,live_channels,live_dev,io_calls,partial,odd,read_error,fail_codec_alloc;
static i2s_chan_handle_t tx_handle;
static uint8_t regs[256];static i2s_event_callbacks_t events;static void*event_arg;
static int gate(void){return ++calls==fail_at?ESP_FAIL:0;}
void*__real_calloc(size_t,size_t);
void*__wrap_calloc(size_t n,size_t z){if(fail_codec_alloc&&live_dev){fail_codec_alloc=0;return NULL;}return __real_calloc(n,z);}
int audio_codec_delete_codec_if(const audio_codec_if_t*c){int e=c->close(c);free((void*)c);return e;}
esp_err_t i2s_new_channel(const i2s_chan_config_t*c,i2s_chan_handle_t*tx,i2s_chan_handle_t*rx){assert(c->dma_desc_num==4&&c->dma_frame_num==256&&c->auto_clear);if(gate())return ESP_FAIL;*tx=calloc(1,sizeof(**tx));*rx=calloc(1,sizeof(**rx));assert(*tx&&*rx);tx_handle=*tx;live_channels+=2;return 0;}
esp_err_t i2s_channel_init_std_mode(i2s_chan_handle_t h,const i2s_std_config_t*c){assert(h&&c->clk_cfg.sample_rate_hz==48000&&c->slot_cfg.bits==16&&c->slot_cfg.mode==1&&c->slot_cfg.slot_mask==(h==tx_handle?I2S_STD_SLOT_BOTH:I2S_STD_SLOT_LEFT)&&c->gpio_cfg.bclk==23&&c->gpio_cfg.ws==10&&c->gpio_cfg.dout==25&&c->gpio_cfg.din==24&&c->gpio_cfg.mclk==-1);return gate();}
esp_err_t i2s_channel_register_event_callback(i2s_chan_handle_t h,const i2s_event_callbacks_t*c,void*p){assert(h);if(gate())return ESP_FAIL;events=*c;event_arg=p;return 0;}
esp_err_t i2s_channel_enable(i2s_chan_handle_t h){if(gate())return ESP_FAIL;h->on=1;return 0;}
esp_err_t i2s_channel_disable(i2s_chan_handle_t h){if(gate())return ESP_FAIL;h->on=0;return 0;}
esp_err_t i2s_del_channel(i2s_chan_handle_t h){assert(!h->on);if(gate())return ESP_FAIL;free(h);live_channels--;return 0;}
esp_err_t i2s_channel_write(i2s_chan_handle_t h,const void*p,size_t n,size_t*out,unsigned timeout){assert(h->on&&timeout==20&&n<=1024);for(size_t i=0;i<n;i++)assert(!((const uint8_t*)p)[i]);if(gate())return ESP_FAIL;*out=n;return 0;}
esp_err_t i2s_channel_read(i2s_chan_handle_t h,void*p,size_t n,size_t*out,unsigned timeout){assert(h->on&&timeout==20);if(gate())return ESP_FAIL;*out=odd?3:partial?126:n;memset(p,0,*out);return read_error;}
esp_err_t i2c_master_bus_add_device(void*b,const i2c_device_config_t*c,i2c_master_dev_handle_t*out){assert(b==(void*)1&&c->device_address==0x18&&c->scl_speed_hz==100000);if(gate())return ESP_FAIL;*out=(void*)2;live_dev++;return 0;}
esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t b){assert(b==(void*)2);if(gate())return ESP_FAIL;live_dev--;return 0;}
esp_err_t i2c_master_transmit(i2c_master_dev_handle_t b,const uint8_t*p,size_t n,int timeout){assert(b==(void*)2&&n==2&&timeout==20);io_calls++;if(gate())return ESP_FAIL;regs[p[0]]=p[1];return 0;}
esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t b,const uint8_t*p,size_t n,void*out,size_t z,int timeout){assert(b==(void*)2&&n==1&&z==1&&timeout==20);io_calls++;if(gate())return ESP_FAIL;*(uint8_t*)out=regs[p[0]];return 0;}
static void cleanup(audio_rta_board_t*b){fail_at=0;for(int i=0;i<3;i++){if(!audio_rta_board_close(b))break;}assert(!live_channels&&!live_dev);assert(!audio_rta_board_close(b));}
int main(void){audio_rta_board_t b;memset(&b,0,sizeof(b));assert(!audio_rta_board_open(&b,(void*)1,0));int stages=calls;assert(regs[0x02]==0x18&&regs[0x14]==0x1a&&regs[0x16]==0&&regs[0x31]==0x60);cleanup(&b);assert(regs[0x14]==0&&regs[0x0d]==0xfc);
 for(int k=1;k<=stages;k++){memset(regs,0,sizeof(regs));memset(&b,0,sizeof(b));calls=io_calls=0;fail_at=k;assert(audio_rta_board_open(&b,(void*)1,0)!=0);if(k==1)assert(!io_calls);cleanup(&b);}
 calls=0;fail_at=0;fail_codec_alloc=1;memset(&b,0,sizeof(b));assert(audio_rta_board_open(&b,(void*)1,0));cleanup(&b);
 calls=0;fail_at=0;memset(&b,0,sizeof(b));assert(!audio_rta_board_open(&b,(void*)1,0));for(int gain=0;gain<=42;gain+=6){assert(!audio_rta_board_gain(&b,gain));assert(regs[0x16]==gain/6);}assert(audio_rta_board_gain(&b,7));
 int16_t pcm[512];size_t n;bool discontinuity;partial=1;assert(!audio_rta_board_read(&b,pcm,512,&n,&discontinuity)&&n==63);odd=1;assert(audio_rta_board_read(&b,pcm,512,&n,&discontinuity));odd=partial=0;events.on_recv_q_ovf(b.rx,NULL,event_arg);assert(audio_rta_board_read(&b,pcm,512,&n,&discontinuity)==ESP_OK&&discontinuity);read_error=ESP_ERR_INVALID_STATE;assert(audio_rta_board_read(&b,pcm,512,&n,&discontinuity)==ESP_ERR_INVALID_STATE&&!discontinuity);read_error=ESP_ERR_TIMEOUT;assert(audio_rta_board_read(&b,pcm,512,&n,&discontinuity)==ESP_ERR_TIMEOUT);read_error=0;cleanup(&b);
 /* Every close-stage failure retains its live handle and succeeds on retry. */
 calls=0;memset(&b,0,sizeof(b));assert(!audio_rta_board_open(&b,(void*)1,0));calls=0;assert(!audio_rta_board_close(&b));int close_stages=calls;
 for(int k=1;k<=close_stages;k++){calls=0;fail_at=0;memset(&b,0,sizeof(b));assert(!audio_rta_board_open(&b,(void*)1,0));calls=0;fail_at=k;audio_rta_board_close(&b);cleanup(&b);}
 printf("PASS actual adapter+installed ES8311: %d init and %d teardown transaction faults;48k format/registers/gain/mute, busy-before-codec, partial/odd reads, overrun, timeout; outstanding channels=%d devices=%d\n",stages,close_stages,live_channels,live_dev);return 0;}
""")
incs=[D,R/'ESP32C5/main',M/'include',M/'interface',M/'device/include',M/'device/es8311',M/'device',M/'device/priv_include']
cmd=['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-DCONFIG_CODEC_ES8311_SUPPORT=1','-include','stdlib.h',*['-I'+str(p) for p in incs],str(D/'host.c'),str(M/'device/es8311/es8311.c'),str(M/'esp_codec_dev_vol.c'),'-Wl,--wrap=calloc','-lm','-o',str(D/'host')]
with (D/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
subprocess.run([str(D/'host')],check=True)
