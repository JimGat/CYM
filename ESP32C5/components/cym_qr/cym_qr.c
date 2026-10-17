#include "cym_qr.h"
#include "cym_qr_zxing.h"
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include "qr_alloc.h"
struct cym_qr {cym_zx_t *decoder;int width,height;};
cym_qr_t *cym_qr_create(int width,int height)
{
    if(width<1||height<1||width>1024||height>1024)return NULL;
    cym_qr_t *q=calloc(1,sizeof(*q));if(!q)return NULL;
    cym_zx_config_t config={1,width,height,1,1,1,1};
    if(cym_zx_create(&config,&q->decoder)!=CYM_ZX_OK){free(q);return NULL;}
    q->width=width;q->height=height;return q;
}
void cym_qr_destroy(cym_qr_t *q)
{
    if(!q)return;
    // Caller owns lifecycle; never free the wrapper if the engine is busy.
    if(cym_zx_destroy(q->decoder)!=CYM_ZX_OK)return;
    memset(q,0,sizeof(*q));free(q);
}
int cym_qr_decode_gray_ex(cym_qr_t *q,const uint8_t *gray,size_t stride,uint8_t *out,size_t cap,cym_qr_stats_t *stats)
{
    cym_qr_stats_t local={0};if(!stats)stats=&local;memset(stats,0,sizeof(*stats));
    if(!q||!gray||!out||cap<CYM_QR_MAX_PAYLOAD||stride<(size_t)q->width||
       stride>INT_MAX||stride>(SIZE_MAX-(size_t)q->width)/(size_t)(q->height>1?q->height-1:1))return -1;
    cym_zx_result_t result;
    cym_zx_status_t rc=cym_zx_decode(q->decoder,gray,(q->height-1)*stride+q->width,q->width,q->height,stride,out,cap,&result);
    stats->engine_status=rc;stats->candidates=result.candidates;
    stats->valid=result.valid;stats->payload_length=result.valid?result.length:0;
    // ZXing supplies returned symbols, not quirc finder/normal/mirror counts.
    return rc==CYM_ZX_OK?(int)result.length:rc==CYM_ZX_NOT_FOUND?0:-1;
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

int cym_qr_decode_gray(cym_qr_t *q,const uint8_t *g,size_t stride,uint8_t *out,size_t cap)
{return cym_qr_decode_gray_ex(q,g,stride,out,cap,NULL);}
const char *cym_qr_error_name(unsigned e)
{
    static const char *names[]={"SUCCESS","INVALID_GRID_SIZE","INVALID_VERSION","FORMAT_ECC","DATA_ECC","UNKNOWN_DATA_TYPE","DATA_OVERFLOW","DATA_UNDERFLOW"};
    return e<CYM_QR_ERROR_COUNT?names[e]:"INVALID_ERROR";
}
