import os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'ESP32C5/components/cym_camera'
class CameraTests(unittest.TestCase):
 def test_real_service_ownership_and_packet_validation(self):
  self.assertTrue((B/'cym_camera.c').exists(),'Camera service missing')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'esp_err.h').write_text('#pragma once\ntypedef int esp_err_t;\n#define ESP_OK 0\n#define ESP_FAIL -1\n#define ESP_ERR_INVALID_STATE 2\n#define ESP_ERR_INVALID_ARG 3\n#define ESP_ERR_NO_MEM 4\n')
   (p/'test.c').write_text(r"""
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "cym_camera.h"
#include "camera_backend.h"
static int fail_open,fail_close,opened,closed,acquires;
static unsigned char rgb[8];
esp_err_t camera_backend_open(void **p,void *bus){(void)bus;if(fail_open)return ESP_FAIL;*p=rgb;opened++;return ESP_OK;}
esp_err_t camera_backend_acquire(void *p,cym_camera_frame_t *f,unsigned timeout){assert(p==rgb&&timeout<=500);acquires++;*f=(cym_camera_frame_t){rgb,2,2,4,CYM_CAMERA_RGB565_LE};return ESP_OK;}
void camera_backend_release(void *p){assert(p==rgb);}
esp_err_t camera_backend_close(void *p){assert(p==rgb);if(fail_close)return ESP_FAIL;closed++;return ESP_OK;}
int main(void){
 cym_camera_t *c=NULL;cym_camera_frame_t f;
 fail_open=1;assert(cym_camera_open(&c,NULL)!=ESP_OK&&c==NULL);fail_open=0;
 assert(cym_camera_open(&c,NULL)==ESP_OK&&c);assert(cym_camera_acquire(c,&f,200)==ESP_OK);
 assert(cym_camera_acquire(c,&f,200)==ESP_ERR_INVALID_STATE);
 assert(cym_camera_close(&c)==ESP_ERR_INVALID_STATE&&c);cym_camera_release(c);
 fail_close=1;assert(cym_camera_close(&c)!=ESP_OK&&c);fail_close=0;assert(cym_camera_close(&c)==ESP_OK&&!c);
 assert(cym_camera_close(&c)==ESP_OK);assert(opened==1&&closed==1&&acquires==1);
 size_t n=4+486*320;unsigned char *packet=calloc(1,n),*out=malloc(240*320*2);
 memset(packet,255,3);packet[3]=0;
 for(int y=0;y<320;y++){size_t o=4+y*486;memset(packet+o,255,3);packet[o+3]=0x40;for(int x=0;x<480;x++)packet[o+6+x]=(unsigned char)(x+y);}
 assert(cym_camera_unpack_bf3901(packet,n,out,153600)==0);assert(out[479]==(unsigned char)479);assert(out[480]==1);
 packet[4]=0;assert(cym_camera_unpack_bf3901(packet,n,out,153600)!=0);
 assert(cym_camera_unpack_bf3901(packet,n-1,out,153600)!=0);free(packet);free(out);return 0;
}
""")
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(p),'-I',str(B/'include'),'-I',str(B),str(p/'test.c'),str(B/'cym_camera.c'),str(B/'camera_packet.c'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
