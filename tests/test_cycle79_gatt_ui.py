from pathlib import Path
import subprocess,unittest
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
HOST=r"""
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "lvgl.h"
/* Result row helper only consumes these completed snapshot fields. */
typedef struct {bool metadata_available;char metadata_fingerprint[65];unsigned metadata_name_source,metadata_fields;} gw_result_t;
#include "gatt_result_ui.h"
static int w,h;static lv_color_t screen[800*480];
static void flush(lv_disp_drv_t*d,const lv_area_t*a,lv_color_t*p){for(int y=a->y1;y<=a->y2;y++)for(int x=a->x1;x<=a->x2;x++){assert(x<w&&y<h);screen[y*w+x]=*p++;}lv_disp_flush_ready(d);}
int main(int argc,char**argv){assert(argc==4);w=atoi(argv[1]);h=atoi(argv[2]);lv_init();static lv_color_t draw[800*16];static lv_disp_draw_buf_t db;lv_disp_draw_buf_init(&db,draw,NULL,w*16);static lv_disp_drv_t d;lv_disp_drv_init(&d);d.hor_res=w;d.ver_res=h;d.draw_buf=&db;d.flush_cb=flush;lv_disp_drv_register(&d);
 for(int style=0;style<2;style++)for(int available=0;available<2;available++){
 lv_obj_t *p=lv_obj_create(lv_scr_act());lv_obj_set_pos(p,0,30);lv_obj_set_size(p,w,h-74);lv_obj_set_style_pad_all(p,6,0);lv_obj_set_style_pad_gap(p,3,0);lv_obj_set_flex_flow(p,LV_FLEX_FLOW_COLUMN);lv_obj_set_scrollbar_mode(p,LV_SCROLLBAR_MODE_AUTO);
 lv_obj_set_style_bg_color(p,lv_color_hex(style?0x101820:0xeeeeee),0);
 gw_result_t r={.metadata_available=available,.metadata_name_source=1,.metadata_fields=1};strcpy(r.metadata_fingerprint,"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef");
 gw_metadata_rows(p,&r,lv_color_hex(style?0xffffff:0x202020));lv_obj_update_layout(p);assert(lv_obj_get_child_cnt(p)==3);
 lv_obj_t *first=lv_obj_get_child(p,0),*last=lv_obj_get_child(p,2);
 assert(strstr(lv_label_get_text(first),available?"0123456789abcdef":"unavailable"));assert(strstr(lv_label_get_text(last),"not identity"));
 for(unsigned i=0;i<3;i++){lv_obj_t*l=lv_obj_get_child(p,i);assert(lv_color_to32(lv_obj_get_style_text_color(l,LV_PART_MAIN))==lv_color_to32(lv_color_hex(style?0xffffff:0x202020)));lv_area_t a;lv_obj_get_coords(l,&a);assert(a.x1>=0&&a.x2<w);assert(lv_label_get_long_mode(l)==LV_LABEL_LONG_WRAP);}
 lv_obj_scroll_to_view(last,LV_ANIM_OFF);lv_obj_update_layout(p);lv_area_t a;lv_obj_get_coords(last,&a);assert(a.y2<h-44);lv_obj_scroll_to_y(p,0,LV_ANIM_OFF);lv_refr_now(NULL);
 if(style==1&&available){FILE*f=fopen(argv[3],"wb");assert(f);fprintf(f,"P6\n%d %d\n255\n",w,h);for(int i=0;i<w*h;i++){lv_color32_t c;c.full=lv_color_to32(screen[i]);unsigned char b[3]={c.ch.red,c.ch.green,c.ch.blue};fwrite(b,1,3,f);}fclose(f);}
 lv_obj_del(p);
 }puts("shared production metadata rows: wrapped/scrollable, both styles, available/absent, mobile bounds PASS");return 0;
}
"""
class GattUI(unittest.TestCase):
 def test_all_screen_sizes_both_styles(self):
  o=ROOT/'.hermes/cycle79/gatt-ui';o.mkdir(parents=True,exist_ok=True);(o/'host.c').write_text(HOST)
  lv=ROOT/'ESP32C5/managed_components/lvgl__lvgl'
  flags=['-std=gnu11','-O1','-g','-DLV_CONF_SKIP=1','-DLV_MEM_CUSTOM=1','-DLV_MEM_CUSTOM_ALLOC=malloc','-DLV_MEM_CUSTOM_FREE=free','-DLV_MEM_CUSTOM_REALLOC=realloc','-DLV_MEM_CUSTOM_INCLUDE="stdlib.h"','-DLV_FONT_MONTSERRAT_12=1','-I'+str(lv),'-I'+str(ROOT/'ESP32C5/main')]
  c=subprocess.run(['cc',*flags,str(o/'host.c'),*[str(p) for p in (lv/'src').rglob('*.c')],'-lm','-o',str(o/'host')],capture_output=True,text=True)
  self.assertEqual(c.returncode,0,c.stderr)
  for w,h in [(240,320),(320,240),(320,480),(480,320),(800,480),(480,800)]:
   ppm=o/f'{w}x{h}.ppm';run=subprocess.run([str(o/'host'),str(w),str(h),str(ppm)],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr)
   Image.open(ppm).save(Path('/home/dev/ws-c5-35-fixes/cycle79')/f'gatt-{w}x{h}.png')
if __name__=='__main__':unittest.main(verbosity=2)
