"""Decode actual generated public QR images through the production quirc adapter."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest
import qrcode
from PIL import Image, ImageOps
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'ESP32C5/components/cym_qr'
class DecoderTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  assert (BASE/'cym_qr.c').exists(),'QR adapter implementation missing'
  cls.tmp=tempfile.TemporaryDirectory()
  lib=Path(cls.tmp.name)/'decoder.so'
  subprocess.run(['cc','-shared','-fPIC','-std=c11','-O2','-Wall','-Wextra','-I',str(BASE/'include'),'-I',str(BASE/'third_party/quirc'),str(BASE/'cym_qr.c'),*[str(BASE/'third_party/quirc'/f) for f in ['quirc.c','decode.c','identify.c','version_db.c']],'-lm','-o',str(lib)],check=True)
  cls.lib=C.CDLL(str(lib))
  cls.lib.cym_qr_create.argtypes=[C.c_int,C.c_int];cls.lib.cym_qr_create.restype=C.c_void_p
  cls.lib.cym_qr_destroy.argtypes=[C.c_void_p]
  cls.lib.cym_qr_decode_gray.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t]
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def decode(self,image):
  image=image.convert('L');w,h=image.size
  ctx=self.lib.cym_qr_create(w,h);self.assertTrue(ctx)
  out=C.create_string_buffer(8896)
  try:
   n=self.lib.cym_qr_decode_gray(ctx,image.tobytes(),w,out,len(out))
   return n,out.raw[:max(0,n)]
  finally:self.lib.cym_qr_destroy(ctx)
 def image(self,data):return qrcode.make(data,box_size=4,border=4).convert('L')
 def test_url_text_binary_long_and_rotations(self):
  for data in [b'https://example.com/qr',b'Plain text\nline two',b'12345678901234567890',b'HELLO WORLD',b'A\0\xffB',b'Long text '*60]:
   for angle in [0,90,180,270]:
    n,out=self.decode(self.image(data).rotate(angle,expand=True));self.assertEqual(n,len(data));self.assertEqual(out,data)
 def test_dense_1200_byte_limitation_never_returns_wrong_payload(self):
  data=b'Long text '*120
  for angle in [0,90,180,270]:
   n,out=self.decode(self.image(data).rotate(angle,expand=True))
   self.assertIn(n,[0,len(data)])
   if n:self.assertEqual(out,data)
 def test_mirror(self):
  data=b'Mirror fixture';self.assertEqual(self.decode(ImageOps.mirror(self.image(data)))[1],data)
 def test_no_code_and_malformed(self):
  self.assertEqual(self.decode(Image.new('L',(240,320),255))[0],0)
  self.assertEqual(self.decode(Image.effect_noise((240,320),100))[0],0)
 def test_dimensions_and_stride(self):
  self.assertFalse(self.lib.cym_qr_create(-1,320));self.assertFalse(self.lib.cym_qr_create(100000,100000))
  ctx=self.lib.cym_qr_create(240,320)
  try:self.assertEqual(self.lib.cym_qr_decode_gray(ctx,b'X',1,None,0),-1)
  finally:self.lib.cym_qr_destroy(ctx)
 def test_multicode_nearest_center(self):
  canvas=Image.new('L',(640,480),255)
  canvas.paste(self.image(b'edge'),(0,0));center=self.image(b'center');canvas.paste(center,(320-center.width//2,240-center.height//2))
  self.assertEqual(self.decode(canvas)[1],b'center')
if __name__=='__main__':unittest.main()
