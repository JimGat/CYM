"""Build the production QR wrapper/ZXing engine once, outside tracked source."""
from pathlib import Path
import os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
_cache=None
_scratch=None
def native_library():
 global _cache,_scratch
 if _cache is None:
  _scratch=tempfile.TemporaryDirectory(prefix="cym-native-")
  build=Path(_scratch.name)
  subprocess.run(["cmake","-S",str(ROOT/"ESP32C5/components/cym_qr/native"),"-B",str(build),"-G","Ninja","-DCMAKE_BUILD_TYPE=Release"],check=True)
  subprocess.run(["cmake","--build",str(build),"--parallel","2"],check=True)
  _cache=build/"libcym_qr_host.so"
 return _cache
