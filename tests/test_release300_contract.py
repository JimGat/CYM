from pathlib import Path
import unittest,json,re
ROOT=Path(__file__).resolve().parents[1]
class Release300(unittest.TestCase):
 def test_version_and_documentation(self):
  for soc in ['ESP32','ESP32C5','ESP32S3']:
   self.assertIn('set(PROJECT_VER "v3.0.33")',(ROOT/soc/'CMakeLists.txt').read_text())
  readme=(ROOT/'README.md').read_text()
  for s in ['v3.0.0','Off-grid amateur radio','Maidenhead','NTP server','NTP client','GPIO28','GPS LOCK','9600','@birolt29']:
   self.assertIn(s,readme)
  notes=(ROOT/'docs/releases/v3.0.0.md').read_text()
  for s in ['FT4','FT8','stratum 1','PPS','Maidenhead','@birolt29']:
   self.assertIn(s,notes)
  self.assertIsNone(re.search(r'doom|easter.?egg|cym_doom',notes,re.I))
 def test_stable_board_and_deployment(self):
  p=(ROOT/'ESP32C5/docs/index.html').read_text()
  hb=re.search(r'"hackerbox-cyd": \{.*?\n        \}',p,re.S).group()
  self.assertIn('stableAvailable: true',hb)
  for b in ['pancake-c5','ws-s3-5b']:
   entry=re.search(r'"'+b+r'": \{.*?\n        \}',p,re.S).group()
   self.assertRegex(entry,r'beta:\s+true')
  deploy=(ROOT/'.github/workflows/deploy-flasher.yml').read_text()
  for s in ['_site/binaries-hackerbox-cyd','_site/manifest.hackerbox-cyd.json']:
   self.assertIn(s,deploy)
if __name__=='__main__':unittest.main()
