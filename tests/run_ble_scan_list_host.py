#!/usr/bin/env python3
"""Execute production list invalidation, not a copy of its decision logic."""
from pathlib import Path
import os,re,subprocess
R=Path(__file__).resolve().parents[1];s=(R/'ESP32C5/main/main.c').read_text()
D=Path(os.environ['CYM_TEST_OUT'])/'ble-list';D.mkdir(parents=True,exist_ok=True)
m=re.search(r'static bool bt_sas_list_changed\(void\)\s*\{',s)
if m:
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 helper=s[m.start():i]
else:helper='static bool bt_sas_list_changed(void){return true;}'
pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
static uint32_t s_bt_results_revision,bt_sas_rendered_revision;
static int bt_sas_page,bt_sas_selected_idx=-1,bt_device_count,bt_sas_rendered_page=-1,bt_sas_rendered_selection=-2,bt_sas_rendered_count=-1,bt_sas_rendered_width,bt_sas_rendered_height;
static int width=320,height=240;
static int lv_disp_get_hor_res(void*p){return width;}
static int lv_disp_get_ver_res(void*p){return height;}
"""
post=r"""
int main(void){
 assert(bt_sas_list_changed());assert(!bt_sas_list_changed()&&"unchanged empty countdown must not rebuild rows");
 for(int i=0;i<100;i++)assert(!bt_sas_list_changed());
 bt_device_count=3;s_bt_results_revision++;assert(bt_sas_list_changed());assert(!bt_sas_list_changed());
 s_bt_results_revision++;assert(bt_sas_list_changed()&&"late name on existing record must refresh");
 bt_sas_selected_idx=1;assert(bt_sas_list_changed());assert(!bt_sas_list_changed());
 bt_sas_page=1;assert(bt_sas_list_changed());assert(!bt_sas_list_changed());
 height=320;width=240;assert(bt_sas_list_changed());
 bt_device_count=0;s_bt_results_revision++;assert(bt_sas_list_changed());assert(!bt_sas_list_changed());
 puts("PASS production BLE list invalidation: empty/countdown, records, late names, selection, pages, orientation, reset");}
"""
(D/'host.c').write_text(pre+helper+post)
for psram in [0,1]:
 subprocess.run(['cc','-std=gnu11','-fsanitize=undefined',f'-DCONFIG_BOARD_HAS_PSRAM={psram}',str(D/'host.c'),'-o',str(D/'host')],check=True)
 subprocess.run([str(D/'host')],check=True)
