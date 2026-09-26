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

    def test_console_transport_follows_sdkconfig(self):
        cli = text("ESP32C5/components/wifi_cli/wifi_cli.c")
        self.assertIn("CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG", cli)
        self.assertIn("esp_console_new_repl_usb_serial_jtag", cli)
        self.assertIn("esp_console_new_repl_uart", cli)

    def test_s3_flush_isolated_and_adc_calibration_portable(self):
        main = text("ESP32C5/main/main.c")
        flush = main[main.rindex("void lvgl_flush_cb"):main.index("void lvgl_touch_read_cb", main.rindex("void lvgl_flush_cb"))]
        self.assertRegex(flush, r"(?s)#else\s+esp_lcd_panel_handle_t panel.*#endif\s+lv_disp_flush_ready\(drv\);")
        self.assertIn("ADC_CALI_SCHEME_CURVE_FITTING_SUPPORTED", main)
        self.assertIn("ADC_CALI_SCHEME_LINE_FITTING_SUPPORTED", main)

    def test_es3c35p_adapter_contract(self):
        header = text("ESP32S3/main/hosyond_s3_35_port.h")
        source = text("ESP32S3/main/hosyond_s3_35_port.c")
        for symbol in ("hosyond_s3_35_display_init", "hosyond_s3_35_draw",
                       "hosyond_s3_35_round_area", "hosyond_s3_35_touch_init",
                       "hosyond_s3_35_touch_read"):
            self.assertIn(symbol, header)
            self.assertIn(symbol, source)
        for invariant in ("40000000", "xSemaphoreGiveFromISR", "xSemaphoreTake",
                          "BOARD_BACKLIGHT_GPIO", "BOARD_TOUCH_I2C_ADDR",
                          "BOARD_LCD_DRAW_ROUNDING", "hosyond_s3_35_lcd_init"):
            self.assertIn(invariant, source)
        init = text("ESP32S3/main/hosyond_s3_35_lcd_init.h")
        self.assertEqual(len(re.findall(r"^\s*\{0x", init, re.MULTILINE)), 63)
        self.assertIn("HOSYOND_S3_35_LCD_INIT_SIZE", init)
        self.assertIn("0x01, 0x3F", init)
        self.assertIn("0x01, 0xDF", init)
        self.assertIn("{0x36, (uint8_t []){0x00}", init)

    def test_shared_peripherals_use_board_profile_contracts(self):
        common = text("ESP32C5/components/wifi_cli/include/wifi_common.h")
        self.assertIn("#define GPS_TX_PIN   BOARD_GPS_TX", common)
        self.assertIn("#define GPS_RX_PIN   BOARD_GPS_RX", common)
        wardrive = text("ESP32C5/components/wifi_wardrive/wifi_wardrive.c")
        self.assertIn("BOARD_SD_SPI_FREQ_HZ / 1000", wardrive)
        cli = text("ESP32C5/components/wifi_cli/wifi_cli.c")
        self.assertIn("if (!BOARD_HAS_RGB_LED) return ESP_OK;", cli)
        main = text("ESP32C5/main/main.c")
        self.assertIn("#if BOARD_HAS_GPS", main)
        self.assertIn("adc_oneshot_io_to_channel(BOARD_BATTERY_ADC_GPIO", main)
        self.assertIn("BOARD_BATTERY_DIVIDER_NUM", main)
        self.assertIn("BOARD_BATTERY_DIVIDER_DEN", main)
        self.assertIn("spi_bus_initialize(BOARD_SD_SPI_HOST", main)
        self.assertNotIn("false && init_battery_adc()", main)

    def test_s3_preserves_canonical_wifi_override_link_policy(self):
        cmake = text("ESP32S3/CMakeLists.txt")
        self.assertIn('idf_build_set_property(LINK_OPTIONS "-Wl,-zmuldefs" APPEND)', cmake)

    def test_release_version_and_four_board_gate(self):
        for project in ("ESP32C5/CMakeLists.txt", "ESP32/CMakeLists.txt", "ESP32S3/CMakeLists.txt"):
            self.assertIn('set(PROJECT_VER "v2.15.29")', text(project))
        makefile = text("Makefile")
        self.assertIn(
            "all-boards: nm-cyd-c5 ws-c5-28 cyd-2432s028 hosyond-s3-35",
            makefile,
        )

    def test_manifest_and_flasher(self):
        manifest_path = ROOT / "ESP32S3/docs/manifest.hosyond-s3-35.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["name"], "CYM Hosyond ES3C35P 3.5 v2.15.29")
        manifest_parts = manifest.get("parts") or manifest["builds"][0]["parts"]
        parts = {item["offset"]: item["path"] for item in manifest_parts}
        self.assertIn(0, parts)
        self.assertIn(0x8000, parts)
        self.assertIn(0x10000, parts)
        flasher = text("ESP32C5/docs/index.html")
        self.assertIn("hosyond-s3-35", flasher)
        self.assertIn("ESP32-S3", flasher)
        self.assertIn("binaries-hosyond-s3-35", flasher)
        self.assertIn('fullBin: "CYM-hosyond-s3-35-full.bin"', flasher)
        self.assertIn('id="dlFull"', flasher)
        self.assertIn(
            'const DEFAULT_BOARD_IDS = ["nm-cyd-c5", "ws-c5-28", "cyd-2432s028", "hosyond-s3-35"]',
            flasher,
        )
        self.assertIn("parts.map(p => ({", flasher)
        workflow = text(".github/workflows/deploy-flasher.yml")
        self.assertIn("ESP32S3/docs/manifest.hosyond-s3-35.json", workflow)
        self.assertIn("ESP32S3/binaries-hosyond-s3-35", workflow)
        self.assertIn("python3 -m json.tool", workflow)
        for full_image in (
            "CYM-NM28C5-full.bin",
            "CYM-WS-C5-28-full.bin",
            "CYM-CYD-2432S028-full.bin",
            "CYM-hosyond-s3-35-full.bin",
        ):
            self.assertIn(full_image, workflow)

if __name__ == "__main__":
    unittest.main()
