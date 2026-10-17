"""Clock-only production callback and changed-text execution; not hardware proof."""
from pathlib import Path
import subprocess, unittest
import test_revision91 as helpers
ROOT=helpers.ROOT
OUT=ROOT/'.hermes/targeted93'
HELPER='static void clock_label_set_text_if_changed(lv_obj_t *label, const char *text)'
CALLBACK='static void clock_ui_timer_cb(lv_timer_t *timer)\n{'
LABELS=['s_ntp_source_lbl','s_ntp_time_lbl','s_ntp_date_lbl','s_clock_maidenhead_lbl','s_ntp_offset_lbl','s_ntp_ip_lbl','s_ntp_network_lbl','s_ntp_host_lbl','s_ntp_service_lbl','s_clock_reliability_lbl','s_clock_caps_lbl','s_ntp_age_lbl','s_ntp_uncert_lbl','s_ntp_req_lbl']
BASE=r"""#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
typedef struct {char text[160];bool has_text;unsigned sets;} lv_obj_t;
typedef int lv_timer_t;typedef unsigned lv_color_t;
static unsigned setter_calls;
static const char *lv_label_get_text(lv_obj_t *label){assert(label);return label->has_text?label->text:NULL;}
static void lv_label_set_text(lv_obj_t *label,const char *text){assert(label&&text);snprintf(label->text,sizeof(label->text),"%s",text);label->has_text=true;label->sets++;setter_calls++;}
"""
class Targeted93(unittest.TestCase):
 extract=helpers.Revision91.extract
 def run_c(self,name,code):
  OUT.mkdir(parents=True,exist_ok=True);src=OUT/(name+'.c');src.write_text(code);exe=OUT/name
  cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-format-truncation','-fsanitize=address,undefined','-fno-omit-frame-pointer','-g',str(src),'-o',str(exe)]
  result=subprocess.run(cmd,capture_output=True,text=True);(OUT/(name+'-compile.log')).write_text(result.stdout+result.stderr);self.assertEqual(result.returncode,0,result.stderr)
  result=subprocess.run([str(exe)],capture_output=True,text=True);(OUT/(name+'-runtime.log')).write_text(result.stdout+result.stderr);self.assertEqual(result.returncode,0,result.stderr)
 def test_changed_text_production_helper(self):
  source=(ROOT/'ESP32C5/main/main.c').read_text();self.assertTrue(HELPER+'\n{' in source,'missing production changed-text guard')
  fn=self.extract(source,HELPER+'\n{')
  self.run_c('changed-text',BASE+fn+r"""
int main(void){lv_obj_t label={0};clock_label_set_text_if_changed(NULL,"text");clock_label_set_text_if_changed(&label,NULL);assert(setter_calls==0);
clock_label_set_text_if_changed(&label,"first");assert(setter_calls==1&&label.sets==1);
char same[]="first";assert(same!=label.text);clock_label_set_text_if_changed(&label,same);assert(setter_calls==1);
clock_label_set_text_if_changed(&label,"changed");assert(setter_calls==2&&label.sets==2);
clock_label_set_text_if_changed(&label,label.text);assert(setter_calls==2);
strcpy(label.text,"externally updated");clock_label_set_text_if_changed(&label,"changed");assert(setter_calls==3);
memset(&label,0,sizeof(label));clock_label_set_text_if_changed(&label,"changed");assert(setter_calls==4&&label.sets==1);
lv_obj_t other={0};clock_label_set_text_if_changed(&other,"changed");assert(setter_calls==5&&other.sets==1);
puts("CLOCK_HELPER content equality across addresses, changed/null/first/recreated/new/external PASS");return 0;}
""")
 def test_production_callback_stable_labels_and_second_cadence(self):
  source=(ROOT/'ESP32C5/main/main.c').read_text();helper=self.extract(source,HELPER+'\n{') if HELPER+'\n{' in source else ''
  cb=self.extract(source,CALLBACK)
  code=BASE+r"""
enum {CYM_TIME_UNSYNCED,CYM_TIME_GPS_ACQUIRING,CYM_TIME_GPS_LOCKED,CYM_TIME_NETWORK_SYNC,CYM_TIME_NTP_HOLDOVER,CYM_TIME_RTC_HOLDOVER,CYM_TIME_GPS_RTC_HOLDOVER,CYM_TIME_RTOS_HOLDOVER};
typedef struct {struct timeval utc;int source,reliability;bool gps_rtc_trusted,estimate_characterized;uint64_t source_age_ms;uint32_t uncertainty_us;} cym_time_snapshot_t;
typedef struct {unsigned long valid_requests;} cym_ntp_server_stats_t;
static cym_time_snapshot_t sample;static bool have_snapshot=true;
static bool cym_timekeeper_snapshot(cym_time_snapshot_t*out){*out=sample;return have_snapshot;}
static const char *cym_timekeeper_reliability_name(int reliability){return reliability?"Good":"Untrusted";}
static unsigned requests;
static void cym_ntp_server_get_stats(cym_ntp_server_stats_t*out){out->valid_requests=requests;}
static struct {bool valid;double latitude,longitude;} current_gps;
static bool maidenhead6(double lat,double lon,char out[7]){(void)lat;(void)lon;strcpy(out,"AA00aa");return true;}
#define BOARD_TIME_HAS_GPS_UART 1
#define BOARD_TIME_HAS_RTC 1
#define BOARD_TIME_HAS_MDNS 1
#define LV_OBJ_FLAG_HIDDEN 1
#define NTP_AP_PASSWORD "synthetic-fixture"
enum {CLOCK_MODE_DISPLAY_ONLY,CLOCK_MODE_AP_NTP,CLOCK_MODE_CLIENT_NTP};
enum {NTP_PUBLIC_IDLE,NTP_PUBLIC_SYNCING,NTP_PUBLIC_SUCCESS,NTP_PUBLIC_TIME_OK,NTP_PUBLIC_TIMEOUT,NTP_PUBLIC_SKIPPED_GPS};
static int s_clock_mode,s_ntp_public_state,g_clock_offset_minutes;
static bool s_ntp_clock_active=true,s_ntp_wifi_connected,s_ntp_wifi_failed,s_ntp_mdns_ok,s_ntp_udp_ok;
static const char *s_ntp_net_status="Connecting...",*s_ntp_mdns_status="mDNS: Idle";
static char s_ntp_ip_str[40],s_ntp_ap_ssid[40];
static lv_color_t source_color;
static lv_color_t lv_color_hex(unsigned value){return value;}
static void lv_obj_set_style_text_color(lv_obj_t*obj,lv_color_t color,int part){assert(obj&&part==0);source_color=color;}
static void lv_obj_clear_flag(lv_obj_t*obj,int flag){assert(obj&&flag==1);}
static void lv_obj_add_flag(lv_obj_t*obj,int flag){assert(obj&&flag==1);}
static lv_obj_t *s_ntp_retry_btn;
"""
  code+='\n'.join('static lv_obj_t *'+n+';' for n in LABELS)+'\n'+helper+'\n'+cb
  code+='\nint main(void){lv_obj_t labels[14]={0};\n'+'\n'.join(f'{n}=&labels[{i}];' for i,n in enumerate(LABELS))
  code+=r"""
sample.utc.tv_sec=0;sample.source=CYM_TIME_NETWORK_SYNC;sample.reliability=1;s_clock_mode=CLOCK_MODE_CLIENT_NTP;s_ntp_public_state=NTP_PUBLIC_TIME_OK;
clock_ui_timer_cb(NULL);assert(setter_calls==14);assert(!strcmp(s_ntp_time_lbl->text,"00:00:00"));assert(!strcmp(s_ntp_date_lbl->text,"1970-01-01"));assert(source_color==0x69F0AE);
setter_calls=0;clock_ui_timer_cb(NULL);assert(setter_calls==0);
for(int second=1;second<=3;second++){sample.utc.tv_sec=second;setter_calls=0;clock_ui_timer_cb(NULL);char expected[16];snprintf(expected,sizeof(expected),"00:00:%02d",second);assert(!strcmp(s_ntp_time_lbl->text,expected));assert(setter_calls==1);}
setter_calls=0;sample.utc.tv_sec=86400;clock_ui_timer_cb(NULL);assert(setter_calls==2);assert(!strcmp(s_ntp_date_lbl->text,"1970-01-02"));
setter_calls=0;s_ntp_udp_ok=true;s_ntp_mdns_ok=true;s_ntp_mdns_status="mDNS: Registered cym-ntp.local";requests=7;s_ntp_public_state=NTP_PUBLIC_TIMEOUT;clock_ui_timer_cb(NULL);assert(setter_calls==4);assert(!strcmp(s_ntp_service_lbl->text,"NTP: UDP/123 SERVING"));assert(!strcmp(s_ntp_network_lbl->text,"Public NTP: retrying in 60s"));
setter_calls=0;sample.source=CYM_TIME_GPS_LOCKED;clock_ui_timer_cb(NULL);assert(setter_calls==2);assert(source_color==0x69F0AE);assert(!strcmp(s_ntp_source_lbl->text,"GPS LOCK"));
setter_calls=0;s_ntp_clock_active=false;sample.utc.tv_sec++;clock_ui_timer_cb(NULL);assert(setter_calls==0);
s_ntp_clock_active=true;s_ntp_time_lbl=NULL;setter_calls=0;have_snapshot=false;clock_ui_timer_cb(NULL);assert(!strcmp(s_ntp_source_lbl->text,"UNSYNCED"));assert(source_color==0xFF5252);
puts("CLOCK_CALLBACK 14 first updates,0 stable updates,1 per second,2 at day change,4 service changes PASS (synthetic source)");return 0;}
"""
  self.run_c('clock-callback',code)
 def test_scope_cadence_and_stop_contract(self):
  source=(ROOT/'ESP32C5/main/main.c').read_text();cb=self.extract(source,CALLBACK)
  self.assertNotIn('lv_label_set_text(',cb)
  for label in LABELS:self.assertIn('clock_label_set_text_if_changed('+label,cb)
  shown=self.extract(source,'static void show_clock_screen(void)\n{')
  self.assertIn('lv_timer_create(clock_ui_timer_cb, 1000, NULL)',shown)
  self.assertLess(shown.index('create_function_page_base("Clock")'),shown.index('g_screen_stop_fn = clock_stop'))
  self.assertIn('lv_disp_get_ver_res(NULL)',shown);self.assertIn('LV_SCROLLBAR_MODE_AUTO',shown)
  stop=self.extract(source,'static void clock_stop(void)\n{')
  self.assertIn('lv_timer_del(s_ntp_ui_timer)',stop)
  for label in LABELS:self.assertIn(label+' = NULL;',stop)
  for name in ['show_main_tiles','show_cat_tools']:
   menu=self.extract(source,'static void '+name+'(void)\n{');self.assertIn('"Clock"',menu)
if __name__=='__main__':unittest.main(verbosity=2)
