"""Production native presenter, no LVGL renderer or synthetic FPS claim."""
from pathlib import Path
import subprocess, unittest
ROOT=Path(__file__).resolve().parents[1]
HOST=r"""
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "doom_native.h"
static uint16_t screen[480*320],buf[2048],palette[256];
static uint8_t indexed[320*200];
static unsigned sends,polls,fail_at,cancel_at;
static bool send(void *ctx,doom_rect r,const uint16_t *p){
 doom_native *n=ctx;assert(r.w*r.h<=2048);assert(r.x>=0&&r.y>=0&&r.x+r.w<=n->native_w&&r.y+r.h<=n->native_h);
 sends++;if(sends==fail_at)return false;
 for(int y=0;y<r.h;y++)for(int x=0;x<r.w;x++)screen[(r.y+y)*n->native_w+r.x+x]=*p++;
 return true;
}
static bool poll(void *ctx){(void)ctx;return ++polls!=cancel_at;}
int main(void){
 for(unsigned i=0;i<256;i++)palette[i]=(uint16_t)(i*251+7);
 palette[0]=0xf800;palette[1]=0x07e0;palette[2]=0x001f;
 for(unsigned i=0;i<sizeof(indexed);i++)indexed[i]=(uint8_t)(i/320+i%320);
 for(int board=0;board<2;board++)for(unsigned rot=0;rot<4;rot++){
  int w=board?480:320,h=board?320:240;doom_game_layout l=doom_game_layout_make(w,h);
  doom_native n={0};assert(!doom_native_takeover(&n,l,rot&1?h:w,rot&1?w:h,rot,buf,2048,false));
  assert(doom_native_takeover(&n,l,rot&1?h:w,rot&1?w:h,rot,buf,2048,true));
  memset(screen,0,sizeof(screen));sends=polls=fail_at=cancel_at=0;
  assert(doom_native_controls(&n,send,poll,&n));assert(n.completed==0);
  for(unsigned key=0;key<9;key++)assert(doom_native_label_pixels(&n,key)>0);
  assert(doom_native_viewport(&n,indexed,palette,send,poll,&n,100));assert(n.completed==1&&!n.painting);
  for(int y=0;y<l.frame.h;y++)for(int x=0;x<l.frame.w;x++){
   int nx,ny;assert(doom_native_point(&n,l.frame.x+x,l.frame.y+y,&nx,&ny));
   assert(screen[ny*n.native_w+nx]==(uint16_t)((palette[indexed[(y*200/l.frame.h)*320+x*320/l.frame.w]]>>8)|(palette[indexed[(y*200/l.frame.h)*320+x*320/l.frame.w]]<<8)));
  }
  assert(!doom_native_due(&n,149));assert(doom_native_due(&n,150));
  sends=0;fail_at=2;assert(!doom_native_viewport(&n,indexed,palette,send,poll,&n,200));assert(n.completed==1&&!n.painting&&n.failed==1);
  sends=polls=fail_at=0;cancel_at=3;assert(!doom_native_viewport(&n,indexed,palette,send,poll,&n,300));assert(n.completed==1&&!n.painting);
  n.painting=true;assert(!doom_native_release(&n));n.painting=false;assert(doom_native_release(&n));
 }
 puts("production native: RGB565 scaling/all rotations/two geometries/visible controls/cancel/partial failure/completed-only/cadence/takeover ownership PASS");
 return 0;
}
"""
class Native(unittest.TestCase):
 def test_production_presenter(self):
  out=Path('/home/dev/ws-c5-35-fixes/cycle90/host');out.mkdir(parents=True,exist_ok=True)
  (out/'native.c').write_text(HOST)
  hdr=ROOT/'ESP32C5/components/cym_doom/include/doom_native.h'
  self.assertTrue(hdr.exists(),'missing production native isolated presenter')
  r=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(hdr.parent),str(out/'native.c'),str(ROOT/'ESP32C5/components/cym_doom/doom_contracts.c'),'-o',str(out/'native')],capture_output=True,text=True)
  (out/'native-compile.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(out/'native')],capture_output=True,text=True);(out/'native.log').write_text(r.stdout+r.stderr)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
