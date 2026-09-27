#!/usr/bin/env python3
"""Static regression contracts for Detect & Defend harvester integration."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "ESP32C5/main/main.c").read_text(encoding="utf-8")


def function_body(name: str) -> str:
    match = re.search(rf"static\s+(?:void|bool|int)\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", SOURCE)
    if not match:
        return ""
    start = match.start()
    depth = 0
    seen = False
    for idx in range(match.end() - 1, len(SOURCE)):
        if SOURCE[idx] == "{":
            depth += 1
            seen = True
        elif SOURCE[idx] == "}":
            depth -= 1
            if seen and depth == 0:
                return SOURCE[start:idx + 1]
    return ""


class DetectDefendHarvesterContract(unittest.TestCase):
    def test_menu_exposes_harvester_screen_with_stop_hook(self):
        self.assertIn('"Deauth\\nHarvest"', SOURCE)
        self.assertIn('show_harvester_detector_screen();', function_body("dd_menu_tile_cb"))
        show = function_body("show_harvester_detector_screen")
        self.assertIn('create_function_page_base("Deauth Harvest")', show)
        self.assertIn("g_screen_stop_fn = harvester_detector_stop;", show)

    def test_pwnagotchi_records_are_per_bssid_and_age_after_60_seconds(self):
        cb = function_body("pwn_promiscuous_cb")
        timer = function_body("pwn_ui_timer_cb")
        self.assertIn("#define PWN_AGE_MS 60000", SOURCE)
        self.assertIn("memcmp(s_pwn[i].mac, bssid, 6)", cb)
        self.assertIn("memcpy(s_pwn[idx].mac, bssid, 6)", cb)
        self.assertIn("now - s_pwn[i].last_ms <= PWN_AGE_MS", timer)

    def test_pwnagotchi_pwnd_total_is_parsed_and_visible(self):
        cb = function_body("pwn_promiscuous_cb")
        timer = function_body("pwn_ui_timer_cb")
        self.assertIn('"\\\"pwnd_tot\\\":"', cb)
        self.assertRegex(timer, r"pwnd(?:_tot)?[:=]%l?d")

    def test_harvester_uses_true_unique_targets_with_per_target_aging(self):
        cb = function_body("harv_promiscuous_cb")
        self.assertIn("#define HARV_AGE_MS 60000", SOURCE)
        self.assertIn("seen_bssid", SOURCE)
        self.assertIn("seen_ms", SOURCE)
        self.assertNotIn("last_bssid", SOURCE)
        self.assertRegex(cb, r"memcmp\([^\n]*seen_bssid")
        self.assertRegex(cb, r"now\s*-\s*[^\n]*seen_ms[^\n]*HARV_AGE_MS")

    def test_harvester_retries_are_deduplicated_and_tables_evict_lru(self):
        cb = function_body("harv_promiscuous_cb")
        self.assertRegex(cb, r"f\[1\]\s*&\s*0x08")
        self.assertIn("oldest", cb)
        self.assertIn("HARV_MAX", cb)
        self.assertIn("HARV_PROBE_MAX", cb)

    def test_ui_uses_observation_language_not_confirmed_attribution(self):
        timer = function_body("harv_ui_timer_cb")
        self.assertNotIn("CONFIRMED attacker", SOURCE)
        self.assertNotIn('"ATK ', timer)
        self.assertNotIn('"Deauth attack', timer)
        self.assertIn("Possible", timer)
        self.assertIn("activity", timer.lower())

    def test_fox_hunt_is_labeled_as_frame_signal_not_attacker_identity(self):
        timer = function_body("harv_ui_timer_cb")
        self.assertNotIn("attacker ch", timer)
        self.assertIn("frame signal", timer.lower())

    def test_scope_is_explicitly_2_4_ghz_and_channel_parking_is_bounded(self):
        show = function_body("show_harvester_detector_screen")
        task = function_body("harv_task")
        cb = function_body("harv_promiscuous_cb")
        self.assertRegex(show, r"2\.4\s*GHz")
        self.assertIn("HARV_PARK_MS", SOURCE)
        self.assertIn("s_harv_park_started", SOURCE)
        self.assertNotRegex(cb, r"s_harv_park_until\s*=\s*now\s*\+\s*1200")
        self.assertIn("esp_wifi_set_channel", task)
        self.assertIn("ESP_OK", task)

    def test_stop_waits_for_callback_quiescence_and_reentry_is_guarded(self):
        stop = function_body("harvester_detector_stop")
        show = function_body("show_harvester_detector_screen")
        cb = function_body("harv_promiscuous_cb")
        self.assertIn("s_harv_cb_inflight", cb)
        self.assertIn("s_harv_cb_inflight", stop)
        self.assertRegex(stop, r"(?:while|for)\s*\([^)]*")
        self.assertIn("if(!inflight)break", stop.replace(" ", ""))
        self.assertIn("s_harv_task", show)
        self.assertIn("if (s_harv_task || inflight)", show)

    def test_task_lifecycle_does_not_manually_free_a_live_static_stack(self):
        show = function_body("show_harvester_detector_screen")
        stop = function_body("harvester_detector_stop")
        self.assertIn("xTaskCreate(", show)
        self.assertNotIn("xTaskCreateStatic", show)
        self.assertNotIn("s_harv_stack", stop)


if __name__ == "__main__":
    unittest.main(verbosity=2)
