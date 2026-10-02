#!/usr/bin/env python3
"""Contract for the standalone Classic CYD GPS electrical diagnostic."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "ClassicCYDgpsTest"
MAIN = TOOL / "main" / "ClassicCYDgpsTest.c"


class ClassicCydGpsTestToolContract(unittest.TestCase):
    def test_project_files_exist(self):
        required = [
            TOOL / "CMakeLists.txt", TOOL / "sdkconfig.defaults",
            TOOL / "partitions.csv", TOOL / "README.md", TOOL / "build.sh",
            TOOL / "main" / "CMakeLists.txt", MAIN,
        ]
        self.assertTrue(all(path.is_file() for path in required))

    def test_scans_expected_receive_pins_and_bauds(self):
        source = MAIN.read_text()
        for pin in (1, 3, 26):
            self.assertIn(f"GPIO_NUM_{pin}", source)
        for baud in (9600, 38400, 115200):
            self.assertIn(str(baud), source)
        self.assertIn("UART_NUM_2", source)
        self.assertIn("UART_PIN_NO_CHANGE", source)
        self.assertNotIn("uart_write_bytes", source)

    def test_scan_reset_preserves_selected_pin_and_baud(self):
        source = MAIN.read_text()
        self.assertIn("gpio_num_t selected_pin = r->pin;", source)
        self.assertIn("int selected_baud = r->baud;", source)
        self.assertIn("r->pin = selected_pin;", source)
        self.assertIn("r->baud = selected_baud;", source)

    def test_reports_uart_and_nmea_evidence_on_screen(self):
        source = MAIN.read_text()
        for event in ("UART_FIFO_OVF", "UART_BUFFER_FULL", "UART_BREAK",
                      "UART_PARITY_ERR", "UART_FRAME_ERR"):
            self.assertIn(event, source)
        for metric in ("bytes", "frame_errors", "parity_errors", "dollar_count",
                       "line_count", "valid_checksums", "sample_hex"):
            self.assertIn(metric, source)
        self.assertIn("FOUND RX GPIO", source)
        self.assertIn("NO UART BYTES", source)

    def test_console_and_boot_logs_are_disabled(self):
        config = (TOOL / "sdkconfig.defaults").read_text()
        self.assertIn("CONFIG_ESP_CONSOLE_NONE=y", config)
        self.assertIn("CONFIG_BOOTLOADER_LOG_LEVEL_NONE=y", config)

    def test_full_image_packaging_is_explicit(self):
        build = (TOOL / "build.sh").read_text()
        self.assertIn("merge-bin", build)
        for offset in ("0x1000", "0x8000", "0x10000"):
            self.assertIn(offset, build)
        self.assertIn("ClassicCYDgpsTest-full.bin", build)


if __name__ == "__main__":
    unittest.main()
