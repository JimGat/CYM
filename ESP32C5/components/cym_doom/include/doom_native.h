/* Isolated main-owner RGB565 rasterizer. No LVGL, engine pointers, RTOS or ISR.
 * send() returns true ONLY after the complete stripe ceased borrowing pixels.
 * A rejected or partially completed viewport is not a completed presentation.
 */
#ifndef CYM_DOOM_NATIVE_H
#define CYM_DOOM_NATIVE_H
#include "doom_contracts.h"
#include <string.h>
#define DOOM_NATIVE_PERIOD_MS 50u
#define DOOM_NATIVE_PRIORITY 3u
#define DOOM_NATIVE_MAX_PIXELS 2048u
#define DOOM_NATIVE_BLOCK_TICKS 1u
/* One owner serializes this state. Never visible to the DMA ISR. */
typedef struct {
 doom_game_layout layout;
 int native_w,native_h;unsigned rotation;
 uint16_t *buffer;size_t capacity;
 uint16_t sx[480],sy[320];
 uint32_t completed,failed,last_finish_ms;
 bool active,painting,paced;
} doom_native;
typedef bool (*doom_native_send)(void *,doom_rect,const uint16_t *);
typedef bool (*doom_native_poll)(void *);
/* Existing SPI panel adapters consume high RGB565 byte first (both WS
 * profiles configure LV_COLOR_16_SWAP). Engine palette is logical RGB565.
 * This conversion replaces lv_color_make, not an R/B bitfield swap. */
static inline uint16_t doom_native_wire565(uint16_t c){return (uint16_t)((c>>8)|(c<<8));}
static inline bool doom_native_inside(doom_rect r,int x,int y){return x>=r.x&&y>=r.y&&x-r.x<r.w&&y-r.y<r.h;}
static inline bool doom_native_point(const doom_native *n,int x,int y,int *nx,int *ny){
 if(x<0||y<0||x>=n->layout.width||y>=n->layout.height)return false;
 switch(n->rotation){
 case 0:*nx=x;*ny=y;break;
 case 1:*nx=y;*ny=n->native_h-1-x;break;
 case 2:*nx=n->native_w-1-x;*ny=n->native_h-1-y;break;
 case 3:*nx=n->native_w-1-y;*ny=x;break;
 default:return false;
 }
 return *nx>=0&&*ny>=0&&*nx<n->native_w&&*ny<n->native_h;
}
static inline bool doom_native_takeover(doom_native *n,doom_game_layout l,int nw,int nh,unsigned r,uint16_t *buf,size_t cap,bool drained){
 if(!n||!drained||n->painting||n->active||!buf||cap>DOOM_NATIVE_MAX_PIXELS||cap<(size_t)nw||r>3||nw<=0||nh<=0||l.width<=0||l.width>480||l.height<=0||l.height>320||l.frame.w<=0||l.frame.h<=0||l.frame.x<0||l.frame.y<0||l.frame.x+l.frame.w>l.width||l.frame.y+l.frame.h>l.height)return false;
 if((r&1?nh:nw)!=l.width||(r&1?nw:nh)!=l.height)return false;
 memset(n,0,sizeof(*n));n->layout=l;n->native_w=nw;n->native_h=nh;n->rotation=r;n->buffer=buf;n->capacity=cap;n->active=true;
 for(int x=0;x<l.frame.w;x++)n->sx[x]=(uint16_t)(x*320/l.frame.w);
 for(int y=0;y<l.frame.h;y++)n->sy[y]=(uint16_t)(y*200/l.frame.h);
 return true;
}
static inline bool doom_native_release(doom_native *n){if(n->painting)return false;n->active=false;return true;}
static inline bool doom_native_due(const doom_native *n,uint32_t now){return n->active&&!n->painting&&(!n->paced||(uint32_t)(now-n->last_finish_ms)>=DOOM_NATIVE_PERIOD_MS);}
/* Tiny 5x7 fixed raster alphabet. Labels are drawn once, never every frame. */
static inline uint8_t doom_native_glyph(char c,unsigned row){
 static const struct {char c;uint8_t rows[7];} glyphs[]={
 {'F',{31,16,16,30,16,16,16}},{'W',{17,17,17,21,21,21,10}},
 {'D',{30,17,17,17,17,17,30}},{'B',{30,17,17,30,17,17,30}},
 {'A',{14,17,17,31,17,17,17}},{'C',{14,17,16,16,16,17,14}},
 {'K',{17,18,20,24,20,18,17}},{'I',{31,4,4,4,4,4,31}},
 {'R',{30,17,17,30,20,18,17}},{'E',{31,16,16,30,16,16,31}},
 {'U',{17,17,17,17,17,17,14}},{'S',{15,16,16,14,1,1,30}},
 {'M',{17,27,21,21,17,17,17}},{'N',{17,25,25,21,19,19,17}},
 {'O',{14,17,17,17,17,17,14}},{'X',{17,17,10,4,10,17,17}},
 {'T',{31,4,4,4,4,4,4}},{'<',{1,2,4,8,4,2,1}},{'>',{16,8,4,2,4,8,16}},
 {'V',{17,17,17,17,17,10,4}},{'P',{30,17,17,30,16,16,16}},
 {'L',{16,16,16,16,16,16,31}},{'Y',{17,17,10,4,4,4,4}}
 };
 for(unsigned i=0;i<sizeof(glyphs)/sizeof(glyphs[0]);i++)if(glyphs[i].c==c)return glyphs[i].rows[row];
 return 0;
}
static inline const char *doom_native_label(const doom_native *n,unsigned k,int *x,int *y){
 doom_game_layout l=n->layout;const char *text="";int cx=0;
 switch(k){
 case 0:text="<";cx=l.pad.x+9;*y=l.pad.y+l.pad.h/2-7;break;
 case 1:text="FWD";cx=l.pad.x+l.pad.w/2;*y=l.pad.y+8;break;
 case 2:text=">";cx=l.pad.x+l.pad.w-9;*y=l.pad.y+l.pad.h/2-7;break;
 case 3:text="BACK";cx=l.pad.x+l.pad.w/2;*y=l.pad.y+l.pad.h-22;break;
 case 4:text="FIRE";cx=l.fire.x+l.fire.w/2;*y=l.fire.y+l.fire.h/2-7;break;
 case 5:text="USE";cx=l.use.x+l.use.w/2;*y=l.use.y+l.use.h/2-7;break;
 case 6:text="MENU";cx=l.width/6;*y=l.height-21;break;
 case 7:text="OK";cx=l.width/2;*y=l.height-21;break;
 case 8:text="EXIT";cx=l.width*5/6;*y=l.height-21;break;
 case 9:text="NATIVE VIEWPORT";cx=l.frame.x+83;*y=2;break;
 }
 *x=cx-((int)strlen(text)*12-2)/2;return text;
}
static inline bool doom_native_ink(const doom_native *n,unsigned k,int x,int y){
 int bx=0,by=0;const char *s=doom_native_label(n,k,&bx,&by);int dx=x-bx,dy=y-by;
 if(dx<0||dy<0||dy>=14||(size_t)(dx/12)>=strlen(s)||dx%12>=10)return false;
 return (doom_native_glyph(s[dx/12],(unsigned)dy/2)&(1u<<(4-(dx%12)/2)))!=0;
}
static inline unsigned doom_native_label_pixels(const doom_native *n,unsigned k){
 unsigned count=0;for(int y=0;y<n->layout.height;y++)for(int x=0;x<n->layout.width;x++)if(doom_native_ink(n,k,x,y))count++;return count;
}
static inline uint16_t doom_native_static_pixel(const doom_native *n,int x,int y){
 doom_game_layout l=n->layout;uint16_t c=0;
 if(doom_native_inside(l.pad,x,y)||doom_native_inside(l.fire,x,y)||doom_native_inside(l.use,x,y)||y>=l.height-28)c=0x1168;
 for(unsigned k=0;k<10;k++)if(doom_native_ink(n,k,x,y))return 0xd77f;
 return c;
}
static inline bool doom_native_region(doom_native *n,doom_rect logical,const uint8_t *pixels,const uint16_t *palette,doom_native_send send,doom_native_poll poll,void *ctx){
 if(!n->active||n->painting||!send||!poll)return false;
 int a,b,c,d;doom_native_point(n,logical.x,logical.y,&a,&b);doom_native_point(n,logical.x+logical.w-1,logical.y+logical.h-1,&c,&d);
 int x=a<c?a:c,y=b<d?b:d,w=(a<c?c-a:a-c)+1,h=(b<d?d-b:b-d)+1;
 n->painting=true;bool ok=true;
 for(int off=0;off<h;){
  if(!poll(ctx)){ok=false;break;}
  int rows=(int)(n->capacity/(size_t)w);if(rows>h-off)rows=h-off;
  for(int j=0;j<rows;j++)for(int i=0;i<w;i++){
   int lx=0,ly=0;doom_rotate_point(n->native_w,n->native_h,n->rotation,x+i,y+off+j,&lx,&ly);
   n->buffer[j*w+i]=doom_native_wire565(pixels?palette[pixels[n->sy[ly-n->layout.frame.y]*320+n->sx[lx-n->layout.frame.x]]]:doom_native_static_pixel(n,lx,ly));
  }
  if(!send(ctx,(doom_rect){x,y+off,w,rows},n->buffer)){ok=false;break;}
  off+=rows;
 }
 n->painting=false;return ok;
}
static inline bool doom_native_controls(doom_native *n,doom_native_send send,doom_native_poll poll,void *ctx){
 return doom_native_region(n,(doom_rect){0,0,n->layout.width,n->layout.height},NULL,NULL,send,poll,ctx);
}
static inline bool doom_native_viewport(doom_native *n,const uint8_t *pixels,const uint16_t *palette,doom_native_send send,doom_native_poll poll,void *ctx,uint32_t finish_ms){
 if(!pixels||!palette)return false;
 bool ok=doom_native_region(n,n->layout.frame,pixels,palette,send,poll,ctx);
 n->last_finish_ms=finish_ms;n->paced=true;
 if(ok)n->completed++;else n->failed++;
 return ok;
}
#endif
