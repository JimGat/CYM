#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_ERR_INVALID_ARG 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_NOT_SUPPORTED 3
#define ESP_ERR_INVALID_RESPONSE 4
static uint8_t regs[256];
static bool s_battery_adc_ready;
static int fail_reg=-1, write_fail, writes;
static void *s_pmic_dev;
static esp_err_t ws35_pmic_read(uint8_t reg,uint8_t *data,size_t len) {
 if(reg==fail_reg)return 9;
 memcpy(data,regs+reg,len);return 0;
}
static esp_err_t i2c_master_transmit(void *dev,const uint8_t *b,size_t len,int timeout) {
 (void)dev;assert(timeout==100);assert(len==2);assert(b[0]==0x30);writes++;
 if(write_fail)return 8;
 regs[b[0]]=b[1];return 0;
}
/* PRODUCTION_FUNCTION */
int main(void) {
 bool present=true;uint16_t mv=42;
 regs[3]=0x4a;
 assert(ws_c5_35_battery_read(NULL,&mv)==ESP_ERR_INVALID_ARG);
 for(int ctrl=0;ctrl<256;ctrl++) {
  regs[0x30]=ctrl;s_battery_adc_ready=false;regs[0]=0;writes=0;
  int result=ws_c5_35_battery_read(&present,&mv);
  assert(regs[0x30]==(ctrl|1));assert(writes==((ctrl&1)?0:1));
  assert(result==((ctrl&1)?ESP_OK:ESP_ERR_INVALID_STATE));assert(!present && mv==0);
 }
 s_battery_adc_ready=true;regs[0]=8;
 for(int v=2500;v<=5000;v+=25){regs[0x34]=0xe0|(v>>8);regs[0x35]=v;assert(ws_c5_35_battery_read(&present,&mv)==0);assert(present && mv==v);}
 regs[0x34]=0;regs[0x35]=0;assert(ws_c5_35_battery_read(&present,&mv)==ESP_ERR_INVALID_RESPONSE);assert(!present && mv==0);
 for(int reg=0;reg<3;reg++){fail_reg=(int[]){3,0,0x34}[reg];assert(ws_c5_35_battery_read(&present,&mv)==9);assert(!present && mv==0);}fail_reg=-1;
 s_battery_adc_ready=false;fail_reg=0x30;assert(ws_c5_35_battery_read(&present,&mv)==9);assert(!s_battery_adc_ready);fail_reg=-1;
 regs[0x30]=0;write_fail=1;assert(ws_c5_35_battery_read(&present,&mv)==8);assert(!s_battery_adc_ready);write_fail=0;
 regs[3]=0;assert(ws_c5_35_battery_read(&present,&mv)==ESP_ERR_NOT_SUPPORTED);
 return 0;
}
