#include "doom_mixer.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned le32(const unsigned char *p){return (unsigned)p[0]|(unsigned)p[1]<<8|(unsigned)p[2]<<16|(unsigned)p[3]<<24;}
int main(int argc,char **argv){
 assert(argc==2);
 FILE *f=fopen(argv[1],"rb");assert(f);unsigned char h[12],entry[16];assert(fread(h,1,12,f)==12);
 unsigned count=le32(h+4),dir=le32(h+8),off=0,n=0;
 for(unsigned i=0;i<count;i++){assert(!fseek(f,(long)dir+i*16,SEEK_SET));assert(fread(entry,1,16,f)==16);if(!memcmp(entry+8,"DSPISTOL",8)){off=le32(entry);n=le32(entry+4);break;}}
 assert(n>48);unsigned char *lump=malloc(n);assert(lump);assert(!fseek(f,off,SEEK_SET));assert(fread(lump,1,n,f)==n);fclose(f);
 doom_sample s;assert(doom_sample_parse(&s,lump,n));assert(s.rate>0&&s.count>0);
 doom_mixer m={0};assert(doom_mixer_start(&m,0,&s,127));assert(doom_mixer_playing(&m,0));
 int16_t out[1024];doom_mixer_render(&m,out,1024,22050);unsigned nonzero=0;for(unsigned i=0;i<1024;i++)nonzero+=out[i]!=0;assert(nonzero);
 doom_mixer_volume(&m,0,0);doom_mixer_render(&m,out,32,22050);for(unsigned i=0;i<32;i++)assert(out[i]==0);
 doom_mixer_stop(&m,0);assert(!doom_mixer_playing(&m,0));assert(!doom_mixer_start(&m,8,&s,127));
 for(int i=0;i<8;i++)assert(doom_mixer_start(&m,i,&s,127));
 for(unsigned i=0;i<400;i++)doom_mixer_render(&m,out,1024,22050);
 for(int i=0;i<8;i++)assert(!doom_mixer_playing(&m,i));
 assert(!doom_sample_parse(&s,lump,7));lump[0]=0;assert(!doom_sample_parse(&s,lump,n));
 lump[0]=3;lump[2]=lump[3]=0;assert(!doom_sample_parse(&s,lump,n));
 lump[2]=0x11;lump[3]=0x2b;memset(lump+4,255,4);assert(!doom_sample_parse(&s,lump,n));
 free(lump);puts("MIXER_AUDIO real DSPISTOL, channels/volume/rate/faults OK");return 0;
}
