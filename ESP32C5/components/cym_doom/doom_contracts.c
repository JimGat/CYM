/* Portable production helper implementation. Hardware adapters must provide
 * serialization and worker join; these helpers deliberately own neither.
 */
#include "doom_contracts.h"
#include <string.h>
static uint32_t le32(const unsigned char *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static bool name_is(const unsigned char *p,const char *name){unsigned char n[8]={0};size_t len=strlen(name);if(len>8)return false;memcpy(n,name,len);return memcmp(p,n,8)==0;}
/* Use uint64 arithmetic before multiplication/subtraction. Read one 16-byte
 * directory entry at a time, cap count and file size to engine signed limits.
 * Zero-size marker entries are legitimate. Doom II/Hexen/mod PWADs are refused.
 */
doom_wad_result doom_wad_validate(doom_read_at read,void *ctx,uint64_t size){
    unsigned char h[12],e[16];
    if(!read||size<12||size>INT32_MAX)return DOOM_WAD_BOUNDS;
    if(!read(ctx,0,h,sizeof(h)))return DOOM_WAD_IO;
    if(memcmp(h,"IWAD",4))return DOOM_WAD_UNSUPPORTED;
    uint32_t count=le32(h+4),table=le32(h+8);
    if(count==0||count>16384||table<12||table>size||(uint64_t)count*16>size-table)return DOOM_WAD_BOUNDS;
    unsigned resources=0;int map_next=-1;
    static const char *map_names[]={"THINGS","LINEDEFS","SIDEDEFS","VERTEXES","SEGS","SSECTORS","NODES","SECTORS","REJECT","BLOCKMAP"};
    static const unsigned map_units[]={10,14,30,4,12,4,28,26,1,2};
    for(uint32_t i=0;i<count;i++){
        if(!read(ctx,(uint64_t)table+(uint64_t)i*16,e,sizeof(e)))return DOOM_WAD_IO;
        uint32_t pos=le32(e),len=le32(e+4);
        if(pos>size||len>size-pos||len>INT32_MAX)return DOOM_WAD_BOUNDS;
        if(name_is(e+8,"MAP01")||name_is(e+8,"BEHAVIOR")||name_is(e+8,"IMPXA1")||name_is(e+8,"ETTNA1"))return DOOM_WAD_UNSUPPORTED;
        if(name_is(e+8,"PLAYPAL")){if(len<768)return DOOM_WAD_RESOURCES;resources|=1;}
        if(name_is(e+8,"COLORMAP")){if(len<8192)return DOOM_WAD_RESOURCES;resources|=2;}
        if(name_is(e+8,"PNAMES")){if(len<4)return DOOM_WAD_RESOURCES;resources|=4;}
        if(name_is(e+8,"TEXTURE1")){if(len<4)return DOOM_WAD_RESOURCES;resources|=8;}
        if(name_is(e+8,"POSSA1")){if(len<8)return DOOM_WAD_RESOURCES;resources|=16;}
        if(map_next>=0){
            if(!name_is(e+8,map_names[map_next])||len==0||len%map_units[map_next])return DOOM_WAD_RESOURCES;
            if(map_next==9){if(len<8)return DOOM_WAD_RESOURCES;map_next=-1;resources|=32;}else map_next++;
        }else if(name_is(e+8,"E1M1")){map_next=0;}
    }
    if(map_next>=0||resources!=63)return DOOM_WAD_RESOURCES;
    return DOOM_WAD_OK;
}
void doom_trigger_reset(doom_trigger *t){memset(t,0,sizeof(*t));}
/* Count only complete press/release pairs inside the same target. Unsigned
 * elapsed subtraction supports monotonic timer rollover, not backwards clocks.
 */
bool doom_trigger_update(doom_trigger *t,uint32_t now,bool down,bool target,bool allowed){
    if(!target||!allowed){doom_trigger_reset(t);return false;}
    if(t->count&&(uint32_t)(now-t->first_ms)>6000){t->count=0;t->down=false;}
    if(down){if(!t->down&&t->count==0)t->first_ms=now;t->down=true;return false;}
    if(!t->down)return false;
    t->down=false;
    if((uint32_t)(now-t->first_ms)>6000){t->count=0;return false;}
    if(++t->count==8){doom_trigger_reset(t);return true;}
    return false;
}
/* Fit the original 320x200 aspect in the available surface, centered. Reject
 * unbounded dimensions so signed pixel arithmetic is deterministic on host/IDF.
 */
doom_rect doom_scale_fit(int w,int h){doom_rect r={0};if(w<=0||h<=0||w>4096||h>4096)return r;if(w*5<=h*8){r.w=w;r.h=w*5/8;}else{r.h=h;r.w=h*8/5;}r.x=(w-r.w)/2;r.y=(h-r.h)/2;return r;}
bool doom_scale_point(doom_rect r,int x,int y,int *sx,int *sy){if(!sx||!sy||r.w<=0||r.h<=0||r.w>4096||r.h>4096||x<r.x||y<r.y||x-r.x>=r.w||y-r.y>=r.h)return false;*sx=(x-r.x)*320/r.w;*sy=(y-r.y)*200/r.h;return true;}
bool doom_rotate_point(int w,int h,unsigned rot,int x,int y,int *lx,int *ly){if(!lx||!ly||w<=0||h<=0||rot>3||x<0||y<0||x>=w||y>=h)return false;switch(rot){case 1:*lx=h-y-1;*ly=x;break;case 2:*lx=w-x-1;*ly=h-y-1;break;case 3:*lx=y;*ly=w-x-1;break;default:*lx=x;*ly=y;}return true;}
void doom_keys_set(doom_keys *k,unsigned desired){k->desired=desired&((1u<<9)-1);}
/* A desired-state snapshot cannot overflow an event queue. Reconcile releases
 * before new presses, including all releases after touch loss or cancel.
 */
bool doom_keys_next(doom_keys *k,unsigned *key,bool *pressed){unsigned diff=k->delivered&~k->desired;bool p=false;if(!diff){diff=k->desired&~k->delivered;p=true;}if(!diff||!key||!pressed)return false;unsigned bit=diff&(~diff+1u);if(p)k->delivered|=bit;else k->delivered&=~bit;*key=bit;*pressed=p;return true;}
/* Bottom 3x3 touch grid: left/forward/right, back/fire/use, menu/confirm/Exit.
 * Works in logical LVGL coordinates AFTER HAL rotation. A single touch is one
 * held action; no external keyboard, IMU or multitouch assumptions.
 */
unsigned doom_touch_keys(int w,int h,int x,int y,bool down){static const unsigned keys[]={DOOM_KEY_LEFT,DOOM_KEY_FORWARD,DOOM_KEY_RIGHT,DOOM_KEY_BACK,DOOM_KEY_FIRE,DOOM_KEY_USE,DOOM_KEY_MENU,DOOM_KEY_CONFIRM,DOOM_KEY_EXIT};if(!down||w<3||h<90||w>4096||h>4096||x<0||y<h-90||x>=w||y>=h)return 0;unsigned col=(unsigned)(x*3/w),row=(unsigned)((y-(h-90))/30);return keys[row*3+col];}
bool doom_lifecycle_begin(doom_lifecycle *l){if(l->phase!=DOOM_IDLE||l->owned_count)return false;l->phase=DOOM_STARTING;l->worker_done=false;if(++l->generation==0)++l->generation;return true;}
bool doom_lifecycle_own(doom_lifecycle *l,doom_cleanup_fn fn,void *ptr){if(!fn||l->worker_done||l->phase!=DOOM_STARTING||l->owned_count==DOOM_OWNERS_MAX)return false;l->owned[l->owned_count].fn=fn;l->owned[l->owned_count++].ptr=ptr;return true;}
bool doom_lifecycle_running(doom_lifecycle *l){if(l->phase!=DOOM_STARTING||l->worker_done)return false;l->phase=DOOM_RUNNING;return true;}
void doom_lifecycle_stop(doom_lifecycle *l){if(l->phase!=DOOM_IDLE)l->phase=DOOM_STOPPING;}
void doom_lifecycle_fail(doom_lifecycle *l){if(l->phase!=DOOM_IDLE)l->phase=DOOM_FAILED;}
void doom_lifecycle_worker_done(doom_lifecycle *l){l->worker_done=true;}
bool doom_lifecycle_joined(const doom_lifecycle *l){return l->worker_done;}
void doom_lifecycle_cleanup(doom_lifecycle *l){if(!l->worker_done)return;while(l->owned_count){unsigned i=--l->owned_count;doom_cleanup_fn fn=l->owned[i].fn;void *ptr=l->owned[i].ptr;l->owned[i].fn=NULL;l->owned[i].ptr=NULL;fn(ptr);}l->phase=DOOM_IDLE;}
bool doom_lifecycle_callback_valid(const doom_lifecycle *l,uint32_t generation){return generation!=0&&generation==l->generation&&!l->worker_done&&(l->phase==DOOM_STARTING||l->phase==DOOM_RUNNING);}
bool doom_gate_ready(doom_gate g){return g.supported&&g.idle&&g.sd_ready&&g.licensed&&g.assets_valid&&g.psram_largest>=6u*1024*1024&&g.psram_free>=13u*512*1024;}

/* Match the SHA256 of the official private host fixture, not its filename. */
bool doom_wad_trusted_hash(const uint8_t hash[32]){static const uint8_t trusted[32]={0x73,0x23,0xbc,0xc1,0x68,0xc5,0xa4,0x5f,0xf1,0x07,0x49,0xb3,0x39,0x96,0x0e,0x98,0x31,0x47,0x40,0xa7,0x34,0xc3,0x0d,0x4b,0x9f,0x33,0x37,0x00,0x1f,0x9e,0x70,0x3d};return hash&&memcmp(hash,trusted,sizeof(trusted))==0;}
