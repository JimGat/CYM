"""Exercise generated pack and authentic manual installer (not string-only ZIP proof)."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,tempfile,unittest,zipfile
ROOT=Path(__file__).resolve().parents[1]
ASSETS=Path(os.environ.get('CYM_SD_ASSETS_REPO',ROOT.parent/'CYM-SD-Assets'))
class QrSdPack(unittest.TestCase):
 def test_pack_install_inventory_and_preservation(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);archive=d/'pack.zip'
   subprocess.run(['python3',str(ASSETS/'tools/build_sd_pack.py'),str(archive)],check=True)
   with zipfile.ZipFile(archive) as z:
    self.assertIn('sdcard/lab/QR/',z.namelist());self.assertTrue(z.testzip() is None)
    z.extractall(d/'unpacked')
   src=d/'unpacked/sdcard';dst=d/'card';dst.mkdir();(dst/'personal.txt').write_bytes(b'keep')
   spec=importlib.util.spec_from_file_location('installer',ASSETS/'tools/install_sd.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   m.install(src,dst);self.assertTrue((dst/'lab/QR').is_dir())
   (dst/'lab/QR/qr-00000000.json').write_bytes(b'existing scan')
   before={str(p.relative_to(dst)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dst.rglob('*') if p.is_file()}
   m.install(src,dst)
   after={str(p.relative_to(dst)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dst.rglob('*') if p.is_file()}
   self.assertEqual(before,after)
   layout=json.loads((ASSETS/'SD_LAYOUT.json').read_text());self.assertIn('lab/QR',layout['directories'])
   for directory in layout['directories']:self.assertTrue((dst/directory).is_dir(),directory)
   for file in layout['files']:self.assertTrue((dst/file).is_file(),file)
   self.assertIn('{ SD_ITEM_DIR,  "/sdcard/lab/QR",',(ROOT/'ESP32C5/main/main.c').read_text())
 def test_collision_preserves_regular_file(self):
  spec=importlib.util.spec_from_file_location('installer',ASSETS/'tools/install_sd.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as d:
   dst=Path(d);(dst/'lab').mkdir();(dst/'lab/QR').write_bytes(b'keep collision')
   with self.assertRaises(FileExistsError):m.install(ASSETS/'sdcard',dst)
   self.assertEqual((dst/'lab/QR').read_bytes(),b'keep collision')
if __name__=='__main__':unittest.main()
