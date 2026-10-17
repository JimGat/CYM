"""Bounded diagnostic boundary contracts and real-production host helper execution."""
from pathlib import Path
import re,subprocess,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
class MemoryBoundaryHost(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main=(ROOT/'ESP32C5/main/main.c').read_text()
        cls.scanner=(ROOT/'ESP32C5/components/wifi_scanner/wifi_scanner.c').read_text()
    def test_production_helpers(self):
        subprocess.run([sys.executable,str(ROOT/'tests/run_memory_boundary_host.py')],check=True)
    def test_paired_display_and_radio_boundaries(self):
        for name in ['display-drawbuffers-before','display-drawbuffers-after','wifi-init-before','wifi-init-after','wifi-teardown-before','wifi-teardown-after','ble-init-before','ble-init-after','ble-teardown-before','ble-teardown-after','ble-scan-start','ble-scan-complete']:
            self.assertIn('"'+name+'"',self.main)
        for name in ['wifi-scan-start','wifi-scan-start-return','wifi-scan-complete']:
            self.assertIn('cym_debug_memory_snapshot("'+name+'")',self.scanner)
    def test_counter_scope_no_resets_or_rf_changes(self):
        self.assertNotIn('s_bt_cb_total = s_bt_ext_events = s_bt_leg_events = 0',self.main)
        for name in ['s_bt_cb_total','s_bt_ext_events','s_bt_leg_events','s_bt_parse_fail','s_bt_blacklisted','s_bt_already_seen']:
            self.assertIn('__atomic_load_n(&'+name+', __ATOMIC_RELAXED)',self.main)
            self.assertIn('__atomic_fetch_add(&'+name+', 1, __ATOMIC_RELAXED)',self.main)
        self.assertIn('bt_diag_end("gap-complete", 0)',self.main)
        self.assertIn('bt_diag_end("cancel-return", 0)',self.main)
    def test_clock_admission_precedes_radio_mutations(self):
        for name in ['ensure_wifi_mode','ensure_ble_mode','_ot_switch_to_wifi','_ot_switch_to_ble','_ot_switch_to_154','wdup_ensure_wifi']:
            self.assertRegex(self.main,r'static bool '+name+r'\([^;]*?\)\s*\{\s*if \(!clock_radio_admit\(\)\) return false;')
        self.assertRegex(self.main,r'static void radio_reset_to_idle\(void\)\s*\{\s*if \(!clock_radio_reset_admit\(\)\) return;')
        self.assertRegex(self.main,r'static void reset_function_page_children\(void\)\s*\{\s*clock_cancel_radio_navigation\(\);')
        self.assertRegex(self.main,r'void show_menu\(void\)\s*\{\s*clock_cancel_radio_navigation\(\);')
        self.assertRegex(self.main,r'static void nav_back_cb\(lv_event_t \*e\)\s*\{\s*clock_cancel_radio_navigation\(\);')
        self.assertIn('show_menu(); // same Stop -> UI destruction',self.main)
        self.assertIn('if (clock_attack_route_uses_radio(name))',self.main)
        self.assertIn('clock_radio_handoff_poll();',self.main)
        self.assertIn('if (!wifi_claimed) return;',self.main)
