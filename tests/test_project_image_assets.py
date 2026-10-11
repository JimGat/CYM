"""Project artwork and LVGL image serialization contracts."""
import importlib.util
from pathlib import Path
import re
import unittest
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]

class ImageAssets(unittest.TestCase):
    def test_public_pngs_are_identical(self):
        a=ROOT/'docs/screenshots/DeeDee.png'
        b=ROOT/'ESP32C5/docs/deedee.png'
        self.assertEqual(a.read_bytes(), b.read_bytes())
        with Image.open(a) as im:
            self.assertEqual(im.mode, 'RGBA')
            self.assertEqual(im.size, (447,913))

    def test_artwork_transparency(self):
        for name in ['DeeDee','BrattSister']:
            with self.subTest(name=name), Image.open(ROOT/'docs/screenshots'/f'{name}.png') as im:
                self.assertEqual(im.mode, 'RGBA')
                a=im.getchannel('A');w,h=im.size
                self.assertEqual(a.getpixel((0,0)),0)
                self.assertEqual(a.getpixel((w-1,h-1)),0)
                self.assertEqual(a.getextrema(),(0,255))
                self.assertGreater(a.getbbox()[0],0)
                self.assertLess(a.getbbox()[2],w)

    def test_image_descriptor_contract(self):
        s=(ROOT/'ESP32C5/main/deedee_img.c').read_text()
        self.assertIn('LV_IMG_CF_TRUE_COLOR_ALPHA',s)
        self.assertIn('#if LV_COLOR_16_SWAP',s)
        self.assertRegex(s,r'\.w\s*=\s*120')
        self.assertRegex(s,r'\.h\s*=\s*180')
        self.assertRegex(s,r'\.data_size\s*=\s*64800')

    def test_embedded_pixels_match_png(self):
        s=(ROOT/'ESP32C5/main/deedee_img.c').read_text()
        body=s.split('= {',1)[1].split('};',1)[0]
        actual=bytearray()
        for color,alpha in re.findall(r'IMAGE_PIXEL\(0x([0-9a-fA-F]{4}), 0x([0-9a-fA-F]{2})\)',body):
            n=int(color,16);actual.extend([n&255,n>>8,int(alpha,16)])
        im=Image.open(ROOT/'docs/screenshots/BrattSister.png').convert('RGBA')
        fit=ImageOps.contain(im,(116,176),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(120,180))
        canvas.paste(fit,((120-fit.width)//2,(180-fit.height)//2))
        expected=bytearray()
        for r,g,b,a in canvas.get_flattened_data():
            n=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
            expected.extend([n&255,n>>8,a])
        self.assertEqual(len(actual),64800)
        self.assertEqual(actual,expected)

    def test_converter_color_and_alpha_order(self):
        spec=importlib.util.spec_from_file_location('image_converter',ROOT/'tools/convert_project_image.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        im=Image.new('RGBA',(3,1));im.putdata([(255,0,0,255),(0,255,0,128),(0,0,255,0)])
        self.assertEqual(mod.rgb565_alpha(im),bytes([0,248,255,224,7,128,31,0,0]))
        self.assertEqual(mod.rgb565_alpha(im,True),bytes([248,0,255,7,224,128,0,31,0]))

if __name__=='__main__':unittest.main()
