from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'ESP32C5/components/cym_doom'
OUT=ROOT/'.hermes/doom-prototype/exclusive-host'
class ExclusiveAudio(unittest.TestCase):
 def test_production_sanitized(self):
  OUT.mkdir(parents=True,exist_ok=True)
  cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(COMP/'include'),str(ROOT/'tests/exclusive_audio_cases.c'),str(COMP/'doom_mixer.c'),'-o',str(OUT/'cases')]
  r=subprocess.run(cmd,capture_output=True,text=True);(OUT/'compile.log').write_text(r.stdout+r.stderr)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  r=subprocess.run([str(OUT/'cases'),str(ROOT/'.hermes/doom-prototype/fixtures/freedoom-0.13.0/freedoom1.wad')],capture_output=True,text=True,timeout=30)
  (OUT/'runtime.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
