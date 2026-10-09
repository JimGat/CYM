"""Private official fixture only; no assets are committed or fetched by tests."""
from pathlib import Path
import ctypes as c,hashlib,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'.hermes/doom-prototype/fixtures/freedoom-0.13.0/freedoom1.wad'
class DoomRealAsset(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not FIXTURE.exists():raise unittest.SkipTest('Private official Freedoom fixture absent; runtime proof not substituted')
  out=ROOT/'.hermes/doom-prototype/host';out.mkdir(exist_ok=True)
  cls.libpath=out/'libdoom_contracts.so'
  r=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'ESP32C5/components/cym_doom/include'),str(ROOT/'ESP32C5/components/cym_doom/doom_contracts.c'),'-o',str(cls.libpath)],capture_output=True,text=True)
  if r.returncode:raise AssertionError(r.stderr)
  cls.lib=c.CDLL(str(cls.libpath));cls.readtype=c.CFUNCTYPE(c.c_bool,c.c_void_p,c.c_uint64,c.c_void_p,c.c_size_t)
  cls.lib.doom_wad_validate.argtypes=[cls.readtype,c.c_void_p,c.c_uint64];cls.lib.doom_wad_validate.restype=c.c_int
  cls.lib.doom_wad_trusted_hash.argtypes=[c.POINTER(c.c_uint8)];cls.lib.doom_wad_trusted_hash.restype=c.c_bool
 def test_official_resource_bounds(self):
  maximum=0
  with FIXTURE.open('rb') as f:
   def read(ctx,off,dst,n):
    nonlocal maximum
    maximum=max(maximum,n);f.seek(off);data=f.read(n)
    if len(data)!=n:return False
    c.memmove(dst,data,n);return True
   cb=self.readtype(read);self.assertEqual(self.lib.doom_wad_validate(cb,None,FIXTURE.stat().st_size),0)
  self.assertLessEqual(maximum,16)
 def test_official_digest_allowlist(self):
  digest=hashlib.file_digest(FIXTURE.open('rb'),'sha256').digest();buf=(c.c_uint8*32).from_buffer_copy(digest);self.assertTrue(self.lib.doom_wad_trusted_hash(buf))
 def test_altered_content_rejected(self):
  data=bytearray(FIXTURE.read_bytes());data[1024]^=1;buf=(c.c_uint8*32).from_buffer_copy(hashlib.sha256(data).digest());self.assertFalse(self.lib.doom_wad_trusted_hash(buf))
if __name__=='__main__':unittest.main(verbosity=2)
