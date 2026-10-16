"""Native decoder allocation-failure cleanup and RGB565-LE normalization."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class AllocationAndPixels(unittest.TestCase):
 def test_actual_decoder_oom_cleanup_and_rgb565_stride(self):
  b=ROOT/'ESP32C5/components/cym_qr'
  code=r"""
#include <assert.h>
#include <stdlib.h>
#include "cym_qr.h"
void *__real_malloc(size_t);
void *__real_calloc(size_t,size_t);
void __real_free(void*);
static int call,fail,live;
void *__wrap_malloc(size_t n){if(++call==fail)return NULL;void *p=__real_malloc(n);if(p)live++;return p;}
void *__wrap_calloc(size_t n,size_t m){if(++call==fail)return NULL;void *p=__real_calloc(n,m);if(p)live++;return p;}
void __wrap_free(void *p){if(p){assert(live>0);live--;}__real_free(p);}
int main(void){
 for(fail=1;fail<=12;fail++){call=0;assert(live==0);cym_qr_t*q=cym_qr_create(240,320);if(q)cym_qr_destroy(q);assert(live==0);}
 uint8_t rgb[]={0,248,224,7,99,99,31,0,255,255,99,99},gray[4]={0};
 assert(cym_qr_rgb565_gray(rgb,6,gray,2,2)==0);
 assert(gray[0]==(77*255>>8)&&gray[1]==(150*255>>8)&&gray[2]==(29*255>>8)&&gray[3]==255);
 assert(cym_qr_rgb565_gray(rgb,3,gray,2,2)==-1);
 assert(cym_qr_rgb565_gray(NULL,6,gray,2,2)==-1);
 return 0;
}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   subprocess.run(['cc','-std=c11','-O1','-fno-builtin','-I',str(b/'include'),'-I',str(b/'third_party/quirc'),str(p/'test.c'),str(b/'cym_qr.c'),*[str(b/'third_party/quirc'/f) for f in ['quirc.c','decode.c','identify.c','version_db.c']],'-Wl,--wrap=malloc','-Wl,--wrap=calloc','-Wl,--wrap=free','-lm','-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
