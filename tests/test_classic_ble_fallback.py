from pathlib import Path
import os, subprocess, sys, tempfile, unittest
class ClassicBleFallback(unittest.TestCase):
 def test_production_fallback_control_flow(self):
  with tempfile.TemporaryDirectory() as d:
   env=dict(os.environ,CYM_TEST_OUT=d)
   subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('run_classic_ble_fallback_host.py'))],env=env,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
