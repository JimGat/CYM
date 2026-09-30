"""Regression contracts for Chameleon BLE discovery on BLE 4.2 Classic CYD."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "ESP32C5/main/chameleon_ble.c").read_text(encoding="utf-8")


class ChameleonBleScanContract(unittest.TestCase):
    def test_extended_scan_falls_back_to_legacy_when_controller_returns_enotsup(self):
        self.assertIn("BLE_HS_ENOTSUP", SRC)
        self.assertIn("ble_gap_disc(BLE_OWN_ADDR_PUBLIC", SRC)
        self.assertIn("s_cham_scan_begin", SRC)

    def test_scan_restart_reuses_the_compatible_scan_helper(self):
        start = SRC.index("static int s_scan_gap_cb")
        end = SRC.index("struct ble_hs_adv_fields", start)
        callback_prefix = SRC[start:end]
        self.assertIn("BLE_GAP_EVENT_DISC_COMPLETE", callback_prefix)
        self.assertIn("s_cham_scan_begin()", callback_prefix)

    def test_public_scan_start_uses_the_compatible_scan_helper(self):
        start = SRC.index("void cham_scan_start(void)")
        end = SRC.index("void cham_scan_stop(void)", start)
        self.assertIn("s_cham_scan_begin()", SRC[start:end])


if __name__ == "__main__":
    unittest.main()
