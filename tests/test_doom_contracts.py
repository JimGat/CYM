"""Execute production portable helpers on the host, with UBSan and strict C warnings.
Synthetic headers are parser fixtures, NOT game data or runtime proof.
"""
from pathlib import Path
import subprocess, unittest
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.hermes/doom-prototype/host'
class DoomContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True,exist_ok=True)
        cls.exe=OUT/'contracts'
        cls.command=['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-O1','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'ESP32C5/components/cym_doom/include'),str(ROOT/'tests/doom_contract_cases.c'),str(ROOT/'ESP32C5/components/cym_doom/doom_contracts.c'),'-o',str(cls.exe)]
        r=subprocess.run(cls.command,text=True,capture_output=True)
        (OUT/'compile.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise AssertionError(r.stdout+r.stderr)
    def run_case(self,case):
        r=subprocess.run([str(self.exe),case],text=True,capture_output=True,timeout=10)
        (OUT/(case+'.log')).write_text(r.stdout+r.stderr)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_wad_valid_directory(self):self.run_case('wad-valid')
    def test_wad_bounds_and_corruption(self):self.run_case('wad-bounds')
    def test_wad_resources_and_unsupported(self):self.run_case('wad-resources')
    def test_trigger_releases_timing_reset(self):self.run_case('trigger')
    def test_scale_touch_and_rotation(self):self.run_case('scale')
    def test_held_keys_touch_loss(self):self.run_case('keys')
    def test_lifecycle_partial_init_error_recovery(self):self.run_case('lifecycle')
    def test_gates_cancel_and_generation(self):self.run_case('gate')
if __name__=='__main__':unittest.main(verbosity=2)
