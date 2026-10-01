#!/usr/bin/env python3
"""Cross-board source contracts for the universal capability-aware Clock."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "ESP32C5/main/main.c").read_text()
TK_H = (ROOT / "ESP32C5/components/cym_timekeeper/include/cym_timekeeper.h").read_text()
TK_C = (ROOT / "ESP32C5/components/cym_timekeeper/cym_timekeeper.c").read_text()
NTP_C = (ROOT / "ESP32C5/components/cym_timekeeper/cym_ntp_server.c").read_text()
HAL_H = (ROOT / "ESP32C5/components/board_hal/include/board_hal.h").read_text()
BOARDS = ROOT / "ESP32C5/components/board_hal/include/boards"


def section(start, end):
    assert start in MAIN, start
    i = MAIN.index(start)
    assert end in MAIN[i + len(start):], end
    return MAIN[i:MAIN.index(end, i + len(start))]


class BoardProfileContract(unittest.TestCase):
    expected = {
        "ws_c5_28.h": (1, 1, 50, 100, 500000, 250000, 2000000, 100, 1),
        "nm_cyd_c5.h": (0, 1, 0, 100, 500000, 250000, 2000000, 100, 1),
        "cyd2usb.h": (0, 1, 0, 150, 500000, 250000, 2000000, 100, 0),
        "hosyond_s3_35.h": (0, 1, 0, 100, 500000, 250000, 2000000, 100, 1),
    }
    symbols = (
        "BOARD_TIME_HAS_RTC", "BOARD_TIME_HAS_GPS_UART",
        "BOARD_TIME_RTC_DRIFT_PPM", "BOARD_TIME_RTOS_DRIFT_PPM",
        "BOARD_TIME_GPS_UNCERTAINTY_US", "BOARD_TIME_NTP_UNCERTAINTY_US",
        "BOARD_TIME_GPS_RTC_UNCERTAINTY_US", "BOARD_TIME_GPS_RTC_DRIFT_PPM",
        "BOARD_TIME_HAS_MDNS", "BOARD_TIME_ESTIMATE_CHARACTERIZED",
    )

    def _value(self, text, name):
        m = re.search(rf"#define\s+{name}\s+(\d+)", text)
        self.assertIsNotNone(m, f"missing {name}")
        return int(m.group(1))

    def test_each_release_board_has_explicit_profile(self):
        names = self.symbols[:-1]
        for filename, values in self.expected.items():
            text = (BOARDS / filename).read_text()
            self.assertEqual(tuple(self._value(text, n) for n in names), values, filename)
            self.assertEqual(self._value(text, "BOARD_TIME_ESTIMATE_CHARACTERIZED"), 0, filename)

    def test_only_ws_has_rtc_address(self):
        for filename in self.expected:
            text = (BOARDS / filename).read_text()
            self.assertEqual("BOARD_RTC_I2C_ADDR" in text, filename == "ws_c5_28.h")

    def test_cyd_routes_gps_to_uart_expansion_jst(self):
        text = (BOARDS / "cyd2usb.h").read_text()
        self.assertRegex(text, r"BOARD_GPS_UART_NUM\s+UART_NUM_1")
        self.assertRegex(text, r"BOARD_GPS_TX_GPIO\s+1")
        self.assertRegex(text, r"BOARD_GPS_RX_GPIO\s+3")

    def test_normalized_fallbacks_and_sanity_checks_exist(self):
        for symbol in self.symbols:
            self.assertIn(symbol, HAL_H)
        self.assertIn("BOARD_RTC_I2C_ADDR", HAL_H)
        self.assertIn("#error", HAL_H)


class TimekeeperContract(unittest.TestCase):
    def test_source_and_reliability_enums(self):
        self.assertIn("CYM_TIME_RTOS_HOLDOVER", TK_H)
        self.assertIn("CYM_TIME_NTP_HOLDOVER", TK_H)
        self.assertIn("CYM_TIME_GPS_RTC_HOLDOVER", TK_H)
        for value in ("UNTRUSTED", "DEGRADED", "HOLDOVER", "GOOD", "EXCELLENT"):
            self.assertIn("CYM_TIME_RELIABILITY_" + value, TK_H)

    def test_snapshot_has_capability_and_reliability_fields(self):
        for field in ("reliability", "has_rtc", "has_gps_uart", "estimate_characterized"):
            self.assertRegex(TK_H, rf"\b{field}\b")
        self.assertIn("cym_timekeeper_reliability_name", TK_H)

    def test_uncertainty_uses_board_profile(self):
        self.assertIn("grow_uncertainty", TK_C)
        self.assertIn("BOARD_TIME_RTC_DRIFT_PPM", TK_C)
        self.assertIn("BOARD_TIME_RTOS_DRIFT_PPM", TK_C)
        self.assertIn("BOARD_TIME_GPS_UNCERTAINTY_US", TK_C)
        self.assertIn("BOARD_TIME_NTP_UNCERTAINTY_US", TK_C)

    def test_no_rtc_gps_loss_enters_rtos_holdover(self):
        self.assertRegex(TK_C, re.compile(r"GPS_LOSS_TIMEOUT.*?CYM_TIME_RTOS_HOLDOVER", re.S))

    def test_no_fix_gps_rtc_has_separate_cross_validated_path(self):
        self.assertIn("cym_timekeeper_observe_gps_rtc_utc", TK_H)
        self.assertIn("CYM_TIME_GPS_RTC_HOLDOVER", TK_C)
        self.assertIn("s_gps_rtc_trusted", TK_C)
        self.assertIn("GPS_RTC_CROSSCHECK_MAX_ERROR_S", TK_C)
        self.assertIn("BOARD_TIME_GPS_RTC_UNCERTAINTY_US", TK_C)
        self.assertIn("BOARD_TIME_GPS_RTC_DRIFT_PPM", TK_C)
        self.assertIn("GPS RTC moved backwards past its last trusted epoch", TK_C)
        self.assertIn("revoke_gps_rtc_trust", TK_C)
        self.assertRegex(TK_C, re.compile(
            r"GPS RTC discontinuity.*?revoke_gps_rtc_trust", re.S))
        self.assertRegex(TK_C, re.compile(
            r"revoke_gps_rtc_trust.*?CYM_TIME_GPS_RTC_HOLDOVER.*?CYM_TIME_RTOS_HOLDOVER",
            re.S))
        observer = TK_C[TK_C.index("esp_err_t cym_timekeeper_observe_gps_rtc_utc"):TK_C.index("esp_err_t cym_timekeeper_observe_network_utc")]
        self.assertRegex(observer, re.compile(
            r"may_take_over.*?CYM_TIME_NTP_HOLDOVER.*?CYM_TIME_GPS_RTC_HOLDOVER",
            re.S))

    def test_network_expiry_preserves_ntp_lineage(self):
        self.assertIn("CYM_TIME_NTP_HOLDOVER", TK_C)
        self.assertRegex(TK_C, re.compile(
            r"s_source == CYM_TIME_NETWORK_SYNC.*?CYM_TIME_GPS_RTC_HOLDOVER.*?CYM_TIME_NTP_HOLDOVER",
            re.S))

    def test_reliability_boundaries_are_explicit(self):
        self.assertIn("1000000", TK_C)
        self.assertIn("2000000", TK_C)
        self.assertIn("CYM_TIME_RELIABILITY_EXCELLENT", TK_C)
        self.assertIn("CYM_TIME_RELIABILITY_GOOD", TK_C)


class NTPQualityContract(unittest.TestCase):
    def test_rtos_holdover_is_served_as_synchronized(self):
        self.assertIn("CYM_TIME_RTOS_HOLDOVER", NTP_C)
        self.assertRegex(NTP_C, re.compile(r"CYM_TIME_RTOS_HOLDOVER.*?NTP_STRATUM_SECONDARY", re.S))

    def test_untrusted_is_leap_alarm_stratum_16(self):
        self.assertIn("NTP_LI_ALARM", NTP_C)
        self.assertIn("NTP_STRATUM_UNSYNC", NTP_C)


class BuildIntegrationContract(unittest.TestCase):
    def test_all_application_components_link_timekeeper(self):
        for rel in ("ESP32/main/CMakeLists.txt", "ESP32C5/main/CMakeLists.txt", "ESP32S3/main/CMakeLists.txt"):
            self.assertIn("cym_timekeeper", (ROOT / rel).read_text(), rel)

    def test_sntp_header_is_universal(self):
        include = '#include "esp_netif_sntp.h"'
        self.assertIn(include, MAIN)
        prefix = MAIN[max(0, MAIN.index(include) - 100):MAIN.index(include)]
        self.assertNotIn("CONFIG_BOARD_WS_C5_28", prefix)

    def test_mdns_is_omitted_from_constrained_cyd_build(self):
        self.assertNotIn("espressif/mdns", (ROOT / "ESP32/main/idf_component.yml").read_text())
        for rel in ("ESP32C5/main/idf_component.yml", "ESP32S3/main/idf_component.yml"):
            self.assertIn("espressif/mdns", (ROOT / rel).read_text(), rel)
        include = '#include "mdns.h"'
        prefix = MAIN[max(0, MAIN.index(include) - 100):MAIN.index(include)]
        self.assertIn("BOARD_TIME_HAS_MDNS", prefix)

    def test_timekeeper_initializes_every_board(self):
        block = section("void app_main(void)", "// Main loop")
        self.assertIn("cym_timekeeper_init", block)
        self.assertIn("BOARD_TIME_HAS_RTC", block)
        self.assertIn("cym_timekeeper_init(NULL)", block)

    def test_gps_observation_is_capability_gated(self):
        start = MAIN.index("static bool parse_gps_nmea(const char *nmea_sentence)\n{")
        end = MAIN.index("static void gps_task", start)
        parser = MAIN[start:end]
        self.assertIn("BOARD_TIME_HAS_GPS_UART", parser)
        self.assertNotIn("CONFIG_BOARD_WS_C5_28", parser)

    def test_void_rmc_time_is_offered_to_gps_rtc_holdover(self):
        parser = section("static bool parse_gps_nmea(const char *nmea_sentence)\n{", "static void gps_task")
        self.assertRegex(parser, re.compile(
            r"status == 'A' \|\| status == 'V'.*?cym_timekeeper_observe_gps_rtc_utc",
            re.S))
        rmc = parser[parser.index("// Parse GPRMC/GNRMC"):]
        self.assertIn("char *cursor = sentence", rmc)
        self.assertIn("strchr(cursor, ',')", rmc)
        self.assertNotIn('strtok_r(sentence, ",", &sp)', rmc)

    def test_client_mode_refreshes_public_ntp_every_minute(self):
        task = section("static void clock_wifi_task(void *arg)\n{", "static bool maidenhead6")
        self.assertIn("NTP_PUBLIC_REFRESH_INTERVAL_MS", MAIN)
        self.assertRegex(MAIN, r"#define\s+NTP_PUBLIC_REFRESH_INTERVAL_MS\s+60000")
        self.assertGreaterEqual(task.count("clock_try_public_sync();"), 2)
        self.assertIn("while (!s_ntp_stopping", task)

    def test_clock_distinguishes_ntp_and_gps_rtc_holdover(self):
        ui = section("static void clock_ui_timer_cb(lv_timer_t *timer)\n{", "static void clock_retry_cb")
        self.assertIn('badge = "NTP HOLDOVER"', ui)
        self.assertIn('badge = "GPS RTC HOLDOVER"', ui)
        self.assertIn("0xFFD740", ui)
        self.assertIn('"Public NTP: synchronized"', ui)


class NavigationContract(unittest.TestCase):
    def test_classic_has_universal_clock(self):
        block = section("static void show_main_tiles(void)\n{", "// ── WiFi Scan paginated list renderer")
        self.assertIn('"Clock"', block)
        self.assertIn('"Clock Classic"', block)
        self.assertNotIn("CONFIG_BOARD_WS_C5_28", block)
        self.assertNotIn('"NTP\\nClock"', block)

    def test_modern_has_universal_clock(self):
        block = section("static void show_cat_tools(void)\n{", "static void category_tile_event_cb")
        self.assertIn('"Clock"', block)
        self.assertIn('"Clock Modern"', block)
        self.assertNotIn("CONFIG_BOARD_WS_C5_28", block)
        self.assertNotIn('"NTP\\nClock"', block)


class ModeContract(unittest.TestCase):
    def test_chooser_has_four_choices(self):
        block = section("static void show_clock_mode_popup", "static void show_clock_screen")
        for label in ("Display Only", "Client NTP", "AP NTP", "Cancel"):
            self.assertIn(f'"{label}"', block)

    def test_display_callback_is_offline(self):
        block = section("static void clock_mode_display_cb", "static void clock_mode_client_cb")
        self.assertIn("CLOCK_MODE_DISPLAY_ONLY", block)
        self.assertIn("show_clock_screen", block)
        for forbidden in ("esp_wifi_", "esp_netif_", "esp_sntp_", "mdns_", "cym_ntp_server_start"):
            self.assertNotIn(forbidden, block)

    def test_client_wifi_handoff_is_universal(self):
        poll = section("static void s_fileserv_poll_ip_cb", "static void fileserv_stop")
        self.assertIn("s_ntp_pending_after_wifi", poll)
        self.assertIn("show_clock_screen();", poll)
        self.assertNotIn("CONFIG_BOARD_WS_C5_28", poll)

        wifi_screen = section("static void show_wifi_client_server_screen(void)\n{", "static void wdup_push_msg")
        self.assertIn('"WiFi for NTP Clock"', wifi_screen)
        self.assertIn("s_ntp_return_fn", wifi_screen)
        self.assertNotIn("CONFIG_BOARD_WS_C5_28", wifi_screen)

    def test_mode_is_not_persisted(self):
        self.assertNotRegex(MAIN, r'NVS_KEY_[A-Z_]*CLOCK_MODE|nvs_set_\w+\([^\n]*clock_mode')


class DashboardContract(unittest.TestCase):
    def test_dashboard_has_truthful_status_fields(self):
        block = section("static void show_clock_screen(void)\n{", "static void show_clock_settings_screen")
        for label in ("Reliability", "Estimated uncertainty", "Source age", "RTC: not fitted", "GPS: not supported", "estimated (unqualified)"):
            self.assertIn(label, block)
        timer = section("static void clock_ui_timer_cb", "static void clock_exit_cb")
        self.assertIn("cym_timekeeper_reliability_name", timer)

    def test_display_offset_is_presentation_only(self):
        block = section("static void clock_ui_timer_cb", "static void clock_exit_cb")
        self.assertIn("g_clock_offset_minutes", block)
        self.assertNotIn("settimeofday", block)
        self.assertNotIn("cym_timekeeper_observe", block)

    def test_clock_shows_six_character_maidenhead_grid_below_time(self):
        helper = section("static bool maidenhead6", "static void clock_ui_timer_cb")
        for token in ("lon + 180.0", "lat + 90.0", "x / 20.0", "y / 10.0",
                      "x / 2.0", "x * 12.0", "y * 24.0", "out[6] = '\\0'"):
            self.assertIn(token, helper)

        timer = section("static void clock_ui_timer_cb", "static void clock_exit_cb")
        for token in ("s_clock_maidenhead_lbl", "current_gps.valid",
                      "current_gps.latitude", "current_gps.longitude", '"Grid: %s"'):
            self.assertIn(token, timer)

        dashboard = section("static void show_clock_screen(void)\n{", "static void show_clock_settings_screen")
        self.assertLess(dashboard.index("s_ntp_date_lbl ="), dashboard.index("s_clock_maidenhead_lbl ="))
        self.assertLess(dashboard.index("s_clock_maidenhead_lbl ="), dashboard.index("s_ntp_offset_lbl ="))


class NetworkLifecycleContract(unittest.TestCase):
    def test_client_sync_is_bounded_and_disciplines_timekeeper(self):
        block = section("static void clock_try_public_sync", "static void clock_wifi_task")
        self.assertIn("NTP_PUBLIC_SYNC_TIMEOUT_MS", block)
        self.assertIn("cym_timekeeper_observe_network_utc", block)
        self.assertIn('ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org")', block)

    def test_ap_path_has_no_public_sntp(self):
        helper = section("static bool ntp_start_ap_mode", "static void clock_wifi_task")
        task = section("static void clock_wifi_task", "static void clock_ui_timer_cb")
        ap = task[task.index("CLOCK_MODE_AP_NTP"):task.index("if (g_saved_wifi_ssid")]
        self.assertIn("WIFI_MODE_AP", helper)
        self.assertIn("ntp_start_mdns_and_server", helper)
        service = section("static void ntp_start_mdns_and_server", "static void clock_try_public_sync")
        self.assertIn("cym_ntp_server_start", service)
        self.assertIn("ntp_start_ap_mode", ap)
        self.assertNotIn("ESP_NETIF_SNTP_DEFAULT_CONFIG", helper + ap)


class SettingsContract(unittest.TestCase):
    def test_clock_settings_are_universal(self):
        load = section("static void nvs_settings_load(void)", "static void nvs_settings_save_timeout")
        self.assertIn("NVS_KEY_CLK_OFFSET", load)
        self.assertNotRegex(load, re.compile(r"CONFIG_BOARD_WS_C5_28.*?NVS_KEY_CLK_OFFSET", re.S))
        routing = section("static void settings_tile_event_cb(lv_event_t *e)\n{", "// Settings screen")
        self.assertIn('strcmp(tile_name, "Clock")', routing)
        clock_route = routing[routing.index('strcmp(tile_name, "Clock")') - 120:routing.index('strcmp(tile_name, "Clock")') + 160]
        self.assertNotIn("CONFIG_BOARD_WS_C5_28", clock_route)


class DocumentationContract(unittest.TestCase):
    def test_operator_document_exists_and_disclaims_estimates(self):
        p = ROOT / "docs/hardware/universal-clock.md"
        self.assertTrue(p.exists())
        text = p.read_text()
        self.assertIn("Timing values are conservative uncharacterized engineering estimates, not measured accuracy.", text)
        for value in ("Display Only", "Client NTP", "AP NTP", "Maidenhead",
                      "60 seconds", "GPS RTC Holdover", "cross-validated",
                      "WS-C5-28", "NM-CYD-C5", "CYD-2432S028", "Hosyond ES3C35P"):
            self.assertIn(value, text)


class ReleaseVersionContract(unittest.TestCase):
    def test_all_release_versions_are_v21542(self):
        for rel in ("ESP32/CMakeLists.txt", "ESP32C5/CMakeLists.txt", "ESP32S3/CMakeLists.txt"):
            self.assertIn('set(PROJECT_VER "v2.15.50")', (ROOT / rel).read_text(), rel)
        for rel in ("ESP32/docs/manifest.cyd-2432s028.json", "ESP32C5/docs/manifest.json", "ESP32C5/docs/manifest.ws-c5-28.json", "ESP32C5/docs/manifest.pancake-c5.json", "ESP32S3/docs/manifest.hosyond-s3-35.json"):
            self.assertIn("v2.15.50", (ROOT / rel).read_text(), rel)


if __name__ == "__main__":
    unittest.main()
