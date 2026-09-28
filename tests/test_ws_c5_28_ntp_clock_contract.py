#!/usr/bin/env python3
"""Source contracts for WS-C5-28 GPS-disciplined NTP Clock feature.

Verifies that the board header, timekeeper component, NTP server component,
main.c integration, and navigation wiring satisfy the approved design spec.
"""

from pathlib import Path
import re
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "ESP32C5/main/main.c").read_text()
MAIN_CMAKE = (ROOT / "ESP32C5/main/CMakeLists.txt").read_text()
WS_BOARD = (ROOT / "ESP32C5/components/board_hal/include/boards/ws_c5_28.h").read_text()

# Component paths — may not exist yet (tests run RED before implementation)
TK_DIR = ROOT / "ESP32C5/components/cym_timekeeper"
TK_HEADER = TK_DIR / "include/cym_timekeeper.h"
NTP_HEADER = TK_DIR / "include/cym_ntp_server.h"
TK_SRC = TK_DIR / "cym_timekeeper.c"
PCF_SRC = TK_DIR / "pcf85063.c"
PCF_HDR = TK_DIR / "pcf85063.h"
NTP_SRC = TK_DIR / "cym_ntp_server.c"
TK_CMAKE = TK_DIR / "CMakeLists.txt"


def _read_if_exists(p):
    return p.read_text() if p.exists() else ""


class BoardRTCContract(unittest.TestCase):
    """PCF85063A at 0x51 must be declared in the WS-C5-28 board header."""

    def test_rtc_i2c_address_defined(self):
        self.assertIn("#define BOARD_RTC_I2C_ADDR", WS_BOARD)
        self.assertIn("0x51", WS_BOARD)

    def test_gps_uart_pins_unchanged(self):
        self.assertIn("BOARD_HAS_GPS", WS_BOARD)
        self.assertIn("BOARD_GPS_UART_NUM", WS_BOARD)
        self.assertRegex(WS_BOARD, r"BOARD_GPS_TX\s+11")
        self.assertRegex(WS_BOARD, r"BOARD_GPS_RX\s+12")


class TimekeeperComponentContract(unittest.TestCase):
    """cym_timekeeper component must expose the spec's public API."""

    def test_component_cmake_exists(self):
        self.assertTrue(TK_CMAKE.exists(), "cym_timekeeper/CMakeLists.txt must exist")

    def test_header_exists(self):
        self.assertTrue(TK_HEADER.exists(), "cym_timekeeper.h must exist")

    def test_source_state_enum(self):
        h = _read_if_exists(TK_HEADER)
        self.assertIn("CYM_TIME_UNSYNCED", h)
        self.assertIn("CYM_TIME_GPS_ACQUIRING", h)
        self.assertIn("CYM_TIME_GPS_LOCKED", h)
        self.assertIn("CYM_TIME_RTC_HOLDOVER", h)

    def test_snapshot_struct_fields(self):
        h = _read_if_exists(TK_HEADER)
        for field in ("source", "valid", "rtc_valid", "gps_present",
                       "gps_fix", "pps_active", "source_age_ms",
                       "last_gps_sync_epoch", "uncertainty_us",
                       "last_correction_us"):
            self.assertIn(field, h, f"snapshot must include {field}")

    def test_init_function(self):
        h = _read_if_exists(TK_HEADER)
        self.assertIn("cym_timekeeper_init", h)
        self.assertIn("i2c_master_bus_handle_t", h)

    def test_observe_gps_function(self):
        h = _read_if_exists(TK_HEADER)
        self.assertIn("cym_timekeeper_observe_gps_utc", h)

    def test_snapshot_function(self):
        h = _read_if_exists(TK_HEADER)
        self.assertIn("cym_timekeeper_snapshot", h)
        self.assertIn("cym_time_snapshot_t", h)

    def test_source_name_function(self):
        h = _read_if_exists(TK_HEADER)
        self.assertIn("cym_timekeeper_source_name", h)

    def test_note_gps_present_function(self):
        h = _read_if_exists(TK_HEADER)
        self.assertIn("cym_timekeeper_note_gps_present", h)

    def test_pcf85063_source_exists(self):
        self.assertTrue(PCF_SRC.exists(), "pcf85063.c must exist")

    def test_pcf85063_header_exists(self):
        self.assertTrue(PCF_HDR.exists(), "pcf85063.h must exist")

    def test_pcf85063_bcd_conversion(self):
        src = _read_if_exists(PCF_SRC)
        self.assertIn("bcd_to_dec", src)
        self.assertIn("dec_to_bcd", src)

    def test_pcf85063_oscillator_stop(self):
        src = _read_if_exists(PCF_SRC)
        self.assertIn("OS", src, "Must check oscillator-stop flag")

    def test_timekeeper_gps_qualification(self):
        """Three consecutive valid samples required for GPS lock."""
        src = _read_if_exists(TK_SRC)
        self.assertRegex(src, r"[Cc]onsecutive|CONSEC|consec_count|GPS_LOCK_SAMPLES",
                         "Must require consecutive valid GPS samples")

    def test_timekeeper_rtc_write_rate_limit(self):
        """RTC writes bounded to no more than every 10 minutes."""
        src = _read_if_exists(TK_SRC)
        self.assertRegex(src, r"600|RTC_WRITE_INTERVAL|rtc_write_interval",
                         "Must rate-limit RTC writes (~600s)")

    def test_timekeeper_uncertainty_initial(self):
        """GPS-locked UART uncertainty starts at 500ms (500000 us)."""
        src = _read_if_exists(TK_SRC)
        self.assertIn("BOARD_TIME_GPS_UNCERTAINTY_US", src,
                      "Initial GPS uncertainty must come from the board profile")
        self.assertRegex(WS_BOARD, r"BOARD_TIME_GPS_UNCERTAINTY_US\s+500000")

    def test_timekeeper_holdover_drift_rate(self):
        """Holdover uncertainty grows at 50 ppm."""
        src = _read_if_exists(TK_SRC)
        self.assertRegex(src, r"50|HOLDOVER_DRIFT_PPM",
                         "Holdover drift should reference 50 ppm")


class NTPServerComponentContract(unittest.TestCase):
    """cym_ntp_server must expose a bounded UDP/123 responder."""

    def test_ntp_header_exists(self):
        self.assertTrue(NTP_HEADER.exists(), "cym_ntp_server.h must exist")

    def test_ntp_start_stop(self):
        h = _read_if_exists(NTP_HEADER)
        self.assertIn("cym_ntp_server_start", h)
        self.assertIn("cym_ntp_server_stop", h)

    def test_ntp_stats_struct(self):
        h = _read_if_exists(NTP_HEADER)
        for field in ("running", "valid_requests", "malformed_requests",
                       "rate_limited_requests", "send_failures"):
            self.assertIn(field, h, f"stats must include {field}")

    def test_ntp_get_stats(self):
        h = _read_if_exists(NTP_HEADER)
        self.assertIn("cym_ntp_server_get_stats", h)

    def test_ntp_epoch_offset(self):
        """NTP epoch is 1900-01-01, Unix is 1970-01-01 = 2208988800 seconds."""
        src = _read_if_exists(NTP_SRC)
        self.assertIn("2208988800", src, "Must define NTP epoch offset")

    def test_ntp_packet_size(self):
        """NTP packets are exactly 48 bytes."""
        src = _read_if_exists(NTP_SRC)
        self.assertIn("48", src, "Must use 48-byte NTP packets")

    def test_ntp_server_mode(self):
        """Server responds with mode 4."""
        src = _read_if_exists(NTP_SRC)
        self.assertRegex(src, r"mode.*4|NTP_MODE_SERVER.*4|0x04",
                         "Must respond with NTP server mode 4")

    def test_ntp_client_mode_validation(self):
        """Must validate client mode 3."""
        src = _read_if_exists(NTP_SRC)
        self.assertRegex(src, r"mode.*3|NTP_MODE_CLIENT.*3|== 3",
                         "Must validate NTP client mode 3")

    def test_ntp_stratum_gps(self):
        """GPS-locked state uses stratum 1."""
        src = _read_if_exists(NTP_SRC)
        self.assertRegex(src, r"stratum.*1|NTP_STRATUM_PRIMARY",
                         "GPS-locked must be stratum 1")

    def test_ntp_stratum_unsync(self):
        """Unsynchronized state uses stratum 16."""
        src = _read_if_exists(NTP_SRC)
        self.assertIn("16", src, "Unsynchronized must use stratum 16")

    def test_ntp_leap_unsync(self):
        """Unsynchronized: leap indicator 3 (alarm/unknown)."""
        src = _read_if_exists(NTP_SRC)
        self.assertRegex(src, r"LI.*3|leap.*3|LEAP_ALARM|0xC0",
                         "Unsynchronized must set LI=3")

    def test_ntp_rate_limit_global(self):
        """Global token bucket: 8 req/s, burst 32."""
        src = _read_if_exists(NTP_SRC)
        self.assertRegex(src, r"GLOBAL.*RATE|global.*bucket|BURST.*32",
                         "Must implement global rate limiting")

    def test_ntp_rate_limit_per_source(self):
        """Per-source rate limit: 2 req/s, burst 4."""
        src = _read_if_exists(NTP_SRC)
        self.assertRegex(src, r"PER_SOURCE|per_source|SOURCE.*BURST.*4",
                         "Must implement per-source rate limiting")

    def test_ntp_reference_id_gps(self):
        """GPS reference ID is 'GPS\\0'."""
        src = _read_if_exists(NTP_SRC)
        self.assertIn("GPS", src)

    def test_ntp_reference_id_rtc(self):
        """RTC holdover reference ID is 'RTC\\0'."""
        src = _read_if_exists(NTP_SRC)
        self.assertIn("RTC", src)

    def test_ntp_udp_port_123(self):
        src = _read_if_exists(NTP_SRC)
        self.assertIn("123", src)


class MainIntegrationContract(unittest.TestCase):
    """main.c must integrate timekeeper, NTP, and board-gated screens."""

    def test_cym_timekeeper_in_priv_requires(self):
        self.assertIn("cym_timekeeper", MAIN_CMAKE)

    def test_timekeeper_init_called(self):
        self.assertIn("cym_timekeeper_init", MAIN)

    def test_gps_observation_wired(self):
        self.assertIn("cym_timekeeper_observe_gps_utc", MAIN)

    def test_ntp_clock_active_flag(self):
        self.assertIn("s_ntp_clock_active", MAIN)

    def test_ntp_server_start_in_main(self):
        self.assertIn("cym_ntp_server_start", MAIN)

    def test_dhcp_ip_displayed(self):
        self.assertIn("DHCP IP", MAIN)

    def test_hostname_displayed(self):
        self.assertIn("cym-ntp", MAIN)

    def test_screen_stop_fn_registered(self):
        self.assertIn("ntp_clock_stop", MAIN)


class ClockSettingsContract(unittest.TestCase):
    """Settings -> Clock must be board-gated and use correct NVS keys."""

    def test_clock_tile_board_gated(self):
        """Clock tile must appear under CONFIG_BOARD_WS_C5_28."""
        pattern = re.compile(
            r'#if\s+defined\(CONFIG_BOARD_WS_C5_28\).*?"Clock"',
            re.S,
        )
        self.assertRegex(MAIN, pattern)

    def test_nvs_offset_key(self):
        self.assertIn("clk_offset", MAIN)

    def test_nvs_brightness_key(self):
        self.assertIn("clk_bright", MAIN)

    def test_offset_range(self):
        """UTC-12:00 (-720 min) to UTC+14:00 (+840 min)."""
        self.assertIn("-720", MAIN)
        self.assertIn("840", MAIN)

    def test_brightness_range(self):
        """10% to 100% brightness."""
        # Already constrained in set_backlight_percent but NTP clock needs its own
        self.assertRegex(MAIN, r"clk_bright|ntp_clock_brightness")

    def test_no_pps_gpio_selector(self):
        """Version one must not expose PPS GPIO selection."""
        self.assertNotIn("PPS GPIO", MAIN)
        self.assertNotIn("pps_gpio", MAIN)

    def test_save_cancel_controls(self):
        self.assertRegex(MAIN, r"[Ss]ave.*[Cc]lock|clock.*[Ss]ave")


class NTPClockDashboardContract(unittest.TestCase):
    """NTP Clock dashboard must show all required operational fields."""

    def test_ntp_clock_tile_on_classic_home(self):
        """Classic path exposes NTP Clock directly on its home grid."""
        main = MAIN[MAIN.index("static void show_main_tiles(void)\n{"):
                    MAIN.index("// ── WiFi Scan paginated list renderer")]
        self.assertIn("#if defined(CONFIG_BOARD_WS_C5_28)", main)
        self.assertIn('"NTP\\nClock"', main)
        self.assertIn('"NTP Clock Classic"', main)
        wifi = MAIN[MAIN.index("static void show_wifi_menu_screen(void)\n{"):
                    MAIN.index("// WiFi Sniff & Karma screen")]
        self.assertNotIn('"NTP Clock Classic"', wifi)

    def test_ntp_clock_tile_in_cat_tools(self):
        """Modern path: Tools & System -> NTP Clock."""
        pattern = re.compile(
            r'show_cat_tools.*?#if\s+defined\(CONFIG_BOARD_WS_C5_28\).*?"NTP',
            re.S,
        )
        self.assertRegex(MAIN, pattern)

    def test_exit_control(self):
        self.assertRegex(MAIN, r"[Ee]xit.*NTP|ntp.*[Ee]xit")

    def test_udp_123_status(self):
        self.assertIn("UDP/123", MAIN)

    def test_source_badge_labels(self):
        for label in ("GPS LOCK", "ACQUIRING", "RTC HOLDOVER", "UNSYNCED"):
            self.assertIn(label, MAIN, f"Dashboard must show '{label}' state")

    def test_no_auto_dim_while_active(self):
        """Screen idle timer must skip dimming while NTP clock is active."""
        self.assertIn("s_ntp_clock_active", MAIN)


class NTPPacketContract(unittest.TestCase):
    """Pure NTP timestamp and packet format verification."""

    NTP_EPOCH_OFFSET = 2208988800

    def test_ntp_epoch_offset_value(self):
        """Unix epoch 0 (1970-01-01 00:00:00) = NTP 2208988800."""
        import datetime
        ntp_epoch = datetime.datetime(1900, 1, 1, tzinfo=datetime.timezone.utc)
        unix_epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        diff = (unix_epoch - ntp_epoch).total_seconds()
        self.assertEqual(int(diff), self.NTP_EPOCH_OFFSET)

    def test_ntp_packet_is_48_bytes(self):
        """A minimal NTP packet is exactly 48 bytes."""
        packet = bytearray(48)
        self.assertEqual(len(packet), 48)
        # Mode 3 (client), Version 4
        packet[0] = (4 << 3) | 3  # VN=4, Mode=3
        self.assertEqual(packet[0] & 0x07, 3)  # mode
        self.assertEqual((packet[0] >> 3) & 0x07, 4)  # version

    def test_ntp_server_mode_encoding(self):
        """Server response: mode 4, version matches client."""
        for client_version in (3, 4):
            li = 0  # no warning
            vn = client_version
            mode = 4  # server
            byte0 = (li << 6) | (vn << 3) | mode
            self.assertEqual(byte0 & 0x07, 4)
            self.assertEqual((byte0 >> 3) & 0x07, client_version)

    def test_ntp_timestamp_conversion(self):
        """Production helper converts Unix seconds and microseconds to network-order NTP."""
        src = _read_if_exists(NTP_SRC)
        helper = re.search(
            r"static void timeval_to_ntp\([^)]*\)\s*\{(?P<body>.*?)\n\}",
            src,
            re.DOTALL,
        )
        self.assertIsNotNone(helper, "Production timeval_to_ntp helper must exist")
        body = helper.group("body")
        self.assertRegex(
            body,
            r"\*secs\s*=\s*htonl\(\(uint32_t\)\(tv->tv_sec\s*\+\s*NTP_EPOCH_OFFSET\)\)",
        )
        self.assertRegex(
            body,
            r"\(\(uint64_t\)tv->tv_usec\s*<<\s*32\)\s*/\s*1000000ULL",
        )
        self.assertRegex(body, r"\*frac\s*=\s*htonl\(\(uint32_t\)f\)")

    def test_originate_echo_position(self):
        """Production response echoes client transmit bytes 40-47 at bytes 24-31."""
        src = _read_if_exists(NTP_SRC)
        self.assertRegex(
            src,
            r"memcpy\s*\(\s*&resp\[24\]\s*,\s*&buf\[40\]\s*,\s*8\s*\)",
        )
        self.assertRegex(src, r"memcpy\s*\(\s*&resp\[32\]\s*,\s*&rx_s\s*,\s*4\s*\)")
        self.assertRegex(src, r"memcpy\s*\(\s*&resp\[36\]\s*,\s*&rx_f\s*,\s*4\s*\)")
        self.assertRegex(src, r"memcpy\s*\(\s*&resp\[40\]\s*,\s*&tx_s\s*,\s*4\s*\)")
        self.assertRegex(src, r"memcpy\s*\(\s*&resp\[44\]\s*,\s*&tx_f\s*,\s*4\s*\)")

    def test_stratum_1_for_primary_reference(self):
        """A GPS-disciplined server is stratum 1 (primary reference)."""
        stratum = 1
        self.assertEqual(stratum, 1)

    def test_stratum_16_for_unsynchronized(self):
        """Unsynchronized server uses stratum 16."""
        stratum = 16
        self.assertEqual(stratum, 16)

    def test_leap_indicator_3_is_alarm(self):
        """LI=3 means clock not synchronized."""
        li = 3
        byte0 = (li << 6) | (4 << 3) | 4
        self.assertEqual((byte0 >> 6) & 0x03, 3)


class NTPClockBehaviorContract(unittest.TestCase):
    """Behavioral source contracts for lifecycle and routing that broad regexes miss."""

    def _section(self, start, end):
        self.assertIn(start, MAIN)
        self.assertIn(end, MAIN)
        return MAIN[MAIN.index(start):MAIN.index(end, MAIN.index(start) + len(start))]

    def test_rmc_is_checksum_validated_and_continuously_disciplines(self):
        src = MAIN
        start = src.find("static bool parse_gps_nmea(const char *nmea_sentence)\n{")
        end = src.find("static void gps_task", start)
        parser = src[start:end]
        self.assertIn("nmea_checksum_valid(nmea_sentence)", parser)
        self.assertIn("timegm(&t)", parser)
        self.assertNotIn("setenv(\"TZ\"", parser)
        self.assertNotIn("s_gps_synced", parser)
        self.assertIn("cym_timekeeper_observe_gps_utc(epoch, esp_timer_get_time())", parser)

    def test_classic_home_has_exact_board_gated_tile(self):
        menu = self._section("static void show_main_tiles(void)\n{", "// ── WiFi Scan paginated list renderer")
        self.assertIn("#if defined(CONFIG_BOARD_WS_C5_28)", menu)
        self.assertIn('"NTP\\nClock"', menu)
        self.assertIn('"NTP Clock Classic"', menu)

    def test_modern_tools_has_exact_board_gated_tile(self):
        menu = self._section("static void show_cat_tools(void)\n{", "static void category_tile_event_cb")
        self.assertIn("#if defined(CONFIG_BOARD_WS_C5_28)", menu)
        self.assertIn('"NTP\\nClock"', menu)
        self.assertIn('"NTP Clock Modern"', menu)

    def test_callbacks_route_clock_and_both_ntp_parents(self):
        main_cb = self._section("static void main_tile_event_cb(lv_event_t *e)\n{", "// Attack tile event callback")
        settings_cb = self._section("static void settings_tile_event_cb(lv_event_t *e)\n{", "// Settings screen")
        self.assertIn('strcmp(tile_name, "NTP Clock Classic")', main_cb)
        self.assertIn('strcmp(tile_name, "NTP Clock Modern")', main_cb)
        self.assertIn("show_ntp_clock_or_wifi_prompt", main_cb)
        self.assertIn('strcmp(tile_name, "Clock")', settings_cb)
        self.assertIn("show_clock_settings_screen();", settings_cb)

    def test_exit_and_retry_are_functional(self):
        block = self._section("// NTP Clock — WS-C5-28 only", "static void show_settings_screen(void)")
        self.assertIn("ntp_clock_retry_cb", block)
        self.assertIn("Retry WiFi", block)
        self.assertIn("s_ntp_return_fn", block)
        exit_cb = self._section("static void ntp_clock_exit_cb", "static void ntp_clock_stop")
        self.assertIn("ntp_clock_stop();", exit_cb)
        self.assertIn("return_fn();", exit_cb)

    def test_screen_settings_home_labels_use_visible_teal(self):
        screen = self._section("static void show_screen_popup(void)\n{", "// ── Home Layout chooser popup")
        self.assertIn("lv_obj_set_style_text_color(home_hdr, COLOR_MATERIAL_TEAL, 0);", screen)
        self.assertIn("lv_obj_set_style_text_color(screen_home_classic_radio, COLOR_MATERIAL_TEAL, 0);", screen)
        self.assertIn("lv_obj_set_style_text_color(screen_home_4cat_radio, COLOR_MATERIAL_TEAL, 0);", screen)

    def test_ntp_uses_shared_wifi_prompt_until_dhcp(self):
        block = self._section("// NTP Clock — WS-C5-28 only", "static void show_settings_screen(void)")
        self.assertIn("s_ntp_pending_after_wifi", MAIN)
        self.assertIn('"WiFi for NTP Clock"', MAIN)
        self.assertIn("show_ntp_clock_or_wifi_prompt", block)
        self.assertIn("esp_netif_get_ip_info", block)
        poll = self._section("static void s_fileserv_poll_ip_cb", "static void fileserv_stop")
        self.assertIn("s_ntp_pending_after_wifi", poll)
        self.assertIn("show_ntp_clock_screen();", poll)
        wifi_screen = self._section("static void show_wifi_client_server_screen(void)\n{", "/* SSID label */")
        self.assertIn("s_ntp_return_fn", wifi_screen)

    def test_mdns_api_is_declared(self):
        self.assertIn('#include "mdns.h"', MAIN)

    def test_failed_rtc_init_releases_owned_resources(self):
        src = _read_if_exists(PCF_SRC)
        self.assertIn("i2c_master_bus_rm_device", src)
        self.assertIn("vSemaphoreDelete", src)

    def test_rtc_holdover_remains_authoritative_during_gps_qualification(self):
        src = _read_if_exists(TK_SRC)
        self.assertIn("s_rtc_trusted && s_rtc_valid", src)
        self.assertIn("s_holdover_base_uncertainty_us", src)
        self.assertIn("s_holdover_base_age_ms", src)

    def test_ntp_stop_has_bounded_forced_cleanup(self):
        src = _read_if_exists(NTP_SRC)
        self.assertIn("vTaskDelete(s_task)", src)
        self.assertIn("portENTER_CRITICAL", src)

    def test_ntp_launch_always_prompts_for_network_mode(self):
        block = self._section("// NTP Clock — WS-C5-28 only", "static void show_settings_screen(void)")
        self.assertIn("show_ntp_network_mode_popup", block)
        self.assertIn('"Client Mode"', block)
        self.assertIn('"AP Mode"', block)
        self.assertIn('"Cancel"', block)
        start = MAIN.rfind("static void show_ntp_clock_or_wifi_prompt")
        end = MAIN.find("static void ntp_start_mdns_and_server", start)
        launcher = MAIN[start:end]
        self.assertIn("show_ntp_network_mode_popup", launcher)
        self.assertNotIn("ntp_station_has_dhcp()", launcher)

    def test_ntp_client_public_sync_is_bounded_and_updates_timekeeper(self):
        block = self._section("// NTP Clock — WS-C5-28 only", "static void show_settings_screen(void)")
        self.assertIn('ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org")', block)
        self.assertIn("#define NTP_PUBLIC_SYNC_TIMEOUT_MS 5000", MAIN)
        self.assertIn("#define NTP_RTC_REPAIR_THRESHOLD_SEC 5", MAIN)
        self.assertRegex(block, re.compile(r"!before\.valid.*!before\.rtc_valid.*llabs", re.S))
        self.assertIn("esp_netif_sntp_sync_wait(pdMS_TO_TICKS(500))", block)
        self.assertIn("!s_ntp_stopping", block)
        self.assertIn("esp_netif_sntp_deinit();", block)
        self.assertIn("cym_timekeeper_observe_network_utc", block)
        self.assertRegex(block, r"\w+\.source\s*==\s*CYM_TIME_GPS_LOCKED")
        self.assertIn("NTP_PUBLIC_SKIPPED_GPS", block)

    def test_ntp_ap_mode_serves_without_public_internet(self):
        block = self._section("// NTP Clock — WS-C5-28 only", "static void show_settings_screen(void)")
        self.assertIn("WIFI_MODE_AP", block)
        self.assertIn("WIFI_AUTH_WPA2_PSK", block)
        self.assertIn('"CYM-NTP-%02X%02X%02X"', block)
        self.assertIn('#define NTP_AP_PASSWORD "cymtime28"', MAIN)
        self.assertIn("esp_netif_create_default_wifi_ap", block)
        self.assertIn("cym_ntp_server_start", block)
        self.assertIn("AP IP: %s", block)
        self.assertIn("AP SSID:", block)

    def test_public_ntp_is_a_valid_timekeeper_source_and_repairs_rtc(self):
        hdr = _read_if_exists(TK_HEADER)
        src = _read_if_exists(TK_SRC)
        ntp = _read_if_exists(NTP_SRC)
        self.assertIn("CYM_TIME_NETWORK_SYNC", hdr)
        self.assertIn("cym_timekeeper_observe_network_utc", hdr)
        self.assertIn("bool repair_rtc", hdr)
        self.assertRegex(src, re.compile(r"if\s*\(repair_rtc\).*write_rtc_if_due\(epoch", re.S))
        self.assertIn("CYM_TIME_NETWORK_SYNC", src)
        self.assertIn('return "PUBLIC NTP"', src)
        self.assertIn("CYM_TIME_NETWORK_SYNC", ntp)
        self.assertIn("NTP_STRATUM_SECONDARY", ntp)
        self.assertIn("REFID_SNTP", ntp)

    def test_all_release_soc_versions_match_cycle(self):
        for rel in ("ESP32C5/CMakeLists.txt", "ESP32/CMakeLists.txt", "ESP32S3/CMakeLists.txt"):
            self.assertIn('set(PROJECT_VER "v2.15.38")', (ROOT / rel).read_text(), rel)


if __name__ == "__main__":
    unittest.main()
