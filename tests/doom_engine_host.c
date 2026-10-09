/* Real-engine headless runner. Freedoom remains external to firmware source. */
#include "doom_session.h"
#include "doom_contracts.h"
#include "doomstat.h"
#include "p_mobj.h"
#include "d_event.h"
#include "info.h"
extern int leveltime;
extern doom_boolean menuactive;
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
void doom_session_test_fail_after(long);
static unsigned frames;
static uint32_t frame_hash;
static int initial_tics,initial_speed;
static void frame(const uint8_t *pixels,void *ctx){(void)ctx;frames++;uint32_t h=2166136261u;for(unsigned i=0;i<320*200;i++)h=(h^pixels[i])*16777619u;frame_hash=h;}
int main(int argc,char **argv){assert(argc==2);assert(sizeof(states)==sizeof(void *));assert(sizeof(mobjinfo)==sizeof(void *));doom_session_set_frame(frame,NULL);for(unsigned run=0;run<3;run++){frames=0;int rc=doom_session_start(argv[1]);if(rc){printf("REAL_ENGINE_INIT_REFUSED run=%u rc=%d error=%s\n",run,rc,doom_session_error());doom_session_stop();assert(doom_session_owned()==0);return 3;}if(run==0){initial_tics=states[S_PLAY].tics;initial_speed=mobjinfo[MT_BRUISERSHOT].speed;}else{assert(states[S_PLAY].tics==initial_tics);assert(mobjinfo[MT_BRUISERSHOT].speed==initial_speed);}
for(unsigned tick=0;tick<70;tick++){if(doom_session_tick()){printf("REAL_ENGINE_TICK_FAULT run=%u tick=%u error=%s\n",run,tick,doom_session_error());doom_session_stop();assert(doom_session_owned()==0);return 4;}}assert(frames>0);assert(gamestate==GS_LEVEL);assert(players[consoleplayer].mo);assert(leveltime>0);
int before_time=leveltime;fixed_t before_x=players[consoleplayer].mo->x,before_y=players[consoleplayer].mo->y;
doom_session_set_keys(DOOM_KEY_FORWARD);for(unsigned k=0;k<35;k++)assert(doom_session_tick()==0);doom_session_set_keys(0);assert(doom_session_tick()==0);
assert(leveltime>before_time);assert(players[consoleplayer].mo->x!=before_x||players[consoleplayer].mo->y!=before_y);
int before_ammo=players[consoleplayer].ammo[am_clip];doom_session_set_keys(DOOM_KEY_FIRE);for(unsigned k=0;k<35;k++)assert(doom_session_tick()==0);doom_session_set_keys(0);assert(doom_session_tick()==0);assert(players[consoleplayer].ammo[am_clip]<before_ammo);int after_fire_ammo=players[consoleplayer].ammo[am_clip];
doom_session_set_keys(DOOM_KEY_MENU);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);doom_session_set_keys(0);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);assert(menuactive);
doom_session_set_keys(DOOM_KEY_MENU);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);doom_session_set_keys(0);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);assert(!menuactive);
doom_session_set_keys(DOOM_KEY_USE);for(unsigned k=0;k<8;k++)assert(doom_session_tick()==0);assert(players[consoleplayer].cmd.buttons&BT_USE);doom_session_set_keys(0);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);
angle_t angle_before=players[consoleplayer].mo->angle;doom_session_set_keys(DOOM_KEY_RIGHT);for(unsigned k=0;k<12;k++)assert(doom_session_tick()==0);doom_session_set_keys(0);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);assert(players[consoleplayer].mo->angle!=angle_before);assert(players[consoleplayer].cmd.forwardmove==0);assert(players[consoleplayer].cmd.angleturn==0);
doom_session_set_keys(DOOM_KEY_MENU);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);doom_session_set_keys(0);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);assert(menuactive);
/* Enter traverses actual New Game, Episode and Skill menus, not title-only input. */
for(unsigned choice=0;choice<3;choice++){doom_session_set_keys(DOOM_KEY_CONFIRM);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);doom_session_set_keys(0);for(unsigned k=0;k<4;k++)assert(doom_session_tick()==0);}assert(!menuactive);assert(gamestate==GS_LEVEL);assert(leveltime>0);
puts("REAL_ENGINE_USE_TURN_CONFIRM key_release=PASS");
printf("REAL_ENGINE_GAMEPLAY run=%u leveltime=%d movement=PASS fire_ammo=%d->%d menu=PASS\n",run,leveltime,before_ammo,after_fire_ammo);
printf("REAL_ENGINE_PLAY run=%u warmup_ticks=70 frames=%u frame_fnv32=%08x state_bytes=%zu owned=%zu\n",run,frames,frame_hash,doom_session_state_bytes(),doom_session_owned());states[S_PLAY].tics=999;mobjinfo[MT_BRUISERSHOT].speed=999;doom_session_stop();assert(states==NULL);assert(mobjinfo==NULL);assert(doom_session_owned()==0);printf("REAL_ENGINE_CLEAN run=%u owned=0\n",run);}int rc=doom_session_start("/missing/doom1.wad");assert(rc!=0);doom_session_stop();assert(doom_session_owned()==0);printf("REAL_ENGINE_MISSING_WAD_RECOVERED %s\n",doom_session_error());rc=doom_session_start(argv[1]);assert(rc==0);assert(doom_session_tick()==0);doom_session_stop();assert(doom_session_owned()==0);doom_session_test_fail_after(-1);
for(long fail=0;fail<24;fail++){doom_session_test_fail_after(fail);int init=doom_session_start(argv[1]);if(init==0)doom_session_tick();assert(doom_session_stop()==0);assert(doom_session_owned()==0);printf("REAL_ENGINE_ALLOC_RECOVERY injection=%ld owned=0\n",fail);}
doom_session_test_fail_after(-1);assert(doom_session_start(argv[1])==0);doom_session_request_stop();assert(doom_session_tick()!=0);assert(doom_session_stop()==0);assert(doom_session_owned()==0);puts("REAL_ENGINE_CANCEL_RECOVERED owned=0");
assert(doom_session_start(argv[1])==0);assert(doom_session_tick()==0);assert(doom_session_stop()==0);
puts("REAL_ENGINE_GATE PASS: three reopen cycles, missing-file recovery, 24 allocation boundaries, cancel/reopen; host only");return 0;}
