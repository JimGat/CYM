#!/usr/bin/env python3
"""Source contracts for the experimental Waveshare WS-C5-35 target."""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

class WsC535ProfileContract(unittest.TestCase):
    def test_exact_vendor_hardware_profile(self):
        p = text("ESP32C5/components/board_hal/include/boards/ws_c5_35.h")
        expected = {
            "BOARD_SPI_MOSI": 7, "BOARD_SPI_MISO": 2, "BOARD_SPI_SCK": 6,
            "BOARD_LCD_CS": 8, "BOARD_LCD_DC": 5, "BOARD_LCD_RST": -1,
            "BOARD_TOUCH_INT": 3, "BOARD_TOUCH_RST": -1,
            "BOARD_I2C_SDA": 27, "BOARD_I2C_SCL": 26,
            "BOARD_IO_EXPANDER_I2C_ADDR": 0x24,
            "BOARD_TOUCH_I2C_ADDR": 0x38,
            "BOARD_PMIC_I2C_ADDR": 0x34,
            "BOARD_SD_CS": 9, "BOARD_LCD_WIDTH": 320,
            "BOARD_LCD_HEIGHT": 480, "BOARD_LCD_PCLK_HZ": 60000000,
        }
        for macro, value in expected.items():
            rendered = hex(value) if isinstance(value, int) and value >= 16 and macro.endswith("ADDR") else str(value)
            self.assertRegex(p, rf"#define\s+{macro}\s+{re.escape(rendered)}\b", macro)
        for token in ('BOARD_NAME           "WS-C5-35"',
                      'BOARD_DISPLAY_DRIVER "ST7796"',
                      'BOARD_TOUCH_DRIVER   "FT6336"',
                      '04e6134cf3e37309b2bec9915189efeace1161bc'):
            self.assertIn(token, p)

    def test_capabilities_are_experimental_and_honest(self):
        p = text("ESP32C5/components/board_hal/include/boards/ws_c5_35.h")
        for macro, value in {
            "BOARD_HAS_PSRAM": 1, "BOARD_HAS_SD": 1,
            "BOARD_HAS_GPS": 0, "BOARD_HAS_BATTERY_ADC": 0,
            "BOARD_HAS_AUDIO": 0, "BOARD_HAS_RGB_LED": 0,
            "BOARD_TIME_HAS_RTC": 0, "BOARD_TIME_HAS_GPS_UART": 0,
            "BOARD_TIME_ESTIMATE_CHARACTERIZED": 0,
        }.items():
            self.assertRegex(p, rf"#define\s+{macro}\s+{value}\b", macro)
        self.assertNotIn("BOARD_GPS_TX", p)
        self.assertNotIn("BOARD_GPS_RX", p)

    def test_selection_defaults_and_build_entry_points(self):
        k = text("ESP32C5/components/board_hal/Kconfig")
        self.assertIn("config BOARD_WS_C5_35", k)
        self.assertRegex(k, re.compile(r"BOARD_HAS_PSRAM.*?BOARD_WS_C5_35", re.S))
        self.assertRegex(k, re.compile(r"BOARD_HAS_5GHZ.*?BOARD_WS_C5_35", re.S))
        self.assertRegex(k, re.compile(r"BOARD_HAS_802154.*?BOARD_WS_C5_35", re.S))
        self.assertRegex(k, re.compile(r"BOARD_TOUCH_FT6336.*?BOARD_WS_C5_35", re.S))
        self.assertIn("CONFIG_BOARD_WS_C5_35", text("ESP32C5/components/board_hal/include/board_hal.h"))
        d = text("ESP32C5/sdkconfig.defaults.ws-c5-35")
        self.assertIn("CONFIG_BOARD_WS_C5_35=y", d)
        self.assertIn('CONFIG_ESPTOOLPY_FLASHSIZE="32MB"', d)
        self.assertIn("ws-c5-35)", text("scripts/build.sh"))
        mk = text("Makefile")
        self.assertIn("ws-c5-35:", mk)
        all_boards = mk[mk.index("all-boards:"):mk.index("# ── ESP32-C5 boards")]
        self.assertIn("ws-c5-35", all_boards)

class WsC535AdapterContract(unittest.TestCase):
    def test_adapter_uses_vendor_display_contract(self):
        c = text("ESP32C5/main/ws_c5_35_port.c")
        for token in ("esp_lcd_new_panel_st7796", "LCD_RGB_ELEMENT_ORDER_BGR",
                      "BOARD_LCD_PCLK_HZ", "esp_lcd_panel_invert_color",
                      "esp_lcd_panel_mirror", "esp_lcd_panel_disp_on_off"):
            self.assertIn(token, c)
        self.assertRegex(c, re.compile(r"esp_lcd_panel_invert_color\([^;]+true", re.S))
        self.assertRegex(c, re.compile(r"esp_lcd_panel_mirror\([^;]+true\s*,\s*false", re.S))
        self.assertNotIn("esp_lcd_panel_swap_xy", c)

    def test_backlight_and_required_exio5_use_dedicated_adapter(self):
        c = text("ESP32C5/main/ws_c5_35_port.c")
        m = text("ESP32C5/main/main.c")
        self.assertIn("BOARD_POWER_ENABLE_EXIO", c)
        self.assertIn("ws35_exio_set_pin(BOARD_POWER_ENABLE_EXIO, true)", c)
        dim = m[m.rindex("static void screen_set_dimmed"):m.rindex("static void screen_idle_timer_cb")]
        self.assertGreaterEqual(dim.count("ws_c5_35_backlight_set"), 2)

    def test_ch32v006_protocol_is_16_bit_little_endian(self):
        c = text("ESP32C5/main/ws_c5_35_port.c")
        for token in ("WS35_EXIO_REG_MODE", "0x02", "WS35_EXIO_REG_OUTPUT", "0x03",
                      "WS35_EXIO_REG_PWM", "0x05", "BOARD_IO_EXPANDER_I2C_ADDR",
                      "output_shadow & 0xff", "output_shadow >> 8"):
            self.assertIn(token, c)
        self.assertNotIn("custom_io_expander_new_i2c_ch32v003", c)
        self.assertIn("BOARD_LCD_RESET_EXIO", c)
        self.assertIn("BOARD_TOUCH_RESET_EXIO", c)

    def test_touch_uses_vendor_ft6336_path_without_pancake_transform(self):
        c = text("ESP32C5/main/ws_c5_35_port.c")
        self.assertIn("esp_lcd_touch_new_i2c_ft6336", c)
        self.assertIn("ESP_LCD_TOUCH_IO_I2C_FT6336_CONFIG", c)
        self.assertIn("BOARD_TOUCH_I2C_ADDR", c)
        self.assertIn(".swap_xy = 0", c)
        self.assertIn(".mirror_x = 0", c)
        self.assertIn(".mirror_y = 0", c)
        self.assertNotIn("pancake_c5", c)

    def test_main_selects_dedicated_adapter(self):
        m = text("ESP32C5/main/main.c")
        for symbol in ("ws_c5_35_display_init", "ws_c5_35_touch_init",
                       "ws_c5_35_touch_read", "ws_c5_35_backlight_set"):
            self.assertIn(symbol, m)
        cm = text("ESP32C5/main/CMakeLists.txt")
        self.assertIn('"ws_c5_35_port.c"', cm)
        self.assertIn("esp_lcd_touch_ft6336", cm)
        self.assertIn("espressif__esp_lcd_st7796", cm)

class WsC535PackagingContract(unittest.TestCase):
    def test_version_is_shared_for_cycle(self):
        for rel in ("ESP32C5/CMakeLists.txt", "ESP32/CMakeLists.txt", "ESP32S3/CMakeLists.txt"):
            self.assertIn('set(PROJECT_VER "v2.15.59")', text(rel), rel)

    def test_dedicated_package_and_manifest(self):
        c = text("ESP32C5/CMakeLists.txt")
        self.assertRegex(c, re.compile(r"CONFIG_BOARD_WS_C5_35.*?binaries-ws-c5-35.*?CYM-WS-C5-35.*?32MB", re.S))
        manifest = json.loads(text("ESP32C5/docs/manifest.ws-c5-35.json"))
        self.assertIn("WS-C5-35 Experimental", manifest["name"])
        self.assertEqual(manifest["version"], "v2.15.59")
        self.assertEqual({p["offset"] for p in manifest["parts"]}, {0x2000, 0x8000, 0x10000})
        self.assertTrue(all("binaries-ws-c5-35" in p["path"] for p in manifest["parts"]))

    def test_beta_flasher_is_opt_in_and_isolated(self):
        f = text("ESP32C5/docs/index.html")
        self.assertIn('"ws-c5-35": {', f)
        start = f.index('"ws-c5-35": {')
        board = f[start:f.index("},", start)]
        for token in ('fullBin: "CYM-WS-C5-35-full.bin"',
                      'manifest: "docs/manifest.ws-c5-35.json"',
                      "beta:    true", "Experimental"):
            self.assertIn(token, board)
        defaults = re.search(r"const DEFAULT_BOARD_IDS = \[(.*?)\]", f).group(1)
        self.assertNotIn("ws-c5-35", defaults)
        self.assertIn('const PAGE_VERSION    = "2.14.0"', f)
        w = text(".github/workflows/deploy-flasher.yml")
        for token in ("manifest.ws-c5-35.json", "binaries-ws-c5-35", "CYM-WS-C5-35-full.bin"):
            self.assertIn(token, w)
        ws_copy = next(line for line in w.splitlines() if "cp ESP32C5/binaries-ws-c5-35/*.bin" in line)
        self.assertNotIn("|| true", ws_copy)

class WsC535DocumentationContract(unittest.TestCase):
    def test_docs_mark_static_evidence_and_pending_hardware_validation(self):
        r = text("README.md")
        d = text("docs/hardware/waveshare-c5-touch-lcd-35.md")
        for token in ("Development channel only; not stable", "hardware validation pending",
                      "CH32V006", "ST7796", "FT6336"):
            self.assertIn(token, r + d)
        self.assertIn("https://github.com/waveshareteam/ESP32-C5-Touch-LCD-3.5", d)
        self.assertIn("04e6134cf3e37309b2bec9915189efeace1161bc", d)
        self.assertIn("GPS", d)
        self.assertIn("disabled", d.lower())

if __name__ == "__main__":
    unittest.main()
