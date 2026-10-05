#!/usr/bin/env python3
"""Source contracts for the beta C5Lab Pancake-C5 target and related docs."""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

class PancakeProfileContract(unittest.TestCase):
    def test_exact_pinned_hardware_profile(self):
        p = text("ESP32C5/components/board_hal/include/boards/pancake_c5.h")
        expected = {
            "BOARD_SPI_MOSI": 24, "BOARD_SPI_MISO": 4, "BOARD_SPI_SCK": 23,
            "BOARD_LCD_CS": 5, "BOARD_LCD_DC": 3, "BOARD_LCD_RST": 2,
            "BOARD_BACKLIGHT_GPIO": 26, "BOARD_TOUCH_INT": 25,
            "BOARD_TOUCH_RST": 8, "BOARD_I2C_SDA": 9, "BOARD_I2C_SCL": 10,
            "BOARD_SD_CS": 7, "BOARD_GPS_TX": 13, "BOARD_GPS_RX": 14,
            "BOARD_RGB_LED_GPIO": 27, "BOARD_BATTERY_ADC_GPIO": 6,
            "BOARD_LCD_WIDTH": 480, "BOARD_LCD_HEIGHT": 320,
        }
        for macro, value in expected.items():
            self.assertRegex(p, rf"#define\s+{macro}\s+{value}\b", macro)
        for token in ('BOARD_NAME           "Pancake-C5"',
                      'BOARD_DISPLAY_DRIVER "ILI9341-compatible"',
                      'BOARD_TOUCH_DRIVER   "FT6336U"',
                      'C5Lab/pancake', '02528ded8feb242a8400e575b14e489ada1f960b'):
            self.assertIn(token, p)

    def test_capabilities_are_explicit_and_honest(self):
        p = text("ESP32C5/components/board_hal/include/boards/pancake_c5.h")
        for macro, value in {
            "BOARD_HAS_PSRAM": 1, "BOARD_HAS_SD": 1, "BOARD_HAS_RGB_LED": 1,
            "BOARD_HAS_BATTERY_ADC": 1, "BOARD_HAS_GPS": 1,
            "BOARD_TIME_HAS_RTC": 0, "BOARD_TIME_HAS_GPS_UART": 1,
            "BOARD_TIME_GPS_UNCERTAINTY_US": 500000,
            "BOARD_TIME_NTP_UNCERTAINTY_US": 250000,
            "BOARD_TIME_ESTIMATE_CHARACTERIZED": 0,
        }.items():
            self.assertRegex(p, rf"#define\s+{macro}\s+{value}\b", macro)
        self.assertNotIn("BOARD_RTC_I2C_ADDR", p)

    def test_kconfig_defaults_and_hal_dispatch(self):
        k = text("ESP32C5/components/board_hal/Kconfig")
        self.assertIn("config BOARD_PANCAKE_C5", k)
        self.assertRegex(k, re.compile(r"BOARD_HAS_PSRAM.*?BOARD_PANCAKE_C5", re.S))
        self.assertRegex(k, re.compile(r"BOARD_HAS_5GHZ.*?BOARD_PANCAKE_C5", re.S))
        self.assertRegex(k, re.compile(r"BOARD_HAS_802154.*?BOARD_PANCAKE_C5", re.S))
        self.assertRegex(k, re.compile(r"BOARD_TOUCH_FT6336.*?BOARD_PANCAKE_C5", re.S))
        self.assertIn("CONFIG_BOARD_PANCAKE_C5", text("ESP32C5/components/board_hal/include/board_hal.h"))
        d = text("ESP32C5/sdkconfig.defaults.pancake-c5")
        self.assertIn("CONFIG_BOARD_PANCAKE_C5=y", d)
        self.assertIn('CONFIG_ESPTOOLPY_FLASHSIZE="8MB"', d)

class PancakeAdapterContract(unittest.TestCase):
    def test_adapter_uses_reference_panel_contract(self):
        h = text("ESP32C5/main/pancake_c5_port.h")
        c = text("ESP32C5/main/pancake_c5_port.c")
        for symbol in ("pancake_c5_display_init", "pancake_c5_touch_init",
                       "pancake_c5_touch_read"):
            self.assertIn(symbol, h)
            self.assertIn(symbol, c)
        for token in ("40000000", "LCD_RGB_ELEMENT_ORDER_BGR",
                      "esp_lcd_panel_invert_color", "esp_lcd_panel_mirror",
                      "esp_lcd_panel_swap_xy", "BOARD_TOUCH_I2C_ADDR"):
            self.assertIn(token, c)
        self.assertRegex(c, re.compile(r"esp_lcd_panel_invert_color\([^;]+true", re.S))
        self.assertRegex(c, re.compile(r"esp_lcd_panel_mirror\([^;]+true\s*,\s*true", re.S))
        self.assertRegex(c, re.compile(r"esp_lcd_panel_swap_xy\([^;]+true", re.S))
        self.assertIn("esp_lcd_panel_reset", c)
        self.assertLess(c.index("esp_lcd_panel_reset"), c.index("esp_lcd_panel_init"))
        ili = text("ESP32C5/components/espressif__esp_lcd_ili9341/esp_lcd_ili9341.c")
        self.assertIn("gpio_reset_pin(ili9341->reset_gpio_num)", ili)
        self.assertIn("gpio_set_level(ili9341->reset_gpio_num, ili9341->reset_level)", ili)

    def test_ft6336_uses_supported_idf6_i2c_master_api(self):
        h = text("ESP32C5/main/pancake_ft6336.h")
        c = text("ESP32C5/main/pancake_ft6336.c")
        port = text("ESP32C5/main/pancake_c5_port.c")
        self.assertNotIn('"driver/i2c.h"', h + c + port)
        self.assertIn('"driver/i2c_master.h"', h)
        self.assertIn("i2c_new_master_bus", port)
        self.assertIn("i2c_master_bus_add_device", port)
        self.assertIn("i2c_master_transmit_receive", c)

    def test_ft6336_transform_matches_pinned_reference(self):
        c = text("ESP32C5/main/pancake_ft6336.c")
        self.assertIn("handle->width - raw_y", c)
        self.assertIn("point->y = raw_x", c)
        self.assertIn("FT6336_REG_CHIPID", c)
        self.assertIn("0x38", text("ESP32C5/main/pancake_ft6336.h"))

    def test_shared_main_selects_adapter_without_parallel_app(self):
        m = text("ESP32C5/main/main.c")
        self.assertIn('#include "pancake_c5_port.h"', m)
        self.assertRegex(m, re.compile(r"CONFIG_BOARD_PANCAKE_C5.*?pancake_c5_display_init", re.S))
        self.assertRegex(m, re.compile(r"CONFIG_BOARD_PANCAKE_C5.*?pancake_c5_touch_init", re.S))
        self.assertRegex(m, re.compile(r"CONFIG_BOARD_PANCAKE_C5.*?pancake_c5_touch_read", re.S))
        self.assertIn('"pancake_c5_port.c"', text("ESP32C5/main/CMakeLists.txt"))
        self.assertIn('"pancake_ft6336.c"', text("ESP32C5/main/CMakeLists.txt"))

class PancakePackagingContract(unittest.TestCase):
    def test_build_gate_and_version(self):
        self.assertIn("pancake-c5)", text("scripts/build.sh"))
        self.assertIn("all-boards: nm-cyd-c5 ws-c5-28 ws-c5-35 pancake-c5 cyd-2432s028 hosyond-s3-35", text("Makefile"))
        for rel in ("ESP32C5/CMakeLists.txt", "ESP32/CMakeLists.txt", "ESP32S3/CMakeLists.txt"):
            self.assertIn('set(PROJECT_VER "v2.15.62")', text(rel), rel)

    def test_cmake_exports_pancake_package(self):
        c = text("ESP32C5/CMakeLists.txt")
        self.assertRegex(c, re.compile(r"CONFIG_BOARD_PANCAKE_C5.*?binaries-pancake-c5.*?CYM-Pancake-C5.*?8MB", re.S))

    def test_memory_report_is_packaged_for_pancake(self):
        report = ROOT / "ESP32C5/docs/memory-budget-CYM-Pancake-C5.md"
        self.assertTrue(report.exists())
        self.assertIn("CYM-Pancake-C5", report.read_text())

    def test_manifest_and_beta_flasher(self):
        manifest = json.loads(text("ESP32C5/docs/manifest.pancake-c5.json"))
        self.assertIn("Pancake-C5", manifest["name"])
        self.assertIn("v2.15.62", manifest["name"])
        parts = manifest.get("parts") or manifest["builds"][0]["parts"]
        self.assertEqual({p["offset"] for p in parts}, {0x2000, 0x8000, 0x10000})
        f = text("ESP32C5/docs/index.html")
        self.assertIn('"pancake-c5": {', f)
        self.assertIn('fullBin: "CYM-Pancake-C5-full.bin"', f)
        board = f[f.index('"pancake-c5": {'):f.index("},", f.index('"pancake-c5": {'))]
        self.assertIn("beta:    true", board)
        defaults = re.search(r"const DEFAULT_BOARD_IDS = \[(.*?)\]", f).group(1)
        self.assertNotIn("pancake-c5", defaults)
        w = text(".github/workflows/deploy-flasher.yml")
        for token in ("manifest.pancake-c5.json", "binaries-pancake-c5", "CYM-Pancake-C5-full.bin"):
            self.assertIn(token, w)

class DocumentationContract(unittest.TestCase):
    def test_pancake_is_explicitly_dev_channel_not_stable(self):
        manifest = text("ESP32C5/docs/manifest.pancake-c5.json")
        flasher = text("ESP32C5/docs/index.html")
        readme = text("README.md")
        hardware = text("docs/hardware/pancake-c5.md")
        self.assertIn("Development Channel", manifest)
        self.assertIn("Development channel only; not stable", flasher)
        self.assertIn("Development channel only; not stable", readme)
        self.assertIn("Development channel only; not stable", hardware)
        self.assertIn('urlParams.get("beta") === "1"', flasher)

    def test_readme_documents_physical_hid_clone(self):
        r = text("README.md")
        for token in ("Clone T5577", "HID Prox", "physical", "read-back", "remove the source"):
            self.assertIn(token, r)

    def test_readme_has_full_clock_and_ham_use_case(self):
        r = text("README.md")
        for token in ("Universal Clock", "Display Only", "Client NTP", "AP NTP",
                      "FT4", "FT8", "off-grid", "PCF85063A", "4.32 seconds/day",
                      "UART RMC", "PPS", "not a guaranteed sub-50-ms"):
            self.assertIn(token, r)

    def test_operator_clock_doc_has_accuracy_grid_and_sources(self):
        d = text("docs/hardware/universal-clock.md")
        for token in ("FT4", "FT8", "off-grid", "Accuracy and suitability grid",
                      "4.32 seconds/day", "external 32.768 kHz crystal",
                      "NXP PCF85063A data sheet", "WSJT-X User Guide",
                      "not a guaranteed sub-50-ms"):
            self.assertIn(token, d)

    def test_pancake_docs_credit_inspiration(self):
        r = text("README.md")
        for name in ("D3h420", "Janek", "OyczE"):
            self.assertIn(name, r)
        self.assertIn("Pancake-C5", r)

if __name__ == "__main__":
    unittest.main()
