#!/usr/bin/env python3
"""Boot-safety contract for Classic CYD's discrete RGB LED."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ClassicRgbLedBootContract(unittest.TestCase):
    def test_cyd2usb_never_enters_ws2812_rmt_initialization(self):
        board = (ROOT / 'ESP32C5/components/board_hal/include/boards/cyd2usb.h').read_text()
        self.assertIn('#define BOARD_RGB_LED_GPIO      -1', board)
        self.assertIn('#define BOARD_RGB_LED_COUNT      0', board)
        cli = (ROOT / 'ESP32C5/components/wifi_cli/wifi_cli.c').read_text()
        start = cli.index('esp_err_t init_led(void)')
        end = cli.index('esp_err_t wifi_cli_init(void)', start)
        body = cli[start:end]
        guard = 'if (BOARD_RGB_LED_COUNT <= 0 || BOARD_RGB_LED_GPIO < 0) return ESP_OK;'
        self.assertIn(guard, body)
        self.assertLess(body.index(guard), body.index('led_strip_new_rmt_device'))
        self.assertNotIn('ESP_ERROR_CHECK(led_strip_new_rmt_device', body)

if __name__ == '__main__':
    unittest.main()
