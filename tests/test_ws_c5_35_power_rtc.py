from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class WS35PowerRTC(unittest.TestCase):
    def test_rtc_capability(self):
        s=(ROOT/'ESP32C5/components/board_hal/include/boards/ws_c5_35.h').read_text()
        self.assertIn('#define BOARD_TIME_HAS_RTC                    1',s)
        self.assertIn('#define BOARD_RTC_I2C_ADDR   0x51',s)
    def test_pmic_acquisition_and_shared_bus(self):
        s=(ROOT/'ESP32C5/main/main.c').read_text()
        self.assertTrue('ws_c5_35_battery_read' in s)
        self.assertTrue('cym_timekeeper_init(ws_c5_35_i2c_bus())' in s)
    def test_ws28_is_unchanged(self):
        import subprocess
        for p in ['ESP32C5/components/board_hal/include/boards/ws_c5_28.h', 'ESP32C5/main/custom_io_expander_ch32v003.c']:
            f=ROOT/p
            if f.exists(): self.assertEqual(f.read_bytes(),subprocess.check_output(['git','show','9c5f2d0:'+p],cwd=ROOT))

    def test_production_pmic_faults_and_decode(self):
        import subprocess, tempfile
        source=(ROOT/'ESP32C5/main/ws_c5_35_port.c').read_text()
        a=source.index('esp_err_t ws_c5_35_battery_read(bool *present')
        b=source.index('\n// ── Display init',a)
        harness=(ROOT/'tests/ws35_pmic_cases.c').read_text().replace('/* PRODUCTION_FUNCTION */',source[a:b])
        with tempfile.TemporaryDirectory() as d:
            c=Path(d)/'pmic.c'; exe=Path(d)/'pmic';c.write_text(harness)
            subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
