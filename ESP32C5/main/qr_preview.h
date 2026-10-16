#pragma once
#include <stdint.h>
#include <stddef.h>
/* Persisted index r is LVGL NONE/90/180/270. lv_refr.c maps 90 as
 * (x,y)->(y,W-1-x), i.e. CCW into native display coordinates. Owner confirms
 * raw preview at r=2 aligns with the physical camera. Thus logical preview
 * must be CCW(180-r*90), NOT another copy of global rotation. Composition
 * with LVGL is always 180. No reflection; decoder stays native 240x320. */
static inline void qr_preview_size(int w,int h,unsigned r,int *ow,int *oh)
{*ow=(r&1)?h:w;*oh=(r&1)?w:h;}
/* Fit entire frame, nearest-neighbour downsampling, swapped LVGL RGB565.
 * Caller supplies aspect-preserving dimensions and exclusive output buffer. */
static inline int qr_preview_rgb565(const uint8_t *src,size_t stride,int w,int h,
                                    unsigned r,uint16_t *dst,int ow,int oh)
{
    if(!src||!dst||w<1||h<1||ow<1||oh<1||stride<(size_t)w*2||r>3)return -1;
    int rw,rh;qr_preview_size(w,h,r,&rw,&rh);
    for(int y=0;y<oh;y++)for(int x=0;x<ow;x++){
        int u=x*rw/ow,v=y*rh/oh,sx,sy;
        switch(r){
        case 0:sx=w-1-u;sy=h-1-v;break;
        case 1:sx=w-1-v;sy=u;break;
        case 2:sx=u;sy=v;break;
        default:sx=v;sy=h-1-u;break;
        }
        const uint8_t *p=src+sy*stride+sx*2;
        dst[y*ow+x]=((uint16_t)p[0]<<8)|p[1];
    }
    return 0;
}
