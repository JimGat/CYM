#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "cym_viewport.h"
int main(void) {
 cym_viewport_t v={512,300,2};uint16_t x,y;
 assert(cym_viewport_touch(&v,0,0,&x,&y) && x==0 && y==0);
 assert(cym_viewport_touch(&v,1023,599,&x,&y) && x==511 && y==299);
 assert(!cym_viewport_touch(&v,1024,0,&x,&y));
 assert(!cym_viewport_touch(&v,0,600,&x,&y));
 for(unsigned yy=0;yy<600;yy++)for(unsigned xx=0;xx<1024;xx++){
 assert(cym_viewport_touch(&v,xx,yy,&x,&y));assert(x==xx/2 && y==yy/2);}
 uint16_t src[]={0xf800,0x07e0,0x001f,0xffff},dst[16]={0};
 cym_viewport_t tiny={2,2,2};assert(cym_viewport_expand_rgb565(&tiny,src,dst));
 for(unsigned yy=0;yy<4;yy++)for(unsigned xx=0;xx<4;xx++)assert(dst[yy*4+xx]==src[(yy/2)*2+xx/2]);
 cym_viewport_t identity={2,2,1};assert(cym_viewport_expand_rgb565(&identity,src,dst));
 for(int i=0;i<4;i++)assert(src[i]==dst[i]);
 cym_viewport_t bad={2,2,0};assert(!cym_viewport_expand_rgb565(&bad,src,dst));
 cym_viewport_t future={2,2,3};uint16_t future_dst[36];assert(cym_viewport_expand_rgb565(&future,src,future_dst));
 for(int yy=0;yy<6;yy++)for(int xx=0;xx<6;xx++)assert(future_dst[yy*6+xx]==src[yy/3*2+xx/3]);
 puts("viewport: 614400 inverse-touch points, RGB primaries, identity, scale3, bounds PASS");return 0;
}
