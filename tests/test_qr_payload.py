"""Native behavior tests of the production QR record writer."""
import ctypes as C
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'ESP32C5/components/cym_qr/qr_record.c'
class QRRecordTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  assert SRC.exists(), 'QR record implementation is missing'
  cls.tmp=tempfile.TemporaryDirectory()
  so=Path(cls.tmp.name)/'record.so'
  subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror','-I',str(SRC.parent/'include'),str(SRC),'-o',str(so)],check=True)
  cls.lib=C.CDLL(str(so),use_errno=True)
  cls.lib.cym_qr_record.argtypes=[C.c_char_p,C.c_void_p,C.c_size_t,C.c_char_p,C.c_longlong,C.c_ulonglong,C.c_void_p,C.c_size_t]
  cls.lib.cym_qr_escape.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t]
  cls.lib.cym_qr_escape.restype=C.c_size_t
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def save(self,root,data=b'https://example.com',utc=0):
  out=C.create_string_buffer(128)
  rc=self.lib.cym_qr_record(os.fsencode(root),data,len(data),b'v3.0.8',utc,123456,out,len(out))
  return rc,out.value.decode()
 def test_missing_parents_and_unique_same_payload(self):
  with tempfile.TemporaryDirectory(dir=self.tmp.name) as root:
   rc,a=self.save(root);self.assertEqual(rc,0)
   rc,b=self.save(root);self.assertEqual(rc,0);self.assertNotEqual(a,b)
   self.assertEqual(len(list((Path(root)/'lab/QR').glob('*.json'))),2)
 def test_binary_roundtrip_invalid_clock_and_safe_text(self):
  data=b'A\0\xff\n"\\#ff0000'
  with tempfile.TemporaryDirectory(dir=self.tmp.name) as root:
   rc,name=self.save(root,data);self.assertEqual(rc,0)
   doc=json.loads((Path(root)/'lab/QR'/name).read_text())
   self.assertEqual(bytes.fromhex(doc['payload_hex']),data)
   self.assertEqual(doc['byte_length'],len(data))
   self.assertFalse(doc['timestamp_valid']);self.assertIsNone(doc['utc_unix'])
   self.assertEqual(doc['uptime_ms'],123456);self.assertEqual(doc['symbology'],'QR')
   self.assertEqual(doc['display_text'],r'A\x00\xFF\x0A"\#ff0000')
 def test_regular_file_collisions_preserved(self):
  for collision in ['lab','lab/QR']:
   with tempfile.TemporaryDirectory(dir=self.tmp.name) as root:
    p=Path(root)/collision;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('preserve')
    rc,_=self.save(root);self.assertNotEqual(rc,0);self.assertEqual(p.read_text(),'preserve')
 def test_existing_files_preserved_and_valid_clock(self):
  with tempfile.TemporaryDirectory(dir=self.tmp.name) as root:
   q=Path(root)/'lab/QR';q.mkdir(parents=True);(q/'qr-00000000.json').write_text('old')
   rc,name=self.save(root,utc=1792166400);self.assertEqual(rc,0)
   self.assertEqual((q/'qr-00000000.json').read_text(),'old')
   self.assertTrue(json.loads((q/name).read_text())['timestamp_valid'])
 def test_absent_root_and_bad_args(self):
  rc,name=self.save(Path(self.tmp.name)/'absent');self.assertNotEqual(rc,0);self.assertEqual(name,'')
 def test_escape_bounded(self):
  out=C.create_string_buffer(6);n=self.lib.cym_qr_escape(b'\0\xffabc',5,out,6)
  self.assertEqual(n,11);self.assertLessEqual(len(out.value),5)
if __name__=='__main__':unittest.main()
