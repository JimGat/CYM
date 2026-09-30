#!/usr/bin/env python3
"""Executable contracts for Chameleon Ultra T5577 payloads and verification."""
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN_DIR = ROOT / "ESP32C5/main"
CODEC_C = MAIN_DIR / "chameleon_t55xx.c"
CODEC_H = MAIN_DIR / "chameleon_t55xx.h"
TRANSPORT_C = MAIN_DIR / "chameleon_ble.c"
TRANSPORT_H = MAIN_DIR / "chameleon_ble.h"
MAIN_C = MAIN_DIR / "main.c"


class ChameleonT55xxCodecTest(unittest.TestCase):
    def test_upstream_payloads_and_semantic_verification(self):
        self.assertTrue(CODEC_C.exists(), "codec implementation is missing")
        self.assertTrue(CODEC_H.exists(), "codec header is missing")
        harness = textwrap.dedent(r'''
            #include <stdbool.h>
            #include <stdint.h>
            #include <stdio.h>
            #include <string.h>
            #include "chameleon_t55xx.h"

            static int expect_bytes(const uint8_t *actual, const uint8_t *expected,
                                    size_t len, const char *name) {
                if (memcmp(actual, expected, len) != 0) {
                    fprintf(stderr, "%s payload mismatch\n", name);
                    return 1;
                }
                return 0;
            }

            int main(void) {
                if (CHAM_CMD_EM410X_WRITE_TO_T55XX != 3001 ||
                    CHAM_CMD_HIDPROX_WRITE_TO_T55XX != 3003) return 10;

                const uint8_t em[5] = {0xDE, 0xAD, 0xBE, 0xEF, 0x88};
                const uint8_t em_expected[17] = {
                    0xDE, 0xAD, 0xBE, 0xEF, 0x88,
                    0x20, 0x20, 0x66, 0x66,
                    0x51, 0x24, 0x36, 0x48,
                    0x19, 0x92, 0x04, 0x27
                };
                uint8_t em_payload[CHAM_T55XX_EM_PAYLOAD_LEN] = {0};
                size_t em_len = 0;
                if (!cham_t55xx_build_em_payload(em, sizeof(em), em_payload,
                                                  sizeof(em_payload), &em_len)) return 11;
                if (em_len != sizeof(em_expected)) return 12;
                if (expect_bytes(em_payload, em_expected, em_len, "EM410x")) return 13;
                if (cham_t55xx_build_em_payload(em, 4, em_payload,
                                                sizeof(em_payload), &em_len)) return 14;
                if (cham_t55xx_build_em_payload(em, sizeof(em), em_payload,
                                                sizeof(em_payload) - 1, &em_len)) return 15;
                if (!cham_t55xx_credential_matches(CHAM_T55XX_CRED_EM410X,
                                                    em, sizeof(em), em, sizeof(em))) return 16;
                uint8_t wrong_em[5];
                memcpy(wrong_em, em, sizeof(em));
                wrong_em[4] ^= 1;
                if (cham_t55xx_credential_matches(CHAM_T55XX_CRED_EM410X,
                                                  em, sizeof(em), wrong_em,
                                                  sizeof(wrong_em))) return 17;

                const uint8_t hid[13] = {
                    0x01, 0x00, 0x00, 0x00, 0x0A,
                    0x00, 0x00, 0x00, 0x04, 0xD2,
                    0x00, 0x00, 0x00
                };
                const uint8_t hid_expected[25] = {
                    0x01, 0x00, 0x00, 0x00, 0x0A,
                    0x00, 0x00, 0x00, 0x04, 0xD2,
                    0x00, 0x00, 0x00,
                    0x20, 0x20, 0x66, 0x66,
                    0x51, 0x24, 0x36, 0x48,
                    0x19, 0x92, 0x04, 0x27
                };
                uint8_t hid_payload[CHAM_T55XX_HID_PAYLOAD_LEN] = {0};
                size_t hid_len = 0;
                if (!cham_t55xx_build_hid_payload(hid, sizeof(hid), hid_payload,
                                                   sizeof(hid_payload), &hid_len)) return 20;
                if (hid_len != sizeof(hid_expected)) return 21;
                if (expect_bytes(hid_payload, hid_expected, hid_len, "HID")) return 22;
                if (cham_t55xx_build_hid_payload(hid, 16, hid_payload,
                                                 sizeof(hid_payload), &hid_len)) return 23;
                if (!cham_t55xx_credential_matches(CHAM_T55XX_CRED_HIDPROX,
                                                    hid, sizeof(hid), hid, sizeof(hid))) return 24;
                uint8_t wrong_hid[13];
                memcpy(wrong_hid, hid, sizeof(hid));
                wrong_hid[9] ^= 1;
                if (cham_t55xx_credential_matches(CHAM_T55XX_CRED_HIDPROX,
                                                  hid, sizeof(hid), wrong_hid,
                                                  sizeof(wrong_hid))) return 25;
                if (cham_t55xx_credential_matches(CHAM_T55XX_CRED_HIDPROX,
                                                  hid, sizeof(hid), hid, 16)) return 26;
                return 0;
            }
        ''')
        with tempfile.TemporaryDirectory(prefix="cym-t55xx-") as td:
            td = Path(td)
            source = td / "codec_test.c"
            binary = td / "codec_test"
            source.write_text(harness)
            build = subprocess.run([
                "gcc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(MAIN_DIR), str(source), str(CODEC_C), "-o", str(binary),
            ], text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_codec_does_not_export_or_log_keys(self):
        self.assertTrue(CODEC_C.exists(), "codec implementation is missing")
        self.assertTrue(CODEC_H.exists(), "codec header is missing")
        header = CODEC_H.read_text()
        source = CODEC_C.read_text()
        self.assertNotIn("get_key", header.lower())
        self.assertNotIn("password", header.lower())
        self.assertNotIn("ESP_LOG", source)
        self.assertNotIn("printf", source)

    def test_codec_is_linked_by_every_shared_main_board(self):
        cmakes = (
            ROOT / "ESP32/main/CMakeLists.txt",
            ROOT / "ESP32C5/main/CMakeLists.txt",
            ROOT / "ESP32S3/main/CMakeLists.txt",
        )
        for cmake in cmakes:
            with self.subTest(cmake=cmake):
                self.assertIn("chameleon_t55xx.c", cmake.read_text())


class ChameleonTransportOutcomeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TRANSPORT_C.read_text()
        cls.header = TRANSPORT_H.read_text()

    def test_transport_exposes_typed_last_command_result(self):
        for symbol in (
            "CHAM_CMD_OUTCOME_SUCCESS", "CHAM_CMD_OUTCOME_PROTOCOL_ERROR",
            "CHAM_CMD_OUTCOME_TIMEOUT", "CHAM_CMD_OUTCOME_DISCONNECTED",
            "CHAM_CMD_OUTCOME_BLE_WRITE_ERROR", "CHAM_CMD_OUTCOME_CANCELLED",
            "cham_cmd_result_info_t", "cham_get_last_cmd_result",
        ):
            self.assertIn(symbol, self.header)
        self.assertIn("uint16_t status", self.header)
        self.assertIn("uint16_t cmd", self.header)

    def test_protocol_status_is_retained_before_callback(self):
        start = self.source.index("if (s_pend_cmd != 0xFFFF && fcmd == s_pend_cmd)")
        end = self.source.index("} else if (s_pend_cmd != 0xFFFF)", start)
        block = self.source[start:end]
        self.assertIn("s_last_result.status = fstatus", block)
        self.assertIn("CHAM_CMD_OUTCOME_PROTOCOL_ERROR", block)
        self.assertLess(block.index("s_last_result.status = fstatus"), block.index("if (cb) cb("))

    def test_timeout_and_ble_write_failure_are_distinct(self):
        self.assertIn("CHAM_CMD_OUTCOME_TIMEOUT", self.source)
        self.assertIn("CHAM_CMD_OUTCOME_BLE_WRITE_ERROR", self.source)

    def test_disconnect_failure_is_delivered_from_poll(self):
        gap_start = self.source.index("case BLE_GAP_EVENT_DISCONNECT:")
        gap_end = self.source.index("break;", gap_start)
        gap = self.source[gap_start:gap_end]
        self.assertNotIn("s_pend_cb      = NULL", gap)
        poll_start = self.source.index("if (s_ev_disconnected)")
        poll_end = self.source.index("if (s_ev_connected)", poll_start)
        poll = self.source[poll_start:poll_end]
        self.assertIn("CHAM_CMD_OUTCOME_DISCONNECTED", poll)
        self.assertIn("if (cb) cb(false, NULL, 0)", poll)

    def test_cancel_detaches_callback_but_drains_outstanding_command(self):
        start = self.source.index("void cham_cancel_pending(void)")
        end = self.source.index("cham_state_t cham_get_state", start)
        block = self.source[start:end]
        self.assertRegex(block, r"s_pend_cb\s*=\s*NULL")
        self.assertNotRegex(block, r"s_pend_cmd\s*=\s*0xFFFF")
        self.assertIn("CHAM_CMD_OUTCOME_CANCELLED", block)


class ChameleonT55xxUiFlowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MAIN_C.read_text()

    def test_physical_clone_is_separate_and_confirmed(self):
        self.assertIn('"Clone T5577"', self.source)
        self.assertIn('"Clone to Slot"', self.source)
        self.assertIn('"Remove source card"', self.source)
        self.assertIn('"Place blank/target T5577"', self.source)
        self.assertIn("s_lf_t55_confirm_cb", self.source)

    def test_write_uses_exact_codec_and_bounded_timeout(self):
        self.assertIn("cham_t55xx_build_em_payload", self.source)
        self.assertIn("cham_t55xx_build_hid_payload", self.source)
        self.assertIn("CHAM_CMD_EM410X_WRITE_TO_T55XX", self.source)
        self.assertIn("CHAM_CMD_HIDPROX_WRITE_TO_T55XX", self.source)
        self.assertIn("5000000LL", self.source)

    def test_verification_is_nonblocking_bounded_and_semantic(self):
        self.assertIn("s_lf_t55_expected", self.source)
        self.assertIn("s_lf_t55_settle_at", self.source)
        self.assertIn("100000LL", self.source)
        self.assertIn("s_lf_t55_verify_deadline", self.source)
        self.assertIn("7000000LL", self.source)
        self.assertIn("CHAM_CMD_EM410X_SCAN", self.source)
        self.assertIn("CHAM_CMD_HIDPROX_SCAN", self.source)
        self.assertIn("cham_t55xx_credential_matches", self.source)
        self.assertIn('"Verified - T5577 matches"', self.source)

    def test_failure_outcomes_and_retries_remain_distinct(self):
        for token in (
            "CHAM_CMD_OUTCOME_BLE_WRITE_ERROR", "CHAM_CMD_OUTCOME_PROTOCOL_ERROR",
            "CHAM_CMD_OUTCOME_TIMEOUT", "CHAM_CMD_OUTCOME_DISCONNECTED",
            '"Unsupported Chameleon firmware"', '"Retry Verify"',
            '"Retry Write"', '"Cancel"', '"Verification mismatch"',
            '"No tag found during verification"',
        ):
            self.assertIn(token, self.source)

    def test_stop_hook_cancels_and_clears_physical_clone_ui(self):
        start = self.source.index("static void cham_lf_read_stop(void)")
        end = self.source.index("/* ─────────────────", start)
        block = self.source[start:end]
        self.assertIn("cham_cancel_pending()", block)
        self.assertIn("s_lf_t55_popup", block)
        self.assertIn("s_lf_t55_btn", block)


if __name__ == "__main__":
    unittest.main()
