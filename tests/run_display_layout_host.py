#!/usr/bin/env python3
"""Extract production layout, pagination and callbacks; execute installed LVGL without RF."""
from pathlib import Path
import re,subprocess,os,json,sys,hashlib
R=Path(__file__).resolve().parents[1];E=Path(os.environ['CYM_TEST_OUT']);E.mkdir(parents=True,exist_ok=True)
S=subprocess.check_output(['git','show','HEAD:ESP32C5/main/main.c'],cwd=R,text=True) if os.environ.get('BASELINE') else (R/'ESP32C5/main/main.c').read_text();LV=R/'ESP32C5/managed_components/lvgl__lvgl';D=E/(sys.argv[1] if len(sys.argv)>1 else "display-layout");D.mkdir(exist_ok=True)
def function(n):
 m=re.search(r'(?:static\s+)?(?:inline\s+)?(?:lv_obj_t\s*\*|void\s+|int\s+)'+n+r'\([^;]*?\)\s*\{',S);assert m,n
 i=m.end();depth=1
 while depth:depth+=(S[i]=='{')-(S[i]=='}');i+=1
 return S[m.start():i]
pre=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <malloc.h>
#include <time.h>
#include "lvgl.h"
static size_t lv_live,lv_peak;
void*track_alloc(size_t n){void*p=malloc(n);if(p)lv_live+=malloc_usable_size(p);if(lv_live>lv_peak)lv_peak=lv_live;return p;}
void track_free(void*p){if(p)lv_live-=malloc_usable_size(p);free(p);}
void*track_realloc(void*p,size_t n){size_t old=p?malloc_usable_size(p):0;void*q=realloc(p,n);if(q){lv_live=lv_live-old+malloc_usable_size(q);if(lv_live>lv_peak)lv_peak=lv_live;}return q;}
#define BOARD_HAS_AUDIO_RTA 0
#define FONT lv_font_montserrat_14
#define lv_extra_symbols FONT
#define g_font_icon14 FONT
#define UI_ACCENT_BLUE lv_color_hex(0x1565c0)
#define UI_ACCENT_RED lv_color_hex(0xff0000)
#define UI_ACCENT_AMBER lv_color_hex(0xffa000)
#define UI_ACCENT_PURPLE lv_color_hex(0x8e24aa)
#define UI_ACCENT_CYAN lv_color_hex(0x00bcd4)
#define COLOR_MATERIAL_RED UI_ACCENT_RED
#define COLOR_MATERIAL_GREEN lv_color_hex(0x008800)
#define COLOR_MATERIAL_TEAL lv_color_hex(0x008080)
#define MY_SYMBOL_SKULL_CROSS "S"
#define MY_SYMBOL_SATELLITE "S"
#define MY_SYMBOL_SATELLITE_DISH "D"
#define MY_SYMBOL_DATABASE "D"
#define MY_SYMBOL_BINOCULARS "B"
#define MY_SYMBOL_JET_FIGHTER "J"
#define MY_SYMBOL_CHART_BAR "C"
#define MY_SYMBOL_WAVE "W"
#define MY_SYMBOL_TOWER "T"
#define MY_SYMBOL_EYE "E"
#define MY_SYMBOL_SHIELD "S"
#define MY_SYMBOL_RADAR "R"
#define MY_SYMBOL_NETWORK "N"
static bool dark_mode_enabled=true;
static int screen_orientation,clicks,attacks;
static lv_obj_t *function_page,*home_bg_img,*s_ntp_mode_popup;
static lv_obj_t *s_cc1101_ht_offset_lbl,*s_cc1101_ht_cal_btn,*s_cc1101_ht_status,*s_cc1101_ht_pn,*s_cc1101_ht_ver,*s_cc1101_ht_marc,*s_cc1101_ht_rssi,*s_cc1101_ht_freq;
static void show_audio_rta(void){}
static void show_bluetooth_screen(void){}
static void show_deauth_monitor_screen(void){}
static void show_detect_defend_screen(void){}
static void show_dip_switch_popup(int a,const char*b,void(*c)(void)){(void)a;(void)b;(void)c;}
static void show_disco_mode(void){}
static void show_drone_detector_screen(void){}
static void show_drone_spoof_screen(void){}
static void show_drone_stuff_screen(void){}
static void show_espnow_scout_screen(void){}
static void show_global_attacks_screen(void){}
static void show_go_dark_confirm(void){}
static void show_iot_ot_menu_screen(void){}
static void show_nfc_hub_screen(void){}
static void show_obs_store_screen(void){}
static void show_ot_survey_screen(void){}
static void show_qr_decoder(void){}
static void show_radio_menu_screen(void){}
static void show_wardrive_menu_screen(void){}
static void show_wifi_analyzer_screen(void){}
static void show_wifi_pcap_screen(void){}
static void show_wifi_scan_attack_screen(void){}
static void show_wscope_screen(void){}
static void show_zigbee_wardrive_screen(void){}
static void sniffer_yes_btn_cb(void*p){(void)p;}
static void show_ir_menu_screen(void){}
static bool s_ntp_stopping;static int g_cc1101_freq_offset_millippm;
static lv_color_t ui_bg_color(void){return lv_color_hex(0x111111);}
static lv_color_t ui_panel_color(void){return lv_color_hex(0x222222);}
static lv_color_t ui_card_color(void){return lv_color_hex(0x333333);}
static lv_color_t ui_card_pressed_color(void){return lv_color_hex(0x555555);}
static lv_color_t ui_border_color(void){return lv_color_hex(0x777777);}
static lv_color_t ui_text_color(void){return lv_color_white();}
static lv_color_t ui_muted_color(void){return lv_color_hex(0x888888);}
static lv_color_t ui_accent_color(void){return UI_ACCENT_BLUE;}
static void clock_network_cleanup_poll(void){}
static void clock_mode_popup_close(void){if(s_ntp_mode_popup)lv_obj_del(s_ntp_mode_popup);s_ntp_mode_popup=NULL;}
static void clicked(lv_event_t*e){(void)e;clicks++;}
#define clock_mode_display_cb clicked
#define clock_mode_client_cb clicked
#define clock_mode_ap_cb clicked
#define clock_mode_cancel_cb clicked
#define s_cc1101_ht_run_cb clicked
#define s_offset_entry_cb clicked
#define s_cal_tx_toggle_cb clicked
static void main_tile_event_cb(lv_event_t*);
static int settings_tap_count;static lv_timer_t*settings_nav_timer;
static void settings_nav_timer_cb(lv_timer_t*t){(void)t;}
#define ESP_LOGI(...) ((void)0)
static void(*s_ntp_return_fn)(void);
static void show_main_tiles(void){}
static void show_cat_tools(void){}
static void show_clock_or_mode_prompt(void(*fn)(void));
static void s_cal_tx_stop(void){}
static void show_cc1101_screen(void){}
static void rfhat_add_back_btn(const char*n,void(*f)(void)){(void)n;(void)f;}
static void create_function_page_base(const char*n){(void)n;lv_obj_clean(lv_scr_act());home_bg_img=NULL;function_page=lv_obj_create(lv_scr_act());lv_obj_remove_style_all(function_page);lv_obj_set_size(function_page,lv_disp_get_hor_res(NULL),lv_disp_get_ver_res(NULL));lv_obj_clear_flag(function_page,LV_OBJ_FLAG_SCROLLABLE);}
extern const lv_img_dsc_t lab_bg;
static lv_obj_t *scan_list,*wifi_sas_nav_bar,*wifi_sas_nav_prev,*wifi_sas_nav_lbl,*wifi_sas_nav_next;
static int wifi_sas_page,total;
typedef struct {uint8_t ssid[33],bssid[6];int primary,authmode,rssi;}wifi_ap_record_t;
enum{WIFI_AUTH_WPA3_PSK,WIFI_AUTH_WPA2_WPA3_PSK,WIFI_AUTH_OWE,WIFI_AUTH_WPA3_ENT_192,WIFI_AUTH_WPA3_ENTERPRISE,WIFI_AUTH_WPA2_WPA3_ENTERPRISE,WIFI_AUTH_WPA2_PSK,WIFI_AUTH_WPA2_ENTERPRISE,WIFI_AUTH_WPA_WPA2_PSK,WIFI_AUTH_WPA_PSK,WIFI_AUTH_WEP,WIFI_AUTH_OPEN};
static wifi_ap_record_t records[64];static bool selected[64];
static const wifi_ap_record_t*wifi_scanner_get_results_ptr(void){return records;}
static int wifi_scanner_get_count(void){return total;}
static int wifi_scanner_get_selected(int*a,int cap){int n=0;for(int i=0;i<64&&n<cap;i++)if(selected[i])a[n++]=i;return n;}
static int wifi_scanner_get_selected_count(void){int a[64];return wifi_scanner_get_selected(a,64);}
static void wifi_scanner_select_network(int i,bool s){assert(i>=0&&i<64);selected[i]=s;}
static void show_attack_tiles_screen(void){attacks++;}
"""
if 'static inline int wifi_sas_page_size(void)' in S: page=function('wifi_sas_page_size')
else: page='#define WIFI_SAS_PAGE_SIZE 8\nstatic int wifi_sas_page_size(void){return WIFI_SAS_PAGE_SIZE;}\n'
functions=['create_tile','apply_menu_bg','show_wifi_menu_screen','show_clock_mode_popup','show_cc1101_hw_test_screen','wifi_sas_row_geom','scan_row_click_cb','wifi_scan_rebuild_page','wifi_scan_prev_page_cb','wifi_scan_next_page_cb','wifi_scan_next_btn_cb','show_clock_or_mode_prompt','main_tile_event_cb']
a=S.index('                lv_obj_t *next_btn =',S.index('bool wifi_sas_owns_completion ='))
b=S.index('                }  // End of "if (wifi_sas_should_finalize)"',a)
floating='static lv_obj_t* floating(void){'+S[a:b]+'return next_btn;}\n'
post=r"""
static int failures,checks;
#define CHECK(b,n) do{checks++;if(!(b)){failures++;printf("FAIL %s %dx%d rot%d\n",n,lv_disp_get_hor_res(NULL),lv_disp_get_ver_res(NULL),screen_orientation);}}while(0)
static lv_indev_t*pointer;static lv_indev_state_t state;static int px,py;
static void read_cb(lv_indev_drv_t*d,lv_indev_data_t*v){(void)d;v->point.x=px;v->point.y=py;v->state=state;}
static void sample(int x,int y,bool down){int rx=x,ry=y;lv_disp_drv_t*dr=lv_disp_get_default()->driver;if(screen_orientation==1){rx=y;ry=dr->ver_res-x-1;}else if(screen_orientation==2){rx=dr->hor_res-x-1;ry=dr->ver_res-y-1;}else if(screen_orientation==3){rx=dr->hor_res-y-1;ry=x;}px=rx;py=ry;state=down?LV_INDEV_STATE_PR:LV_INDEV_STATE_REL;lv_tick_inc(20);lv_indev_read_timer_cb(pointer->driver->read_timer);}
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){(void)a;(void)p;lv_disp_flush_ready(d);}
static void render(void){lv_obj_update_layout(lv_scr_act());lv_obj_update_layout(lv_layer_top());lv_refr_now(NULL);}
static bool contained(lv_obj_t*p,lv_obj_t*c){lv_area_t a,b;lv_obj_get_coords(p,&a);lv_obj_get_coords(c,&b);return b.x1>=a.x1&&b.x2<=a.x2&&b.y1>=a.y1&&b.y2<=a.y2;}
static void reachable(lv_obj_t*p,lv_obj_t*c,const char*n){lv_obj_scroll_to_view_recursive(c,LV_ANIM_OFF);render();CHECK(contained(p,c),n);}
static void swipe(lv_obj_t*p,lv_obj_t*target){lv_indev_reset(pointer,NULL);sample(0,0,false);lv_obj_scroll_to_y(p,0,LV_ANIM_OFF);render();if(lv_obj_get_scroll_bottom(p)<=0)return;lv_area_t a;lv_obj_get_coords(target,&a);int x=(a.x1+a.x2)/2,y=(a.y1+a.y2)/2;int before=clicks;sample(x,y,true);for(int i=1;i<=5;i++)sample(x,y-i*9,true);sample(x,y-45,false);CHECK(lv_obj_get_scroll_y(p)>0,"gesture actually scrolls");CHECK(clicks==before,"scroll release must not activate action");lv_indev_reset(pointer,NULL);}
static uint64_t ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec;}
int main(void){lv_init();static lv_color_t buf[480*32];static lv_disp_draw_buf_t db;lv_disp_draw_buf_init(&db,buf,NULL,480*32);static lv_disp_drv_t dr;lv_disp_drv_init(&dr);dr.hor_res=240;dr.ver_res=320;dr.draw_buf=&db;dr.flush_cb=flush;lv_disp_t*d=lv_disp_drv_register(&dr);static lv_indev_drv_t in;lv_indev_drv_init(&in);in.type=LV_INDEV_TYPE_POINTER;in.read_cb=read_cb;pointer=lv_indev_drv_register(&in);
int sizes[][2]={{240,320},{320,480}};
for(int menu=0;menu<2;menu++)for(int dim=0;dim<2;dim++)for(int rot=0;rot<4;rot++){
 dr.hor_res=sizes[dim][0];dr.ver_res=sizes[dim][1];lv_disp_drv_update(d,&dr);screen_orientation=rot;lv_disp_set_rotation(d,rot);int w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);
 create_function_page_base("blank");render();size_t menu_base=lv_live;show_wifi_menu_screen();render();for(unsigned ti=0;ti<lv_obj_get_child_cnt(lv_obj_get_child(function_page,0));ti++)lv_obj_add_event_cb(lv_obj_get_child(lv_obj_get_child(function_page,0),ti),clicked,LV_EVENT_CLICKED,NULL);printf("ALLOC wifi %dx%d rot%d delta=%zu live=%zu\n",w,h,rot,lv_live-menu_base,lv_live);lv_obj_t*grid=lv_obj_get_child(function_page,0);unsigned cnt=lv_obj_get_child_cnt(grid);CHECK(cnt>=10,"WiFi tile inventory");CHECK(lv_obj_has_flag(grid,LV_OBJ_FLAG_SCROLLABLE),"WiFi scrollable");reachable(grid,lv_obj_get_child(grid,0),"WiFi FIRST fully reachable");reachable(grid,lv_obj_get_child(grid,cnt-1),"WiFi LAST fully reachable");swipe(grid,lv_obj_get_child(grid,0));
 lv_area_t bg;lv_img_t*image=(lv_img_t*)home_bg_img;_lv_img_buf_get_transformed_area(&bg,lv_obj_get_width(home_bg_img),lv_obj_get_height(home_bg_img),image->angle,image->zoom,&image->pivot);bg.x1+=home_bg_img->coords.x1;bg.x2+=home_bg_img->coords.x1;bg.y1+=home_bg_img->coords.y1;bg.y2+=home_bg_img->coords.y1;CHECK(bg.x1<=0&&bg.y1<=0&&bg.x2>=w-1&&bg.y2>=h-1,"wallpaper covers live panel");printf("BG %dx%d zoom=%u area=%d,%d,%d,%d\n",w,h,image->zoom,bg.x1,bg.y1,bg.x2,bg.y2);
 lv_obj_t*route=lv_btn_create(function_page);lv_obj_add_event_cb(route,main_tile_event_cb,LV_EVENT_CLICKED,(void*)(menu?"Clock Modern":"Clock Classic"));lv_event_send(route,LV_EVENT_CLICKED,NULL);CHECK(s_ntp_return_fn==(menu?show_cat_tools:show_main_tiles),"Classic/Modern Clock return route");render();lv_area_t ca;lv_obj_get_coords(s_ntp_mode_popup,&ca);CHECK(ca.x1>=12&&ca.y1>=12&&ca.x2<w-12&&ca.y2<h-12,"Clock bounded card");CHECK(lv_obj_get_width(s_ntp_mode_popup)<=280&&lv_obj_get_height(s_ntp_mode_popup)<=250,"Clock design caps");CHECK(lv_obj_get_scroll_dir(s_ntp_mode_popup)==LV_DIR_VER,"Clock vertical scroll");
 for(int i=2;i<6;i++)reachable(s_ntp_mode_popup,lv_obj_get_child(s_ntp_mode_popup,i),"Clock action reachable incl Cancel");swipe(s_ntp_mode_popup,lv_obj_get_child(s_ntp_mode_popup,2));clock_mode_popup_close();
 show_cc1101_hw_test_screen();render();lv_obj_t*card=lv_obj_get_child(function_page,0);CHECK(lv_obj_get_scroll_dir(card)==LV_DIR_VER&&lv_obj_has_flag(card,LV_OBJ_FLAG_SCROLLABLE),"CC1101 scroll enabled");
 const char*texts[]={"Part: 0x00","Version: 0x14","MARCSTATE: IDLE","RSSI: -100 dBm","Frequency: 433.920 MHz"};lv_obj_t*labs[]={s_cc1101_ht_pn,s_cc1101_ht_ver,s_cc1101_ht_marc,s_cc1101_ht_rssi,s_cc1101_ht_freq};for(int i=0;i<5;i++)lv_label_set_text(labs[i],texts[i]);render();reachable(card,lv_obj_get_child(card,0),"CC FIRST");reachable(card,lv_obj_get_parent(s_cc1101_ht_cal_btn),"CC LAST calibration row");swipe(card,lv_obj_get_child(card,7));
 create_function_page_base("results");scan_list=lv_list_create(function_page);lv_obj_set_size(scan_list,lv_pct(100),h-116);lv_obj_set_style_pad_all(scan_list,0,0);lv_obj_set_style_pad_row(scan_list,1,0);lv_obj_set_style_border_width(scan_list,0,0);wifi_sas_nav_prev=lv_btn_create(function_page);wifi_sas_nav_next=lv_btn_create(function_page);wifi_sas_nav_lbl=lv_label_create(function_page);
 total=30;wifi_sas_page=0;size_t scan_base=lv_live;wifi_scan_rebuild_page();render();printf("ALLOC scan %dx%d rot%d delta=%zu rows=%u\n",w,h,rot,lv_live-scan_base,lv_obj_get_child_cnt(scan_list));int ps=(h-116)/25;if(ps<1)ps=1;CHECK(wifi_sas_page_size()==ps,"dynamic page capacity");
 for(int n=0;n<4;n++){
 total=(int[]){0,3,ps+1,2*ps+3}[n];wifi_sas_page=999;wifi_scan_rebuild_page();int pages=(total+ps-1)/ps;if(pages<1)pages=1;CHECK(wifi_sas_page==pages-1,"clamp refresh to LAST page");int rows=total?total-(pages-1)*ps:1;CHECK(lv_obj_get_child_cnt(scan_list)==(unsigned)rows,"empty partial LAST count");CHECK(lv_obj_has_flag(wifi_sas_nav_next,LV_OBJ_FLAG_HIDDEN),"LAST hides pagination Next");
 wifi_sas_page=0;wifi_scan_rebuild_page();CHECK(lv_obj_has_flag(wifi_sas_nav_prev,LV_OBJ_FLAG_HIDDEN),"first hides Prev");if(total>ps){lv_obj_t*row=lv_obj_get_child(scan_list,0);lv_event_send(row,LV_EVENT_CLICKED,NULL);CHECK(selected[0],"select first page");wifi_scan_next_page_cb(NULL);CHECK(wifi_sas_page==1,"pagination Next distinct");row=lv_obj_get_child(scan_list,0);lv_event_send(row,LV_EVENT_CLICKED,NULL);CHECK(selected[ps],"select second page absolute index");wifi_scan_prev_page_cb(NULL);row=lv_obj_get_child(scan_list,0);CHECK(lv_obj_has_state(lv_obj_get_user_data(row),LV_STATE_CHECKED),"selection survives pages");lv_event_send(row,LV_EVENT_CLICKED,NULL);CHECK(!selected[0]&&selected[ps],"selection toggles independent across pages");wifi_scan_next_page_cb(NULL);row=lv_obj_get_child(scan_list,0);CHECK(lv_obj_has_state(lv_obj_get_user_data(row),LV_STATE_CHECKED),"second-page selection restored");lv_event_send(row,LV_EVENT_CLICKED,NULL);CHECK(!selected[ps],"second-page deselect");}
 total=0;wifi_scan_rebuild_page();CHECK(wifi_sas_page==0,"empty refresh resets page");total=ps;wifi_scan_rebuild_page();render();CHECK(lv_obj_get_child_cnt(scan_list)==(unsigned)ps,"full page count");CHECK(contained(scan_list,lv_obj_get_child(scan_list,0))&&contained(scan_list,lv_obj_get_child(scan_list,ps-1)),"full page FIRST LAST fit");
 }
 lv_obj_t*atk=floating();render();const char*label=lv_label_get_text(lv_obj_get_child(atk,0));CHECK(!strcmp(label,"ATK"),"floating ATK exact label");int old=attacks;lv_event_send(atk,LV_EVENT_CLICKED,NULL);CHECK(attacks==old+1,"ATK opens attack-selection callback only");
 uint64_t t=ns();for(int i=0;i<30;i++){show_wifi_menu_screen();render();}uint64_t elapsed=ns()-t;printf("COST wifi %dx%d rot%d ns_per_construct_render=%llu lv_live=%zu\n",w,h,rot,(unsigned long long)(elapsed/30),lv_live);
}
dr.hor_res=100;dr.ver_res=100;lv_disp_set_rotation(d,0);lv_disp_drv_update(d,&dr);CHECK(wifi_sas_page_size()==1,"tiny panel page floor");printf("RESULT checks=%d failures=%d\n",checks,failures);return failures?1:0;}
"""
(D/'host.c').write_text(pre+page+'\n'.join(function(n)for n in functions)+floating+post)
(D/'allocator.h').write_text('#include <stddef.h>\nvoid*track_alloc(size_t);void track_free(void*);void*track_realloc(void*,size_t);\n')
flags=['-include',str(D/'allocator.h'),'-std=gnu11','-O2','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=track_alloc','-DLV_MEM_CUSTOM_FREE=track_free','-DLV_MEM_CUSTOM_REALLOC=track_realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-DLV_FONT_MONTSERRAT_16=1','-I'+str(LV)]
assets=[str(p)for p in(R/'ESP32C5').rglob('lab_bg.c') if 'build_'not in str(p)];assert len(assets)==1,assets
cmd=['cc',*flags,str(D/'host.c'),*assets,*[str(p)for p in(LV/'src').rglob('*.c')],'-lm','-o',str(D/'host')]
with(D/'compile.log').open('w')as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
if rc:print((D/'compile.log').read_text()[-10000:]);sys.exit(rc)
with(D/'run.log').open('w')as f:rc=subprocess.run([str(D/'host')],stdout=f,stderr=subprocess.STDOUT).returncode
(D/'provenance.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(S.encode()).hexdigest(),functions=functions,command=cmd,exit_code=rc),indent=2))
print((D/'run.log').read_text());sys.exit(rc)
