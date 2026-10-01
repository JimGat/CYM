#!/usr/bin/env python3
"""Contracts for Classic CYD external GPS on the P1 UART expansion JST."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "ESP32C5" / "main" / "main.c").read_text()
BOARD = (ROOT / "ESP32C5/components/board_hal/include/boards/cyd2usb.h").read_text()
README = (ROOT / "README.md").read_text()
CLOCK = (ROOT / "docs/hardware/universal-clock.md").read_text()
GUIDE_PATH = ROOT / "docs/hardware/classic-cyd-gps.md"
DOC = GUIDE_PATH.read_text()


class ClassicCydGpsBoardContract(unittest.TestCase):
    def test_uart_expansion_jst_is_the_gps_uart(self):
        self.assertRegex(BOARD, r"BOARD_HAS_GPS\s+1")
        self.assertRegex(BOARD, r"BOARD_GPS_UART_NUM\s+UART_NUM_1")
        self.assertRegex(BOARD, r"BOARD_GPS_TX_GPIO\s+1")
        self.assertRegex(BOARD, r"BOARD_GPS_RX_GPIO\s+3")

    def test_classic_rx_pin_is_input_before_uart1_attach(self):
        # GPIO3 is the reversed Classic UART1 RX path. Establish input mode
        # explicitly before attaching the UART input matrix.
        self.assertRegex(
            MAIN,
            r"#if defined\(CONFIG_BOARD_CYD2USB\)\s+"
            r"(?:/\*.*?\*/|//[^\n]*\n|\s)*"
            r"if \(\(err = gpio_set_direction\(\(gpio_num_t\)GPS_RX_PIN, GPIO_MODE_INPUT\)\) != ESP_OK\) return err;\s+"
            r"#endif\s+if \(\(err = uart_set_pin",
        )

    def test_gps_preserves_rf_hat_control_pins(self):
        def value(name):
            match = re.search(rf"#define\s+{name}\s+(\d+)", BOARD)
            self.assertIsNotNone(match, name)
            return int(match.group(1))
        self.assertEqual(value("BOARD_RFHAT_PIN_A"), 22)
        self.assertEqual(value("BOARD_RFHAT_PIN_B"), 27)
        self.assertTrue({value("BOARD_GPS_TX_GPIO"), value("BOARD_GPS_RX_GPIO")}.isdisjoint(
            {value("BOARD_RFHAT_PIN_A"), value("BOARD_RFHAT_PIN_B")}))

    def test_classic_console_does_not_use_uart_jst(self):
        defaults = (ROOT / "ESP32/sdkconfig.defaults.cyd2usb").read_text()
        self.assertIn("CONFIG_ESP_CONSOLE_NONE=y", defaults)
        self.assertIn("# CONFIG_ESP_CONSOLE_UART_DEFAULT is not set", defaults)
        self.assertIn("CONFIG_BOOTLOADER_LOG_LEVEL_NONE=y", defaults)

    def test_documentation_separates_primary_and_expansion_ports(self):
        self.assertIn("primary USB-C", DOC)
        self.assertIn("second Micro-USB", DOC)
        self.assertIn("must not carry CYM logs", DOC)
        self.assertIn("GPS TX", DOC)
        self.assertIn("GPIO1", DOC)

    def test_console_helper_honors_console_none_profiles(self):
        source = (ROOT / "ESP32C5/components/wifi_cli/wifi_cli.c").read_text()
        self.assertRegex(
            source,
            r"esp_err_t wifi_cli_start_console\(void\) \{\s*#if CONFIG_ESP_CONSOLE_NONE\s*return ESP_ERR_NOT_SUPPORTED;",
        )

    def test_timekeeper_exposes_classic_gps_capability(self):
        self.assertRegex(BOARD, r"BOARD_TIME_HAS_GPS_UART\s+1")
        self.assertRegex(BOARD, r"BOARD_TIME_GPS_UNCERTAINTY_US\s+500000")
        self.assertRegex(BOARD, r"BOARD_TIME_GPS_RTC_UNCERTAINTY_US\s+2000000")
        self.assertRegex(BOARD, r"BOARD_TIME_GPS_RTC_DRIFT_PPM\s+100")


class ClassicCydGpsDocumentationContract(unittest.TestCase):
    def test_readme_describes_external_gps_instead_of_no_gps(self):
        row = next(line for line in README.splitlines() if "**Classic CYD**" in line)
        self.assertNotIn("no GPS", row)
        self.assertIn("external GPS", row)
        self.assertIn("P1 UART expansion JST", row)

    def test_wiring_guide_documents_console_and_gps_connections(self):
        self.assertTrue(GUIDE_PATH.exists(), "Classic CYD GPS wiring guide must exist")
        guide = GUIDE_PATH.read_text() if GUIDE_PATH.exists() else ""
        for text in ("primary USB-C", "second Micro-USB", "P1 UART expansion JST",
                     "GPIO1", "GPIO3", "GPS TX", "GPS RX", "ATGM336H",
                     "onboard voltage regulator", "accepts either supply",
                     "power-interchangeable"):
            self.assertIn(text, guide)
        self.assertIn("GPS TX to P1 RX/GPIO3", guide)
        self.assertIn("RX on GPIO3 and TX on GPIO1", guide)

    def test_universal_clock_no_longer_claims_classic_has_no_gps(self):
        row = next(line for line in CLOCK.splitlines() if "Classic CYD RTOS holdover" in line)
        self.assertNotIn("no supported GPS UART", row)
        self.assertIn("external GPS", row)


if __name__ == "__main__":
    unittest.main()
