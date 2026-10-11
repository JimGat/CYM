#include "doom_mixer.h"
#include <string.h>
static uint32_t le32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
/* DMX format 3: little-endian rate/length, unsigned 8-bit PCM, 16 padding
 * samples at each end (as used by the upstream software mixer). Fail closed. */
bool doom_sample_parse(doom_sample *s,const uint8_t *p,size_t n){
 memset(s,0,sizeof(*s));if(!p||n<8||p[0]!=3||p[1]!=0)return false;
 uint32_t rate=(uint32_t)p[2]|(uint32_t)p[3]<<8,len=le32(p+4);
 if(rate<4000||rate>48000||len<=32||len>1024*1024||len>n-8)return false;
 s->data=p+24;s->count=len-32;s->rate=rate;return true;
}
static bool valid(int c){return c>=0&&c<DOOM_MIX_CHANNELS;}
void doom_mixer_volume(doom_mixer *m,int c,int v){if(valid(c))m->channels[c].volume=v<0?0:v>127?127:(unsigned)v;}
void doom_mixer_stop(doom_mixer *m,int c){if(valid(c))memset(&m->channels[c],0,sizeof(m->channels[c]));}
bool doom_mixer_playing(const doom_mixer *m,int c){return valid(c)&&m->channels[c].sample.data!=0;}
bool doom_mixer_start(doom_mixer *m,int c,const doom_sample *s,int v){
 if(!valid(c)||!s||!s->data||!s->count||s->count>1024*1024||s->rate<4000||s->rate>48000)return false;
 m->channels[c].sample=*s;m->channels[c].phase=0;doom_mixer_volume(m,c,v);return true;
}
/* Fixed-point nearest-sample resampling. Eight full-scale channels are mixed
 * in 32 bits, with conservative 1/4 gain and saturation, never integer wrap. */
void doom_mixer_render(doom_mixer *m,int16_t *out,size_t n,uint32_t rate){
 if(!rate){memset(out,0,n*sizeof(*out));return;}
 for(size_t i=0;i<n;i++){int32_t sum=0;
  for(int c=0;c<DOOM_MIX_CHANNELS;c++){doom_mix_channel *ch=&m->channels[c];if(!ch->sample.data)continue;
   size_t at=(size_t)(ch->phase>>16);if(at>=ch->sample.count){doom_mixer_stop(m,c);continue;}
   sum+=((int32_t)ch->sample.data[at]-128)*256*(int32_t)ch->volume/127;
   ch->phase+=((uint64_t)ch->sample.rate<<16)/rate;
   if((ch->phase>>16)>=ch->sample.count)doom_mixer_stop(m,c);
  }
  sum/=4;out[i]=(int16_t)(sum>32767?32767:sum< -32768? -32768:sum);
 }
}
