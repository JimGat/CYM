"""Verify the built USB console path, not merely sdkconfig.defaults."""
from pathlib import Path
import json
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

class BuiltConsole(unittest.TestCase):
    def test_primary_usb_stdout_is_linked(self):
        build = ROOT / "build"
        config = (build / "config/sdkconfig.h").read_text()
        self.assertIn("#define CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG 1", config)
        self.assertIn("#define CONFIG_ESP_CONSOLE_SECONDARY_NONE 1", config)
        self.assertIn("#define CONFIG_VFS_SUPPORT_IO 1", config,
                      "Minimal ROM stdout is not the qualified USB VFS console")
        description = json.loads((build / "project_description.json").read_text())
        nm = description["c_compiler"].removesuffix("gcc") + "nm"
        symbols = subprocess.check_output([nm, "--defined-only", str(build / "WS28AudioDiag.elf")], text=True)
        for symbol in ["console_write", "esp_vfs_usb_serial_jtag_get_vfs", "usb_serial_jtag_write"]:
            self.assertIn(symbol, symbols)
        self.assertNotIn("#define CONFIG_ESP_CONSOLE_UART_DEFAULT 1", config)
        self.assertNotIn("#define CONFIG_ESP_CONSOLE_UART_CUSTOM 1", config)

if __name__ == "__main__":
    unittest.main()
