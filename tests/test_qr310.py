"""Production asymmetric preview and explicit capture API regression."""
from pathlib import Path
import subprocess,tempfile,unittest,ctypes as C
ROOT=Path(__file__).resolve().parents[1]
class Preview310(unittest.TestCase):
 def test_all_rotations(self):
  source=r'''#include <assert.h>
#include "qr_preview.h"
int main(void){
 uint8_t rgb[48];uint16_t out[24];
 for(int i=0;i<24;i++){rgb[2*i]=i+1;rgb[2*i+1]=128+i;}
 for(unsigned r=0;r<4;r++){
  int w,h;qr_preview_size(4,6,r,&w,&h);
  assert(w==((r&1)?6:4)&&h==((r&1)?4:6));
  assert(!qr_preview_rgb565(rgb,8,4,6,r,out,w,h));
  for(int y=0;y<6;y++)for(int x=0;x<4;x++){
   int dx=r==0?3-x:r==1?y:r==2?x:5-y;
   int dy=r==0?5-y:r==1?3-x:r==2?y:x;
   int i=y*4+x;assert(out[dy*w+dx]==(((i+1)<<8)|(128+i)));
  }
 }
 assert(qr_preview_rgb565(rgb,7,4,6,0,out,4,6)==-1);return 0;
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(source)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'ESP32C5/main'),str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)
class Frame310(unittest.TestCase):
 def test_exact_stride_collision_missing_and_invalid(self):
  b=ROOT/'ESP32C5/components/cym_qr'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);lib=p/'record.so'
   subprocess.run(['cc','-shared','-fPIC','-I',str(b/'include'),str(b/'qr_record.c'),'-o',str(lib)],check=True)
   fn=C.CDLL(str(lib)).cym_qr_debug_frame
   fn.argtypes=[C.c_char_p,C.c_void_p,C.c_int,C.c_int,C.c_size_t,C.c_char_p,C.c_void_p,C.c_size_t]
   name=C.create_string_buffer(64);data=bytes([1,2,99,3,4,99]);root=str(p).encode()
   self.assertNotEqual(fn(str(p/'missing').encode(),data,2,2,3,b'rotation=2',name,64),0);self.assertFalse((p/'missing').exists())
   names=[]
   for _ in range(2):
    self.assertEqual(fn(root,data,2,2,3,b'rotation=2',name,64),0);names.append(name.value)
    f=p/'lab/QR/debug'/name.value.decode();self.assertEqual(f.read_bytes(),b'P5\n# rotation=2\n2 2\n255\n'+bytes([1,2,3,4]))
   self.assertNotEqual(*names);self.assertNotEqual(fn(root,data,2,2,1,b'bad',name,64),0)

class Recognition310(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from test_qr_decoder_contract import DecoderTests
  cls.base=DecoderTests;cls.base.setUpClass();cls.lib=cls.base.lib
  cls.lib.cym_qr_rgb565_gray.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_int,C.c_int]
  class Stats(C.Structure):
   _fields_=[(x,C.c_uint32) for x in ['candidates','normal_attempts','mirror_attempts','valid','payload_length']]+[('errors',C.c_uint32*8)]
  cls.Stats=Stats;cls.lib.cym_qr_decode_gray_ex.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.POINTER(Stats)]
 @classmethod
 def tearDownClass(cls):cls.base.tearDownClass()
 def decode(self,image,padding=0,rgb=False):
  w,h=image.size;gray=image.convert('L').tobytes();stride=w+padding
  if rgb:
   raw=bytearray()
   for y in range(h):
    for x in range(w):
     v=gray[y*w+x];p=((v>>3)<<11)|((v>>2)<<5)|(v>>3);raw.extend([p&255,p>>8])
    raw.extend(bytes(padding))
   outgray=C.create_string_buffer(w*h)
   self.assertEqual(self.lib.cym_qr_rgb565_gray(bytes(raw),w*2+padding,outgray,w,h),0)
   gray=outgray.raw;stride=w
  else:gray=b''.join(gray[y*w:(y+1)*w]+bytes(padding) for y in range(h))
  ctx=self.lib.cym_qr_create(w,h);out=C.create_string_buffer(8896);stats=self.Stats()
  try:
   n=self.lib.cym_qr_decode_gray_ex(ctx,gray,stride,out,8896,C.byref(stats))
   self.assertEqual(sum(stats.errors),stats.normal_attempts+stats.mirror_attempts)
   self.assertEqual(stats.payload_length,max(0,n));return n,out.raw[:max(0,n)],stats
  finally:self.lib.cym_qr_destroy(ctx)
 def test_native_camera_sized_versions_ecc_rotation_mirror_stride_rgb(self):
  import qrcode
  from PIL import Image,ImageOps,ImageFilter
  rows=[]
  for version in [1,2,4,6,10]:
   for ecc in [qrcode.constants.ERROR_CORRECT_L,qrcode.constants.ERROR_CORRECT_M,qrcode.constants.ERROR_CORRECT_Q,qrcode.constants.ERROR_CORRECT_H]:
    payload=b'CYM310';qr=qrcode.QRCode(version=version,error_correction=ecc,box_size=3,border=4);qr.add_data(payload);qr.make(fit=False)
    tile=qr.make_image().convert('L');canvas=Image.new('L',(240,320),255);canvas.paste(tile,((240-tile.width)//2,(320-tile.height)//2))
    for angle in [0,90,180,270]:
     im=canvas.rotate(angle,expand=True)
     for mirrored in [False,True]:
      test=ImageOps.mirror(im) if mirrored else im
      for rgb in [False,True]:
       n,out,stats=self.decode(test,8,rgb)
       rows.append(dict(version=version,ecc=ecc,angle=angle,mirror=mirrored,rgb=rgb,n=n,candidates=stats.candidates,errors=list(stats.errors)))
       self.assertEqual(out,payload,(version,ecc,angle,mirrored,rgb,list(stats.errors)))
  (Path(__import__('os').environ.get('CYM_QR_EVIDENCE_DIR',tempfile.gettempdir()))/'recognition-matrix.json').write_text(__import__('json').dumps(rows,indent=2))
 def test_moderate_blur_contrast_scale_and_no_code(self):
  import qrcode
  from PIL import Image,ImageEnhance,ImageFilter
  im=qrcode.make(b'https://example.com/cym-test',box_size=5,border=4).convert('L')
  for scale in [0.8,1.0,1.2]:
   tile=im.resize((int(im.width*scale),int(im.height*scale)))
   for radius in [0,0.4,0.7]:
    image=ImageEnhance.Contrast(tile.filter(ImageFilter.GaussianBlur(radius))).enhance(0.65)
    self.assertEqual(self.decode(image,7,True)[1],b'https://example.com/cym-test')
  n,out,stats=self.decode(Image.new('L',(240,320),255));self.assertEqual(n,0);self.assertFalse(stats.valid);self.assertEqual(stats.candidates,0)
 def test_empty_is_valid_and_dense_limitation_reported(self):
  import qrcode,json
  im=qrcode.make(b'',box_size=4,border=4).convert('L');n,out,stats=self.decode(im)
  self.assertEqual(n,0);self.assertTrue(stats.valid);self.assertEqual(stats.errors[0],1)
  data=b'Long text '*120;qr=qrcode.QRCode(box_size=4,border=4);qr.add_data(data);qr.make();im=qr.make_image().convert('L')
  rows=[]
  for angle in [0,90,180,270]:
   n,out,stats=self.decode(im.rotate(angle,expand=True))
   self.assertIn(n,[0,len(data)])
   if n:self.assertEqual(out,data)
   rows.append(dict(version=qr.version,size=im.size,angle=angle,n=n,valid=stats.valid,candidates=stats.candidates,errors=list(stats.errors)))
  (Path(__import__('os').environ.get('CYM_QR_EVIDENCE_DIR',tempfile.gettempdir()))/'dense-limitation.json').write_text(json.dumps(rows,indent=2))

class PacketPipeline310(unittest.TestCase):
 setUpClass=classmethod(Recognition310.setUpClass.__func__)
 tearDownClass=classmethod(Recognition310.tearDownClass.__func__)
 decode=Recognition310.decode
 def test_packet_to_payload_and_truncated_rejection(self):
  import qrcode
  from PIL import Image
  camera=ROOT/'ESP32C5/components/cym_camera'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'esp_err.h').write_text('typedef int esp_err_t;\n')
   subprocess.run(['cc','-shared','-fPIC','-I',str(p),'-I',str(camera/'include'),str(camera/'camera_packet.c'),'-o',str(p/'packet.so')],check=True)
   unpack=C.CDLL(str(p/'packet.so')).cym_camera_unpack_bf3901;unpack.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t]
   tile=qrcode.make(b'CYM PACKET 310',box_size=5,border=4).convert('L');im=Image.new('L',(240,320),255);im.paste(tile,((240-tile.width)//2,(320-tile.height)//2))
   raw=bytearray()
   for v in im.tobytes():raw.extend([255,255] if v else [0,0])
   packet=bytearray([255,255,255,0])
   for y in range(320):packet.extend(bytes([255,255,255,64,0,0])+raw[y*480:(y+1)*480])
   rgb=C.create_string_buffer(153600);gray=C.create_string_buffer(76800)
   self.assertEqual(unpack(bytes(packet),len(packet),rgb,len(rgb)),0)
   self.assertEqual(self.lib.cym_qr_rgb565_gray(rgb,480,gray,240,320),0)
   self.assertEqual(self.decode(Image.frombytes('L',(240,320),gray.raw))[1],b'CYM PACKET 310')
   self.assertNotEqual(unpack(bytes(packet),len(packet)-1,rgb,len(rgb)),0)
   packet[4+486*100]=0;self.assertNotEqual(unpack(bytes(packet),len(packet),rgb,len(rgb)),0)

class ThemeNavigation310(unittest.TestCase):
 def test_shared_palette_both_nav_contracts_and_layout(self):
  main=(ROOT/'ESP32C5/main/main.c').read_text();ui=(ROOT/'ESP32C5/main/qr_decoder_ui.c').read_text()
  start=main.index('static void show_qr_decoder(void)\n{');screen=main[start:main.index('\n#endif',start)]
  self.assertLess(screen.index('create_function_page_base'),screen.index('g_screen_stop_fn = qr_decoder_ui_stop'))
  self.assertIn('g_home_layout_4cat ? show_cat_tools : show_main_tiles',screen)
  for token in ['apply_menu_bg()','ui_panel_color()','ui_card_color()','ui_card_pressed_color()','ui_border_color()','ui_text_color()','ui_muted_color()','UI_ACCENT_CYAN','g_font_icon14','screen_orientation']:self.assertIn(token,screen)
  self.assertIn('LV_PART_SCROLLBAR',ui);self.assertIn('LV_STATE_DISABLED',ui);self.assertIn('LV_STATE_PRESSED',ui)
  self.assertIn('lv_label_set_recolor(result_label,false)',ui)
  self.assertLess(ui.index('retry_button=lv_btn_create(body)'),ui.index('result_label=lv_label_create(body)'))
  for w,h in [(320,480),(480,320)]:
   body_h=h-40;preview_h=160 if h>w else 120
   # 12 padding + 34 two-line scan prompt + 6 gap + preview. Debug controls
   # may scroll, but whole frame and permanently separate top Back/Home fit.
   self.assertLess(12+34+6+preview_h,body_h)
  import re
  for label in re.findall(r'lv_label_set_text(?:_static)?\([^,]+,"([^"\n]*)"',ui):self.assertTrue(all(ord(c)<128 for c in label))
if __name__=='__main__':unittest.main()
