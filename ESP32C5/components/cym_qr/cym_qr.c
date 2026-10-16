#include "cym_qr.h"
#include "quirc.h"
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include "qr_alloc.h"
struct cym_qr {
    struct quirc *decoder;
    struct quirc_code code;
    struct quirc_data data;
    int width, height;
};
cym_qr_t *cym_qr_create(int width, int height)
{
    if (width < 1 || height < 1 || width > 1024 || height > 1024) return NULL;
    cym_qr_t *q = calloc(1, sizeof(*q));
    if (!q) return NULL;
    q->decoder = quirc_new(); q->width = width; q->height = height;
    if (!q->decoder || quirc_resize(q->decoder,width,height)) { cym_qr_destroy(q); return NULL; }
    return q;
}
void cym_qr_destroy(cym_qr_t *q)
{
    if (!q) return;
    if (q->decoder) quirc_destroy(q->decoder);
    memset(q,0,sizeof(*q)); free(q);
}
int cym_qr_decode_gray(cym_qr_t *q, const uint8_t *gray, size_t stride, uint8_t *out, size_t cap)
{
    if (!q || !gray || !out || cap < CYM_QR_MAX_PAYLOAD || stride < (size_t)q->width) return -1;
    uint8_t *dst = quirc_begin(q->decoder,NULL,NULL);
    for (int y=0; y<q->height; ++y) memcpy(dst+y*q->width,gray+y*stride,q->width);
    quirc_end(q->decoder);
    int best = INT_MAX, len = 0;
    for (int i=0; i<quirc_count(q->decoder); ++i) {
        quirc_extract(q->decoder,i,&q->code);
        quirc_decode_error_t err = quirc_decode(&q->code,&q->data);
        if (err) { quirc_flip(&q->code); err = quirc_decode(&q->code,&q->data); }
        if (err || q->data.payload_len < 0 || (size_t)q->data.payload_len > cap) continue;
        int x=0,y=0;
        for (int j=0;j<4;++j) { x+=q->code.corners[j].x; y+=q->code.corners[j].y; }
        x=x/4-q->width/2; y=y/4-q->height/2;
        int distance=x*x+y*y;
        if (distance < best) { best=distance;len=q->data.payload_len;memcpy(out,q->data.payload,len); }
    }
    return len;
}
int cym_qr_rgb565_gray(const uint8_t *rgb, size_t stride, uint8_t *gray, int w, int h)
{
    if (!rgb || !gray || w<1 || h<1 || w>1024 || h>1024 || stride<(size_t)w*2) return -1;
    for (int y=0;y<h;++y) for (int x=0;x<w;++x) {
        const uint8_t *p=rgb+y*stride+x*2;
        unsigned v=p[0]|((unsigned)p[1]<<8);
        unsigned r=((v>>11)&31)*255/31, g=((v>>5)&63)*255/63, b=(v&31)*255/31;
        gray[y*w+x]=(77*r+150*g+29*b)>>8;
    }
    return 0;
}
