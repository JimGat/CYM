from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
class Controls(unittest.TestCase):
 def test_real_control_snapshots(self):
  out=ROOT/'.hermes/cycle81';out.mkdir(parents=True,exist_ok=True)
  source=out/'controls.c';source.write_text(r"""
#include "doom_contracts.h"
#include <assert.h>
int main(void){for(int w=320;w<=480;w+=160){int h=w==320?240:320;
 doom_game_layout l=doom_game_layout_make(w,h);assert(l.frame.w*5==l.frame.h*8);
 assert(l.frame.x>=l.pad.x+l.pad.w);assert(l.frame.x+l.frame.w<=l.fire.x);
 assert(l.frame.y+l.frame.h<=h-28);int x[2]={l.pad.x+l.pad.w/2,l.fire.x+10};
 int y[2]={l.pad.y+5,l.fire.y+10};assert(doom_game_touch_keys(l,x,y,2)==(DOOM_KEY_FORWARD|DOOM_KEY_FIRE));
 x[0]=l.pad.x+5;assert(doom_game_touch_keys(l,x,y,2)==(DOOM_KEY_FORWARD|DOOM_KEY_LEFT|DOOM_KEY_FIRE));
 y[0]=l.pad.y+l.pad.h/2;assert(doom_game_touch_keys(l,x,y,1)==DOOM_KEY_LEFT);
 x[0]=l.pad.x+l.pad.w/2;assert(!doom_game_touch_keys(l,x,y,1));
 assert(!doom_game_touch_keys(l,x,y,0));assert(!doom_game_touch_keys(l,0,0,2));
 x[0]=w-1;y[0]=h-1;assert(doom_game_touch_keys(l,x,y,1)==DOOM_KEY_EXIT);
 x[0]=-1;assert(!doom_game_touch_keys(l,x,y,1));
 }assert(!doom_game_layout_make(0,0).frame.w);return 0;}
""")
  exe=out/'controls';r=subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(ROOT/'ESP32C5/components/cym_doom/include'),str(source),str(ROOT/'ESP32C5/components/cym_doom/doom_contracts.c'),'-o',str(exe)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(exe)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
