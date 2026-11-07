#!/usr/bin/env python3
# Production-extracted real settings loader and saver. Mock NVS follows installed
# immediate per-key writes; this is reboot fault simulation, not brownout proof.
import os,re,subprocess,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=Path(os.environ.get("CYM_POWER_SOURCE",R))
O=Path(os.environ["CYM_TEST_OUT"])/"power-storage";O.mkdir(parents=True,exist_ok=False)
s=(S/"ESP32C5/main/main.c").read_text();w=(S/"ESP32C5/components/wifi_cli/wifi_common.c").read_text();h=(S/"ESP32C5/components/wifi_cli/include/wifi_common.h").read_text()
def fn(s,sig):
 a=s.index(sig);b=s.index("{",a);i=b+1;d=1
 while d:d+=(s[i]=="{")-(s[i]=="}");i+=1
 return s[a:i]
types=h[h.index("/* >>> CYM_PWR_DECODE_TYPES_BEGIN"):h.index("CYM_PWR_DECODE_TYPES_END */")+len("CYM_PWR_DECODE_TYPES_END */")]
macros="\n".join(l for l in s.splitlines() if l.startswith("#define NVS_") and not l.rstrip().endswith("\\"))
pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int esp_err_t;typedef int nvs_handle_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_ARG 0x102
#define ESP_ERR_NVS_NOT_FOUND 0x1102
#define ESP_ERR_NVS_TYPE_MISMATCH 0x1103
#define NVS_READONLY 0
#define NVS_READWRITE 1
#define CONFIG_BOARD_LCD_BRIGHTNESS_DEFAULT 80
#define GPS_STALE_ACCURACY_M 100
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
int open_rc,fail_set,sets,commit_rc,commits,closed;
int lvl_rd=ESP_ERR_NVS_NOT_FOUND,leg_rd=ESP_ERR_NVS_NOT_FOUND;
uint8_t stored_lvl,stored_leg;
int unrelated=0x4567;
int nvs_open(const char*n,int m,nvs_handle_t*h){(void)n;(void)m;*h=7;return open_rc;}
int nvs_get_u8(int h,const char*k,uint8_t*v){(void)h;if(!strcmp(k,"pwr_lvl")){*v=stored_lvl;return lvl_rd;}if(!strcmp(k,"pwr_mode")){*v=stored_leg;return leg_rd;}return ESP_ERR_NVS_NOT_FOUND;}
int nvs_set_u8(int h,const char*k,uint8_t v){assert(h==7);if(++sets==fail_set)return ESP_FAIL;if(!strcmp(k,"pwr_lvl")){stored_lvl=v;lvl_rd=0;}else if(!strcmp(k,"pwr_mode")){stored_leg=v;leg_rd=0;}else assert(!"unrelated key write");return 0;}
int nvs_commit(int h){assert(h==7);commits++;return commit_rc;}
void nvs_close(int h){assert(h==7);closed++;}
#define GETSTUB(n,t) int n(int h,const char*k,t*v){(void)h;(void)k;(void)v;return ESP_ERR_NVS_NOT_FOUND;}
GETSTUB(nvs_get_i32,int32_t) GETSTUB(nvs_get_u16,uint16_t) GETSTUB(nvs_get_u32,uint32_t) GETSTUB(nvs_get_i16,int16_t)
int nvs_get_str(int h,const char*k,char*v,size_t*z){(void)h;(void)k;(void)v;(void)z;return ESP_ERR_NVS_NOT_FOUND;}
uint8_t g_pwr_lvl;bool g_max_power_mode;
int screen_timeout_ms,screen_brightness_pct,screen_orientation,g_home_layout_4cat,g_home_layout_nvs_present,scan_time_min_ms,scan_time_max_ms,dark_mode_enabled,g_gatt_timeout_ms;
char g_saved_wifi_ssid[33],g_saved_wifi_pass[65],wigle_api_key[100],wdgwars_api_key[100];
typedef int wd_band_t;typedef int wd_radio_mode_t;
int g_wd_band,g_wd_pcap,g_wd_radio_mode,g_wd_adaptive,g_wd_manual_mode,g_wd_speed_unit,g_wd_gps_baud,g_gps_debug_serial,g_rf_hat_enabled,g_btsc_counter,g_cc1101_freq_offset_millippm,g_bt_scan_duration_s,g_clock_offset_minutes,g_ntp_clock_brightness_pct;
#define WD_MODE_COUNT 5
struct {float latitude,longitude,altitude,accuracy;bool valid;} g_gps_last_known;
void wifi_scanner_set_scan_time(int a,int b){(void)a;(void)b;}void gw_set_timeout(int t){(void)t;}
"""
post=r"""
static void reset(void){open_rc=fail_set=sets=commit_rc=commits=closed=0;lvl_rd=leg_rd=ESP_ERR_NVS_NOT_FOUND;g_pwr_lvl=2;g_max_power_mode=true;}
int main(void){
 reset();open_rc=ESP_FAIL;nvs_settings_load();
 assert(g_pwr_lvl==1 && s_pwr_load_source==PWR_SRC_ERROR && "real loader open error must not be fresh");
 reset();nvs_settings_load();assert(g_pwr_lvl==1 && s_pwr_load_source==PWR_SRC_FRESH);
 reset();leg_rd=0;stored_leg=1;nvs_settings_load();assert(g_pwr_lvl==2);
 lvl_rd=0;stored_lvl=1;nvs_settings_load();assert(g_pwr_lvl==1);
 lvl_rd=ESP_ERR_NVS_TYPE_MISMATCH;nvs_settings_load();assert(g_pwr_lvl==1 && s_pwr_load_source==PWR_SRC_ERROR);
 reset();leg_rd=0;stored_leg=2;nvs_settings_load();assert(g_pwr_lvl==1 && s_pwr_load_source==PWR_SRC_ERROR);
 reset();assert(nvs_settings_save_power_level(0)!=0 && sets==0 && commits==0);
 for(int stage=1;stage<=2;stage++){
  reset();lvl_rd=leg_rd=0;stored_lvl=1;stored_leg=0;fail_set=stage;
  assert(nvs_settings_save_power_level(2)!=0);
  assert(sets==stage && commits==0 && closed==1 && "stop after failed setter, no commit");
  fail_set=0;g_pwr_lvl=1;nvs_settings_load();assert(g_pwr_lvl==(stage==1?1:2));
  assert(stored_leg==0 && unrelated==0x4567);
 }
 reset();commit_rc=ESP_FAIL;assert(nvs_settings_save_power_level(2)!=0);assert(commits==1);
 nvs_settings_load();assert(g_pwr_lvl==2 && "commit failure is uncertain, not rollback");
 reset();assert(nvs_settings_save_power_level(1)==0);assert(sets==2 && commits==1 && closed==1);
 nvs_settings_load();assert(g_pwr_lvl==1 && unrelated==0x4567);
 puts("PASS real loader/save: open, precedence, migration, invalid, partial writes, uncertain commit, reboot, unrelated keys");
}
"""
state="static pwr_src_t s_pwr_load_source = PWR_SRC_FRESH;\n"
# Incoming candidate has no source state; retain FRESH to expose the actual missing assignment.
body=pre+types+"\n"+macros+"\n"+state+fn(w,"pwr_decode_t pwr_decode(")+fn(s,"static inline pwr_key_rd_t pwr_map_rd(")+fn(s,"static void nvs_settings_load(void)")+fn(s,"static esp_err_t nvs_settings_save_power_level(")+post
(O/"host.c").write_text(body)
c=["cc","-std=gnu11","-g","-fsanitize=address,undefined","-fno-pie","-no-pie",str(O/"host.c"),"-o",str(O/"host")]
b=subprocess.run(c,capture_output=True,text=True);(O/"compile.log").write_text(b.stdout+b.stderr);assert b.returncode==0,b.stderr
r=subprocess.run([str(O/"host")],capture_output=True,text=True);(O/"run.log").write_text(r.stdout+r.stderr)
(O/"results.json").write_text(json.dumps(dict(command=c,exit=r.returncode,stdout=r.stdout,stderr=r.stderr),indent=2));print(r.stdout+r.stderr);raise SystemExit(r.returncode)
