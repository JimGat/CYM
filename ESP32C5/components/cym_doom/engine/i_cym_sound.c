/* Native SFX module. Called only by the engine owner. No sample task, no SDL,
 * no synthesizer: -nomusic is retained and music_module is never selected. */
#include "doomfeatures.h"
#include "i_sound.h"
#include "doomgeneric.h"
#include "w_wad.h"
#include "z_zone.h"
#include "doom_mixer.h"
#include "doom_audio.h"
#include <stdio.h>
#include <string.h>
static doom_mixer mixer;
static doom_boolean prefix,ready;
static uint32_t last_ms;
#ifdef ESP_PLATFORM
extern _Noreturn void doom_engine_fail(const char *);
#else
/* Host backend is a PCM sink with counters, not device or speaker evidence. */
unsigned long cym_host_audio_samples,cym_host_audio_nonzero,cym_host_audio_starts;
bool doom_audio_begin(void){return true;}
bool doom_audio_write(const int16_t *p,size_t n){cym_host_audio_samples+=n;for(size_t i=0;i<n;i++)cym_host_audio_nonzero+=p[i]!=0;return true;}
int doom_audio_end(void){return 0;}
#endif
int doom_sound_stop(void){memset(&mixer,0,sizeof(mixer));ready=false;return doom_audio_end();}
static doom_boolean init(doom_boolean p){prefix=p;memset(&mixer,0,sizeof(mixer));ready=doom_audio_begin();last_ms=DG_GetTicksMs();
#ifdef ESP_PLATFORM
 if(!ready)doom_engine_fail("ES8311/I2S audio initialization failed");
#endif
 return ready;}
static void shutdown(void){(void)doom_sound_stop();}
static int lumpnum(sfxinfo_t *s){char name[12];if(s->link)s=s->link;snprintf(name,sizeof(name),"%s%.8s",prefix?"ds":"",s->name);return W_GetNumForName(name);}
static void update(void){if(!ready)return;uint32_t now=DG_GetTicksMs(),ms=now-last_ms;if(!ms)return;last_ms=now;if(ms>50)ms=50;
 int16_t pcm[1103];size_t n=(size_t)ms*22050/1000;doom_mixer_render(&mixer,pcm,n,22050);
 if(!doom_audio_write(pcm,n)){
#ifdef ESP_PLATFORM
  doom_engine_fail("I2S output timeout/fault");
#else
  ready=false;
#endif
 }}
static void params(int c,int v,int sep){(void)sep;doom_mixer_volume(&mixer,c,v);}
static int start(sfxinfo_t *s,int c,int v,int sep){(void)sep;if(!ready||c<0||c>=DOOM_MIX_CHANNELS)return -1;
 int lump=lumpnum(s),length=W_LumpLength(lump);if(length<8||length>1024*1024+8)return -1;
 const uint8_t *p=W_CacheLumpNum(lump,PU_STATIC);doom_sample sample;
 if(!doom_sample_parse(&sample,p,(size_t)length))return -1;
 /* PU_STATIC keeps cache alive until session stop; no foreign worker holds it. */
 if(!doom_mixer_start(&mixer,c,&sample,v))return -1;
#ifndef ESP_PLATFORM
 cym_host_audio_starts++;
#endif
 return c;
}
static void stop(int c){doom_mixer_stop(&mixer,c);}
static doom_boolean playing(int c){return doom_mixer_playing(&mixer,c);}
static snddevice_t devices[]={SNDDEVICE_SB};
sound_module_t DG_sound_module={devices,1,init,shutdown,lumpnum,update,params,start,stop,playing,NULL};
