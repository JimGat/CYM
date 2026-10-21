"""Execute actual pre-project CMake version selection, without configuring any board."""
import os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ClassicCandidateVersion(unittest.TestCase):
 def test_only_actual_classic_no_psram_bumps(self):
  source=(ROOT/'ESP32/CMakeLists.txt').read_text()
  selector=source[source.index('# ── Single source'):source.index('# Bootstrap ESP-IDF')]
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
   d=Path(tmp);defaults=d/'sdkconfig.defaults.cyd2usb';defaults.write_text('CONFIG_BOARD_CYD2USB=y\n')
   extra=d/'sdkconfig.defaults.extra';config=d/'sdkconfig';out=d/'result';script=d/'version.cmake'
   script.write_text('cmake_minimum_required(VERSION 3.16)\nset(CMAKE_SOURCE_DIR \"'+str(d)+'\")\n'+selector+'\nfile(WRITE "'+str(out)+'" "${PROJECT_VER}")\n')
   work=d/'build';work.mkdir()
   cases=[('classic-defaults',None,'','v3.0.35'),('hackerbox-defaults',None,'CONFIG_BOARD_HACKERBOX_CYD=y\n','v3.0.35'),('board-psram-defaults',None,'CONFIG_BOARD_HAS_PSRAM=y\n','v3.0.33'),('spiram-defaults',None,'CONFIG_SPIRAM=y\n','v3.0.33'),('classic-config','CONFIG_BOARD_CYD2USB=y\n','','v3.0.35'),('hackerbox-config','CONFIG_BOARD_CYD2USB=y\nCONFIG_BOARD_HACKERBOX_CYD=y\n','','v3.0.35'),('psram-config','CONFIG_BOARD_CYD2USB=y\nCONFIG_SPIRAM=y\n','','v3.0.33'),('nonclassic-config','CONFIG_BOARD_WS_C5_35=y\n','','v3.0.33')]
   for name,saved,more,expected in cases:
    with self.subTest(case=name):
     if config.exists():config.unlink()
     if saved is not None:config.write_text(saved)
     extra.write_text(more)
     subprocess.run(['cmake','-DSDKCONFIG='+str(config),'-DSDKCONFIG_DEFAULTS='+defaults.name+';'+extra.name,'-P',str(script)],cwd=work,check=True,capture_output=True,text=True)
     self.assertEqual(out.read_text(),expected)
if __name__=='__main__':unittest.main()
