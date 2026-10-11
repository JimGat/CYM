from pathlib import Path
import subprocess, unittest
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'ESP32C5/components/cym_doom'
class ModeIntent(unittest.TestCase):
 def test_production_fault_recovery(self):
  out=ROOT/'.hermes/doom-prototype/mode-host';out.mkdir(parents=True,exist_ok=True)
  code=r"""
#include "game_mode.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static game_intent stored;
static int present,read_fault,set_fault,erase_fault,commit_fault,sets,erases,commits;
static game_read read_record(void *ctx,game_intent *v){(void)ctx;if(read_fault)return GAME_READ_FAULT;if(!present)return GAME_ABSENT;*v=stored;return GAME_FOUND;}
static bool set_record(void *ctx,const game_intent *v){(void)ctx;sets++;if(set_fault)return false;stored=*v;present=1;return true;}
static bool erase_record(void *ctx){(void)ctx;erases++;if(erase_fault)return false;present=0;return true;}
static bool commit(void *ctx){(void)ctx;commits++;return !commit_fault;}
static game_mode_io io={NULL,read_record,set_record,erase_record,commit};
static void reset(void){present=read_fault=set_fault=erase_fault=commit_fault=sets=erases=commits=0;}
int main(void){
 reset();assert(game_mode_consume(&io,true,true,false)==GAME_NORMAL);assert(!commits&&!erases);
 for(int b=0;b<2;b++)for(int sw=0;sw<2;sw++)for(int boot=0;boot<2;boot++){
  reset();assert(game_mode_record(&io,GAME_DOOM));assert(present);
  assert(game_mode_consume(&io,b,sw,boot)==((b&&sw&&!boot)?GAME_DOOM:GAME_NORMAL));
  assert(!present&&erases==1&&commits==2);assert(game_mode_consume(&io,true,true,false)==GAME_NORMAL);
 }
 reset();assert(!game_mode_record(&io,GAME_ARDUBOY));assert(!sets&&!commits);
 assert(!game_mode_record(&io,(game_mode)255));
 reset();set_fault=1;assert(!game_mode_record(&io,GAME_DOOM));assert(!commits);
 reset();commit_fault=1;assert(!game_mode_record(&io,GAME_DOOM));assert(erases==1);
 reset();assert(game_mode_record(&io,GAME_DOOM));erase_fault=1;assert(game_mode_consume(&io,true,true,false)==GAME_NORMAL);assert(present);erase_fault=0;assert(game_mode_consume(&io,true,false,false)==GAME_NORMAL);assert(!present);
 reset();assert(game_mode_record(&io,GAME_DOOM));commit_fault=1;assert(game_mode_consume(&io,true,true,false)==GAME_NORMAL);
 reset();present=1;read_fault=1;assert(game_mode_consume(&io,true,true,false)==GAME_NORMAL);assert(!present&&commits==1);
 for(unsigned field=0;field<3;field++){
  reset();assert(game_mode_record(&io,GAME_DOOM));((uint32_t*)&stored)[field]^=0x100;
  assert(game_mode_consume(&io,true,true,false)==GAME_NORMAL);assert(!present);
 }
 reset();present=1;stored=(game_intent){0x43594d47,0x00010002,0};stored.check=stored.magic^stored.version_mode^0xa5a55a5a;
 assert(game_mode_consume(&io,true,true,false)==GAME_NORMAL);assert(!present);
 puts("mode intent: reason/board/BOOT, one-shot, corrupt/unknown/disabled, set/erase/commit/read faults PASS");return 0;
}
"""
  (out/'cases.c').write_text(code)
  r=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(COMP/'include'),str(out/'cases.c'),str(COMP/'game_mode.c'),'-o',str(out/'cases')],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  r=subprocess.run([str(out/'cases')],capture_output=True,text=True);(out/'runtime.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
