from pathlib import Path
import subprocess,unittest
from test_exclusive_owner_lifecycle import function
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'ESP32C5/components/cym_doom'
class RebootTransaction(unittest.TestCase):
 def test_production_nvs_admission_rotation_and_early_consume(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text()
  funcs='\n'.join(function(s,n) for n in ('game_nvs_read','game_nvs_set','game_nvs_erase','game_nvs_commit','game_nvs_io','game_early_consume','game_selector_rotation','game_record_reboot'))
  code=r"""
#include "game_mode.h"
#include "storage_gate.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef int esp_err_t;typedef unsigned nvs_handle_t;
enum{ESP_OK,ESP_ERR_NVS_NOT_FOUND,ESP_RST_SW=7,NVS_READWRITE=1,pdTRUE=1,BOOT_BTN_GPIO=28,LV_OBJ_FLAG_HIDDEN=1};
static game_intent data;static int present,open_fault,set_fault,commit_fault,erase_fault,read_fault;
static int commits,erases,reboots,takes,gives,boot_init,boot_held,reason=ESP_RST_SW;
static const char*blocker;static bool transport=true,held;
static void *sd_spi_mutex=(void*)1,*function_page=(void*)2,*title_bar=(void*)3;
static bool s_game_reboot_frozen,s_game_selector_rotated;static uint8_t screen_orientation,s_game_prior_orientation,live_rotation;
static int nvs_open(const char*n,int m,nvs_handle_t*h){assert(!strcmp(n,"cym_game")&&m==NVS_READWRITE);*h=1;return open_fault?9:ESP_OK;}
static void nvs_close(nvs_handle_t h){assert(h==1);}
static int nvs_get_blob(nvs_handle_t h,const char*k,void*v,size_t*n){assert(h==1&&!strcmp(k,"intent"));if(read_fault)return 9;if(!present)return ESP_ERR_NVS_NOT_FOUND;memcpy(v,&data,sizeof(data));*n=sizeof(data);return ESP_OK;}
static int nvs_set_blob(nvs_handle_t h,const char*k,const void*v,size_t n){assert(h==1&&!strcmp(k,"intent")&&n==12);if(set_fault)return 9;memcpy(&data,v,n);present=1;return ESP_OK;}
static int nvs_erase_key(nvs_handle_t h,const char*k){assert(h==1&&!strcmp(k,"intent"));erases++;if(erase_fault)return 9;present=0;return ESP_OK;}
static int nvs_commit(nvs_handle_t h){assert(h==1);commits++;return commit_fault?9:ESP_OK;}
static void init_boot_button(void){boot_init++;}
static int gpio_get_level(int pin){assert(pin==28);return !boot_held;}
static int esp_reset_reason(void){return reason;}
static int xSemaphoreTake(void*h,int ticks){assert(h&&ticks==0);takes++;if(!transport)return 0;held=true;return pdTRUE;}
static void xSemaphoreGive(void*h){assert(h&&held);gives++;held=false;}
static const char*game_storage_blocker(void){return blocker;}
static void esp_restart(void){assert(present&&held&&s_game_reboot_frozen);assert(!storage_gate_enter());reboots++;}
static void apply_screen_orientation(int rotation){live_rotation=rotation;}
static void lv_obj_add_flag(void*o,int flag){assert(o&&flag==LV_OBJ_FLAG_HIDDEN);}
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
"""+funcs+r"""
int main(void){
 for(int choice=0;choice<4;choice++){
  screen_orientation=choice;live_rotation=choice;game_selector_rotation(true);assert(live_rotation==3&&screen_orientation==choice);game_selector_rotation(true);game_selector_rotation(false);assert(live_rotation==choice&&screen_orientation==choice);
 }
 blocker="s_fileserv_httpd";assert(!strcmp(game_record_reboot(),blocker));assert(!takes&&!reboots&&!s_game_reboot_frozen);blocker=NULL;
 assert(storage_gate_enter());assert(strstr(game_record_reboot(),"SD open file"));assert(storage_gate_enter());storage_gate_leave();storage_gate_leave();
 transport=false;assert(strstr(game_record_reboot(),"SD transport"));assert(!s_game_reboot_frozen);transport=true;
 open_fault=1;assert(strstr(game_record_reboot(),"NVS intent open"));assert(!held&&!s_game_reboot_frozen);open_fault=0;
 set_fault=1;assert(strstr(game_record_reboot(),"NVS intent set/commit"));assert(!commits&&!held&&!reboots);set_fault=0;
 commit_fault=1;assert(strstr(game_record_reboot(),"NVS intent set/commit"));assert(erases==1&&!present&&!held&&!reboots);commit_fault=0;
 (void)game_record_reboot();assert(reboots==1&&present&&held);xSemaphoreGive(sd_spi_mutex);storage_gate_thaw();s_game_reboot_frozen=false;
 assert(game_early_consume(ESP_OK)==GAME_DOOM);assert(!present&&boot_init==1);assert(game_early_consume(ESP_OK)==GAME_NORMAL);
 game_mode_io io=game_nvs_io(1);assert(game_mode_record(&io,GAME_DOOM));boot_held=1;assert(game_early_consume(ESP_OK)==GAME_NORMAL&&!present);boot_held=0;
 assert(game_mode_record(&io,GAME_DOOM));reason=0;assert(game_early_consume(ESP_OK)==GAME_NORMAL&&!present);reason=ESP_RST_SW;
 assert(game_mode_record(&io,GAME_DOOM));erase_fault=1;assert(game_early_consume(ESP_OK)==GAME_NORMAL&&present);erase_fault=0;reason=0;assert(game_early_consume(ESP_OK)==GAME_NORMAL&&!present);
 puts("production main: named write refusal/freeze/SD-lock/open/set/commit faults, successful same-image reset, real NVS adapter consume, BOOT/power bypass, all4 live rotation restoration PASS");return 0;
}
"""
  out=ROOT/'.hermes/doom-prototype/transaction-host';out.mkdir(parents=True,exist_ok=True);(out/'cases.c').write_text(code)
  r=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-I'+str(COMP/'include'),str(out/'cases.c'),str(COMP/'game_mode.c'),str(COMP/'storage_gate.c'),'-o',str(out/'cases')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  r=subprocess.run([str(out/'cases')],capture_output=True,text=True);(out/'runtime.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
