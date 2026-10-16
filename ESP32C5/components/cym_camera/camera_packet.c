#include "cym_camera.h"
#include <string.h>
int cym_camera_unpack_bf3901(const uint8_t *p,size_t len,uint8_t *out,size_t cap)
{
    const uint8_t fh[]={255,255,255,0},lh[]={255,255,255,0x40};
    if(!p||!out||len<4+486*320||cap<240*320*2||memcmp(p,fh,4))return -1;
    /* Validate every header BEFORE exposing any partial/corrupt image. */
    for(unsigned y=0;y<320;y++)if(memcmp(p+4+y*486,lh,4))return -1;
    for(unsigned y=0;y<320;y++)memcpy(out+y*480,p+4+y*486+6,480);
    return 0;
}
