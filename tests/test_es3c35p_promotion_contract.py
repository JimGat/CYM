from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

class PromotionContract(unittest.TestCase):
    def test_shared_source_and_adapter_boundary(self):
        cmake = text("ESP32S3/main/CMakeLists.txt")
        self.assertIn('set(C5_MAIN "${CMAKE_CURRENT_SOURCE_DIR}/../../ESP32C5/main")', cmake)
        self.assertIn('"${C5_MAIN}/main.c"', cmake)
        self.assertIn('"hosyond_s3_35_port.c"', cmake)
        self.assertNotRegex(cmake, r'(?m)^\s*"main\.c"\s*$')

    def test_es3c35p_profile(self):
        profile = text("ESP32C5/components/board_hal/include/boards/hosyond_s3_35.h")
        required = {
            "BOARD_HAS_PSRAM": "1", "BOARD_HAS_SD": "1",
            "BOARD_HAS_RGB_LED": "1", "BOARD_HAS_BATTERY_ADC": "1",
            "BOARD_HAS_GPS": "1", "BOARD_GPS_UART_NUM": "1",
            "BOARD_GPS_TX": "43", "BOARD_GPS_RX": "44",
            "BOARD_RGB_PIN": "40", "BOARD_BATTERY_ADC_GPIO": "8",
        }
        for macro, value in required.items():
            self.assertRegex(profile, rf"#define\s+{macro}\s+{value}\b")
        for macro in ("BOARD_HAS_5GHZ", "BOARD_HAS_IEEE802154", "BOARD_HAS_AUDIO",
                      "BOARD_HAS_VIBRATOR", "BOARD_HAS_RF_HAT"):
            self.assertRegex(profile, rf"#define\s+{macro}\s+0\b")

    def test_ws_c5_28_gps_profile(self):
        profile = text("ESP32C5/components/board_hal/include/boards/ws_c5_28.h")
        for macro, value in {"BOARD_HAS_GPS":"1", "BOARD_GPS_UART_NUM":"1",
                             "BOARD_GPS_TX":"11", "BOARD_GPS_RX":"12"}.items():
            self.assertRegex(profile, rf"#define\s+{macro}\s+{value}\b")

    def test_board_defaults_and_s3_console_ownership(self):
        hal = text("ESP32C5/components/board_hal/include/board_hal.h")
        for macro in ("BOARD_HAS_GPS", "BOARD_GPS_TX", "BOARD_GPS_RX",
                      "BOARD_HAS_BATTERY_ADC", "BOARD_BATTERY_ADC_GPIO",
                      "BOARD_BATTERY_DIVIDER_NUM", "BOARD_BATTERY_DIVIDER_DEN",
                      "BOARD_HAS_RGB_LED", "BOARD_RGB_PIN"):
            self.assertIn(f"#ifndef {macro}", hal)
        profile = text("ESP32C5/components/board_hal/include/boards/hosyond_s3_35.h")
        self.assertRegex(profile, r"#define\s+BOARD_SD_SPI_FREQ_HZ\s+20000000\b")
        defaults = text("ESP32S3/sdkconfig.defaults.hosyond-s3-35")
        self.assertIn("CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y", defaults)
        self.assertIn("CONFIG_ESP_CONSOLE_SECONDARY_NONE=y", defaults)
        self.assertIn("# CONFIG_ESP_CONSOLE_UART_DEFAULT is not set", defaults)

    def test_release_version_and_four_board_gate(self):
        for project in ("ESP32C5/CMakeLists.txt", "ESP32/CMakeLists.txt", "ESP32S3/CMakeLists.txt"):
            self.assertIn('set(PROJECT_VER "v2.15.27")', text(project))
        makefile = text("Makefile")
        for target in ("esp32c5", "ws-c5-28", "cyd-2432s028", "hosyond-s3-35"):
            self.assertIn(target, makefile)

    def test_manifest_and_flasher(self):
        manifest_path = ROOT / "ESP32S3/docs/manifest.hosyond-s3-35.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["name"], "CYM Hosyond ES3C35P 3.5 v2.15.27")
        parts = {item["offset"]: item["path"] for item in manifest["builds"][0]["parts"]}
        self.assertIn(0, parts)
        self.assertIn(0x8000, parts)
        self.assertIn(0x10000, parts)
        flasher = text("ESP32C5/docs/index.html")
        self.assertIn("hosyond-s3-35", flasher)
        self.assertIn("ESP32-S3", flasher)
        self.assertIn("binaries-hosyond-s3-35", flasher)
        workflow = text(".github/workflows/deploy-flasher.yml")
        self.assertIn("ESP32S3/docs/manifest.hosyond-s3-35.json", workflow)
        self.assertIn("ESP32S3/binaries-hosyond-s3-35", workflow)

if __name__ == "__main__":
    unittest.main()
