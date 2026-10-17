"""Link-injected POSIX failures against authentic production record writer."""
from pathlib import Path
import ctypes as C,os,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class RecordFaults(unittest.TestCase):
 def test_write_close_full_readonly_short_and_interrupted(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=ROOT/'ESP32C5/components/cym_qr'
   (p/'faults.c').write_text(r"""
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
static int mode,calls;
void faults(int m){mode=m;calls=0;}
ssize_t __real_write(int,const void*,size_t);
int __real_close(int);
int __real_open(const char*,int,...);
ssize_t __wrap_write(int fd,const void *s,size_t n){
 if(mode==1 && ++calls>2){errno=ENOSPC;return -1;}
 if(mode==4 && ++calls==1){errno=EINTR;return -1;}
 if(mode==4 && n>2)n=2;
 return __real_write(fd,s,n);
}
int __wrap_close(int fd){int e=__real_close(fd);if(mode==2){errno=EIO;return -1;}return e;}
int __wrap_open(const char *p,int f,...){va_list a;va_start(a,f);int m=va_arg(a,int);va_end(a);if(mode==3){errno=EROFS;return -1;}return __real_open(p,f,m);}
""")
   so=p/'faults.so'
   subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror','-I',str(src/'include'),str(src/'qr_record.c'),str(p/'faults.c'),'-Wl,--wrap=write','-Wl,--wrap=close','-Wl,--wrap=open','-o',str(so)],check=True)
   lib=C.CDLL(str(so));lib.cym_qr_record.argtypes=[C.c_char_p,C.c_void_p,C.c_size_t,C.c_char_p,C.c_longlong,C.c_ulonglong,C.c_void_p,C.c_size_t]
   for mode in [1,2,3,4]:
    card=p/str(mode);card.mkdir();out=C.create_string_buffer(80);lib.faults(mode)
    code=lib.cym_qr_record(os.fsencode(card),b'binary\0payload',14,b'v3.0.8',0,123,out,len(out))
    if mode==4:self.assertEqual(code,0);self.assertTrue(out.value)
    else:self.assertNotEqual(code,0);self.assertEqual(out.value,b'');self.assertEqual(list((card/'lab/QR').iterdir()),[])
   lib.cym_qr_debug_frame.argtypes=[C.c_char_p,C.c_void_p,C.c_int,C.c_int,C.c_size_t,C.c_char_p,C.c_void_p,C.c_size_t]
   for mode in [1,2,3,4]:
    card=p/('frame'+str(mode));card.mkdir();out=C.create_string_buffer(80);lib.faults(mode)
    code=lib.cym_qr_debug_frame(os.fsencode(card),bytes(range(16)),4,4,4,b'rotation=180',out,len(out))
    if mode==4:self.assertEqual(code,0);self.assertTrue(out.value)
    else:self.assertNotEqual(code,0);self.assertEqual(out.value,b'');self.assertEqual(list((card/'lab/QR/debug').iterdir()),[])
   lib.cym_qr_debug_pair.argtypes=[C.c_char_p,C.c_void_p,C.c_void_p,C.c_int,C.c_int,C.c_size_t,C.c_size_t,C.c_char_p,C.c_void_p,C.c_size_t]
   for mode in [1,2,3,4]:
    card=p/('pair'+str(mode));card.mkdir();out=C.create_string_buffer(80);lib.faults(mode)
    code=lib.cym_qr_debug_pair(os.fsencode(card),bytes(range(16)),bytes(range(32)),4,4,4,8,b'frame_id=3',out,len(out))
    if mode==4:
     self.assertEqual(code,0);self.assertTrue(out.value);self.assertEqual((card/'lab/QR/debug/frame-0000.rgb565').read_bytes(),bytes(range(32)))
    else:self.assertNotEqual(code,0);self.assertEqual(out.value,b'');self.assertEqual(list((card/'lab/QR/debug').iterdir()),[])
if __name__=='__main__':unittest.main()
