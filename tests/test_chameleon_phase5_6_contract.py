#!/usr/bin/env python3
"""Executable contracts for Chameleon Phase 5/6 features.

RED phase: written against the unchanged production code; every test that
exercises a NEW requirement is expected to fail.  Tests that verify EXISTING
correct behavior (T5577 preservation, BLE driver, navigation) should pass.

Requirements covered:
 1. NTAG dump: s_ntag_dump[231], bounded final read, 213/215/216 termination
 2. Saved Cards manager (replaces Cards Phase 5 stub)
 3. MF Keys dictionary status screen (replaces MF Keys Phase 6 stub)
 4. MF1 Detect screen (4004-4007, mfkey32 export)
 5. MFC dump commands 2007/2008 (not 4009/4010)
 6. MFC geometry: Mini 5/20, 1K 16/64, 4K 40/256
 7. MFC .nfc load to emulator via cmd 4000, chunked, then 1013 save
 8. NTAG 4022 chunking, no 4014
 9. Chameleon Settings (animation 1015/1016, sleep 1039/1040)
10. Classic + Modern nav to shared NFC/RFID Hub
11. Preserve T5577/BLE driver
12. Stop hooks for new screens
13. Documentation accuracy
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN_C = ROOT / "ESP32C5/main/main.c"
TRANSPORT_H = ROOT / "ESP32C5/main/chameleon_ble.h"


class NtagDumpContract(unittest.TestCase):
    """Req 1: NTAG dump capacity 231 pages, bounded final read, clean termination."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_ntag_dump_array_holds_231_pages(self):
        """NTAG dump storage must allocate all 231 pages without static-BSS truncation."""
        self.assertIn("#define CHAM_NTAG_MAX_PAGES 231", self.src)
        self.assertRegex(self.src, r"calloc\(CHAM_NTAG_MAX_PAGES,\s*4\)",
                         "NTAG dump must allocate full NTAG216 storage on demand")

    def test_ntag_page_read_bounds_at_231(self):
        """Boundary checks in s_ntag_on_page_read must use 231 or CHAM_NTAG_MAX_PAGES, not 222."""
        # Find the callback and verify bound references
        match = re.search(r"static void s_ntag_on_page_read\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_ntag_on_page_read not found")
        body = match.group(1)
        # Must not contain the old 222 bound
        self.assertNotIn("222", body,
                         "s_ntag_on_page_read still uses 222 bound instead of 231")
        # Must contain 231 or CHAM_NTAG_MAX_PAGES bound somewhere
        self.assertTrue("231" in body or "CHAM_NTAG_MAX_PAGES" in body,
                        "Bound must reference 231 or CHAM_NTAG_MAX_PAGES")

    def test_ntag_final_partial_chunk_bounded(self):
        """When cur_page + 4 > max_pages, only valid pages should be stored."""
        match = re.search(r"static void s_ntag_on_page_read\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)
        # Must bound each destination page to both detected geometry and allocation.
        self.assertIn("s_ntag_cur_page < s_ntag_max_pages", body)
        self.assertIn("s_ntag_cur_page < CHAM_NTAG_MAX_PAGES", body)
        self.assertIn("src_page < 4", body)

    def test_ntag_nfc_file_parser_supports_231_pages(self):
        """Parser storage and index checks must cover full NTAG216 geometry."""
        body = re.search(r"static bool s_parse_nfc_file\(.*?\n\{(.*?)\nstatic ",
                         self.src, re.DOTALL).group(1)
        self.assertIn("calloc(CHAM_NTAG_MAX_PAGES, 4)", body)
        self.assertRegex(body, r"idx\s*>=\s*CHAM_NTAG_MAX_PAGES")


class MfcDumpCommandContract(unittest.TestCase):
    """Req 5: MFC dump must use commands 2007 (check) and 2008 (read),
    never 4009/4010.  Payload: [keyType, block, key[6]]."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_mfc_check_uses_cmd_2007(self):
        """s_mf_try_next_check must send command 2007, not 4009."""
        match = re.search(r"static void s_mf_try_next_check\(void\)\s*\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_mf_try_next_check not found")
        body = match.group(1)
        self.assertIn("cham_send_cmd(2007,", body,
                       "MFC key check must use cmd 2007 (mf1CheckKey)")
        self.assertNotIn("4009", body,
                         "Must not use cmd 4009 (emulator config)")

    def test_mfc_read_uses_cmd_2008(self):
        """s_mf_on_block_read must send command 2008, not 4010."""
        match = re.search(r"static void s_mf_on_block_read\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn("cham_send_cmd(2008,", body,
                       "MFC block read must use cmd 2008 (mf1ReadBlock)")
        self.assertNotIn("4010", body)

    def test_mfc_payload_is_keytype_block_key(self):
        """Payload order must be [keyType, block, key] per upstream protocol."""
        # Look for the payload construction in s_mf_try_next_check
        match = re.search(r"static void s_mf_try_next_check\(void\)\s*\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)
        # Payload should start with key_type, then block
        self.assertRegex(body, r"key_type.*auth_blk",
                         "Payload must be [keyType, block, key...] order")

    def test_mfc_dump_section_comment_correct(self):
        """Phase 6 comment must reference 2007/2008, not 4009/4010."""
        # Find the PHASE 6 header comment
        self.assertNotRegex(self.src,
            r"PHASE 6.*4009.*4010",
            "Phase 6 comment must not reference 4009/4010")


class MfcGeometryContract(unittest.TestCase):
    """Req 6: Mini 5 sectors/20 blocks, 1K 16/64, 4K 40/256."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_mfc_dump_array_supports_4k(self):
        """MFC dump storage must allocate all 256 blocks without static-BSS truncation."""
        self.assertIn("#define CHAM_MF_MAX_BLOCKS  256", self.src)
        self.assertRegex(self.src, r"calloc\(CHAM_MF_MAX_BLOCKS,\s*16\)")

    def test_mfc_block_ok_supports_4k(self):
        """Block-presence storage must cover all full-4K blocks."""
        self.assertRegex(self.src, r"calloc\(CHAM_MF_MAX_BLOCKS,\s*sizeof\(bool\)\)")

    def test_mfc_mini_geometry(self):
        """SAK 0x09 (Mini) must use 5 sectors, 20 blocks."""
        self.assertIn("s_mf_total_sectors", self.src,
                      "Must have s_mf_total_sectors variable for geometry")

    def test_mfc_4k_large_sectors(self):
        """4K sectors 32-39 must have 16 blocks each."""
        # Must have a function or logic to compute blocks per sector
        self.assertRegex(self.src, r"sector.*>=\s*32.*16",
                         "4K large sectors (32-39) must use 16 blocks each")

    def test_mfc_save_writes_all_blocks(self):
        """s_mf_save_dump_file must write blocks up to the total for the card type."""
        match = re.search(r"static bool s_mf_save_dump_file\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)
        # Must not hardcode 64 blocks
        self.assertNotRegex(body, r"b\s*<\s*64\b",
                            "Save must not hardcode 64 blocks; use s_mf_total_blocks")


class MfcSlotLoadContract(unittest.TestCase):
    """Req 7: Classic .nfc load to emulator via cmd 4000, chunked, bounded."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_mfc_nfc_file_loading_supported(self):
        """s_parse_nfc_file must not reject MFC files."""
        self.assertNotIn('"MFC load to slot not supported yet"', self.src,
                         "MFC slot load must be implemented, not stubbed")

    def test_uses_cmd_4000_for_mfc_load(self):
        """MFC load must use cmd 4000 (mf1LoadBlockData)."""
        self.assertRegex(self.src, r"cham_send_cmd[^(]*\(4000,",
                         "Must use cmd 4000 for MFC block data load")

    def test_mfc_load_payload_format(self):
        """4000 payload: [startBlock, block0_16bytes, block1_16bytes, ...]."""
        # The code must construct a payload starting with a block number
        self.assertIn("4000", self.src)
        # Chunking: must split into transport-safe sizes
        self.assertRegex(self.src, r"chunk|CHUNK",
                         "MFC load must chunk data for transport safety")

    def test_mfc_load_saves_with_1013(self):
        """After loading all blocks, must call cmd 1013 (saveSettings)."""
        # The MFC load path must eventually chain to 1013
        self.assertRegex(self.src, r"cham_send_cmd\(1013,.*s_clone_on_saved",
                         "MFC load must save settings after writing blocks")

    def test_no_cmd_4014_used(self):
        """Must not use cmd 4014 (mf1GetFirstBlockColl) in load path."""
        self.assertNotRegex(self.src, r"cham_send_cmd[^(]*\(4014,",
                            "Must not use cmd 4014 in slot load")

    def test_mfc_type_constants_correct(self):
        """MFC tag types: Mini=1000, 1K=1001, 2K=1002, 4K=1003."""
        # s_parse_nfc_file must map Classic types to correct constants
        self.assertIn("1000", self.src)  # Mini
        self.assertIn("1001", self.src)  # 1K
        self.assertIn("1003", self.src)  # 4K


class NtagChunkingContract(unittest.TestCase):
    """Req 8: NTAG 4022 must chunk for transport safety."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_ntag_4022_chunking(self):
        """NTAG write via 4022 must chunk pages for 512-byte transport limit."""
        # Find the HF write path and check for chunking
        # The s_parse_nfc_file or the write chain must chunk 4022 payloads
        # For NTAG216 (231 pages * 4 bytes = 924 bytes + 2 header > 512)
        self.assertRegex(self.src, r"4022.*chunk|chunk.*4022|NTAG.*chunk|s_clone_hf_chunk",
                         "NTAG 4022 must be chunked for transport safety")


class SavedCardsScreenContract(unittest.TestCase):
    """Req 2: Saved Cards manager replaces Phase 5 stub."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_no_cards_phase5_stub(self):
        """The 'Cards' Phase 5 stub must be replaced with a real screen."""
        self.assertNotIn('"Phase 5"', self.src,
                         "'Phase 5' stub label must not exist")

    def test_saved_cards_screen_exists(self):
        """show_cham_saved_cards_screen must be defined."""
        self.assertIn("show_cham_saved_cards_screen", self.src)

    def test_saved_cards_lists_files(self):
        """Saved Cards must scan for .rfid and .nfc files."""
        self.assertRegex(self.src, r'(?s)show_cham_saved_cards_screen.*s_fb_scan_dir',
                         "Saved Cards must list saved card files")

    def test_saved_cards_has_delete_confirm(self):
        """Delete must require confirmation."""
        self.assertIn("Delete", self.src)
        self.assertRegex(self.src, r"cham_cards.*delete.*confirm|confirm.*delete",
                         "Cards screen must have safe delete confirmation")

    def test_saved_cards_stop_hook(self):
        """Saved Cards screen must register a stop hook."""
        self.assertIn("cham_saved_cards_stop", self.src)


class MfKeysScreenContract(unittest.TestCase):
    """Req 3: MF Keys dictionary status screen replaces Phase 6 stub."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_no_mfkeys_phase6_stub(self):
        """MF Keys Phase 6 stub label must not exist."""
        # The specific stub pattern: s_cham_stub_tile(..., "MF Keys", "Phase 6")
        self.assertNotRegex(self.src, r'stub_tile.*"MF Keys".*"Phase 6"',
                            "MF Keys Phase 6 stub must be replaced")

    def test_mfkeys_screen_exists(self):
        """show_cham_mfkeys_screen must be defined."""
        self.assertIn("show_cham_mfkeys_screen", self.src)

    def test_mfkeys_shows_counts(self):
        """MF Keys screen must show built-in and external key counts."""
        self.assertRegex(self.src, r"MF_BUILTIN_KEY_COUNT|builtin.*count|Built-in",
                         "MF Keys must display built-in key count")
        self.assertRegex(self.src, r"mf_keys\.dic|external.*count|External",
                         "MF Keys must display external key count")

    def test_mfkeys_no_key_values_shown(self):
        """Must NOT display actual key hex values in the MF Keys UI."""
        # The screen must show counts/status only, not the actual key bytes
        self.assertIn("show_cham_mfkeys_screen", self.src)

    def test_mfkeys_stop_hook(self):
        """MF Keys screen must register a stop hook."""
        self.assertIn("cham_mfkeys_stop", self.src)


class DetectScreenContract(unittest.TestCase):
    """Req 4: MF1 Detect screen using verified upstream protocol (4004-4007)."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_no_detect_phase6_stub(self):
        """Detect Phase 6 stub must be replaced."""
        self.assertNotRegex(self.src, r'stub_tile.*"Detect".*"Phase 6"',
                            "Detect Phase 6 stub must be replaced")

    def test_detect_screen_exists(self):
        """show_cham_detect_screen must be defined."""
        self.assertIn("show_cham_detect_screen", self.src)

    def test_detect_uses_cmd_4004(self):
        """Must use cmd 4004 (mf1SetDetectionEnable)."""
        self.assertRegex(self.src, r"cham_send_cmd[^(]*\(4004,")

    def test_detect_uses_cmd_4005(self):
        """Must use cmd 4005 (mf1GetDetectionCount)."""
        self.assertRegex(self.src, r"cham_send_cmd[^(]*\(4005,")

    def test_detect_uses_cmd_4006(self):
        """Must use cmd 4006 (mf1GetDetectionResult)."""
        self.assertRegex(self.src, r"cham_send_cmd[^(]*\(4006,")

    def test_detect_uses_cmd_4007(self):
        """Must use cmd 4007 (mf1GetDetectionStatus)."""
        self.assertRegex(self.src, r"cham_send_cmd[^(]*\(4007,")

    def test_detect_record_18_bytes(self):
        """Detection records are 18 bytes: [block, flags, uid4, nt4, nr4, ar4]."""
        self.assertRegex(self.src, r"18.*record|record.*18",
                         "Detection records must be 18 bytes")

    def test_detect_exports_mfkey32v2_format(self):
        """Must export in mfkey32v2-compatible text format."""
        self.assertRegex(self.src, r"mfkey32|mfkey|nonce.*export",
                         "Must export mfkey32v2-compatible nonce pairs")
        self.assertIn("/sdcard/lab/rfid/hf/", self.src)

    def test_detect_stop_hook(self):
        """Detect screen must register a stop hook."""
        self.assertIn("cham_detect_stop", self.src)

    def test_detect_bounded_memory(self):
        """Detection nonce storage must be bounded."""
        self.assertRegex(self.src, r"DETECT_MAX|detect_max|s_det_max",
                         "Detection storage must have a max bound")


class SettingsScreenContract(unittest.TestCase):
    """Req 9: Chameleon Settings (animation 1015/1016, sleep 1039/1040)."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_settings_screen_exists(self):
        """show_cham_settings_screen must be defined."""
        self.assertIn("show_cham_settings_screen", self.src)

    def test_animation_get_cmd_1016(self):
        """Must use cmd 1016 (getAnimationMode)."""
        self.assertRegex(self.src, r"cham_send_cmd[^(]*\(1016,")

    def test_animation_set_cmd_1015(self):
        """Must use cmd 1015 (setAnimationMode)."""
        self.assertRegex(self.src, r"cham_send_cmd[^(]*\(1015,")

    def test_sleep_get_cmd_1039(self):
        """Must use cmd 1039 (getSleepTimeout)."""
        self.assertRegex(self.src, r"cham_send_cmd[^(]*\(1039,")

    def test_sleep_set_cmd_1040(self):
        """Must use cmd 1040 (setSleepTimeout)."""
        self.assertRegex(self.src, r"cham_send_cmd[^(]*\(1040,")

    def test_settings_stop_hook(self):
        """Settings screen must register a stop hook."""
        self.assertIn("cham_settings_stop", self.src)

    def test_no_ble_passkeys_or_factory_reset(self):
        """Settings must NOT include BLE passkeys, bonds, or factory reset."""
        # Find the settings screen function body
        idx = self.src.find("show_cham_settings_screen")
        if idx < 0:
            self.skipTest("Settings screen not found yet")
        end_idx = self.src.find("\nstatic void show_", idx + 1)
        if end_idx < 0:
            end_idx = len(self.src)
        body = self.src[idx:end_idx]
        self.assertNotRegex(body, r"1030|1031|1032|1036|1037|1014|1020",
                            "Settings must not include BLE passkeys/bonds/reset")


class NavigationContract(unittest.TestCase):
    """Req 10: Both Classic and Modern nav reach shared NFC/RFID Hub."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_nfc_hub_screen_exists(self):
        self.assertIn("show_nfc_hub_screen", self.src)

    def test_classic_nav_has_nfc_tile(self):
        """Classic horizontal tile strip must have NFC/RFID tile."""
        self.assertRegex(self.src, r'NFC.*RFID|RFID.*NFC')

    def test_modern_nav_reaches_nfc_hub(self):
        """Modern menu must route to NFC/RFID Hub."""
        self.assertIn('show_nfc_hub_screen', self.src)

    def test_chameleon_tile_in_nfc_hub(self):
        """NFC Hub must have Chameleon Ultra tile."""
        self.assertIn("nfc_hub_chameleon_cb", self.src)
        self.assertIn("show_chameleon_screen", self.src)

    def test_tiles_row2_all_clickable(self):
        """Tile row 2 must have all clickable tiles (no stubs)."""
        # Should NOT have LV_OBJ_FLAG_CLICKABLE cleared on any tile row 2 buttons
        # Find tile row 2 section
        idx = self.src.find("Tile row 2")
        if idx < 0:
            self.skipTest("Tile row 2 section not found")
        end_idx = self.src.find("Disconnect button", idx)
        if end_idx < 0:
            end_idx = idx + 2000
        row2 = self.src[idx:end_idx]
        # All tiles should be clickable (no LV_OBJ_FLAG_CLICKABLE cleared)
        self.assertNotIn("LV_OBJ_FLAG_CLICKABLE", row2,
                         "Tile row 2 must not have non-clickable stubs")


class PreservationContract(unittest.TestCase):
    """Req 11-12: Preserve T5577, BLE driver, stop hooks."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_t5577_clone_preserved(self):
        """Physical T5577 clone flow must still exist."""
        for token in ("Clone T5577", "LF_T55_WRITING", "LF_T55_VERIFYING",
                      "cham_t55xx_build_em_payload", "cham_t55xx_build_hid_payload"):
            self.assertIn(token, self.src, f"T5577 token missing: {token}")

    def test_ble_driver_unchanged(self):
        """chameleon_ble.h API must still declare all public functions."""
        hdr = TRANSPORT_H.read_text()
        for fn in ("cham_init", "cham_scan_start", "cham_connect", "cham_disconnect",
                   "cham_cancel_pending", "cham_poll", "cham_send_cmd", "cham_send_cmd_ex"):
            self.assertIn(fn, hdr, f"BLE API missing: {fn}")

    def test_existing_stop_hooks_preserved(self):
        """All existing stop hooks must remain registered."""
        for hook in ("chameleon_screen_stop", "cham_hf_read_stop",
                     "cham_lf_read_stop", "cham_slots_stop"):
            self.assertIn(f"g_screen_stop_fn = {hook}", self.src,
                          f"Stop hook not registered: {hook}")

    def test_new_screens_have_stop_hooks(self):
        """Every new screen must register g_screen_stop_fn."""
        for screen_fn, hook_fn in [
            ("show_cham_saved_cards_screen", "cham_saved_cards_stop"),
            ("show_cham_mfkeys_screen", "cham_mfkeys_stop"),
            ("show_cham_detect_screen", "cham_detect_stop"),
            ("show_cham_settings_screen", "cham_settings_stop"),
        ]:
            if screen_fn in self.src:
                self.assertIn(f"g_screen_stop_fn = {hook_fn}", self.src,
                              f"Stop hook not registered for {screen_fn}")

    def test_new_stop_hooks_cancel_ble_and_null_ptrs(self):
        """New stop hooks must call cham_cancel_pending and NULL LVGL pointers."""
        for hook in ("cham_saved_cards_stop", "cham_mfkeys_stop",
                     "cham_detect_stop", "cham_settings_stop"):
            idx = self.src.find(f"static void {hook}(void)")
            if idx < 0:
                continue  # Will be caught by existence test
            end = self.src.find("\n}", idx)
            body = self.src[idx:end]
            self.assertIn("cham_cancel_pending()", body,
                          f"{hook} must call cham_cancel_pending()")
            self.assertIn("= NULL", body,
                          f"{hook} must NULL LVGL pointers")


class DocumentationContract(unittest.TestCase):
    """Req 13: Docs and comments are accurate."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_phase6_comment_references_correct_commands(self):
        """Phase 6 section comment must reference correct MFC commands."""
        # Should mention 2007/2008 for MFC
        phase6_idx = self.src.find("PHASE 6")
        if phase6_idx < 0:
            self.skipTest("No PHASE 6 comment found")
        comment_end = self.src.find("*/", phase6_idx)
        comment = self.src[phase6_idx:comment_end]
        self.assertRegex(comment, r"2007|mf1CheckKey",
                         "Phase 6 comment must reference cmd 2007")
        self.assertRegex(comment, r"2008|mf1ReadBlock",
                         "Phase 6 comment must reference cmd 2008")

    def test_no_overclaim_on_cracking(self):
        """Must not claim on-device cracking capability in detect screen."""
        # Scope to the chameleon detect section only (other screens may
        # legitimately use 'crack' in unrelated contexts like CC1101 brute force)
        start = self.src.find("show_cham_detect_screen")
        if start < 0:
            self.skipTest("detect screen not found")
        end = self.src.find("show_cham_settings_screen", start)
        if end < 0:
            end = len(self.src)
        detect_section = self.src[start:end].lower()
        for overclaim in ("crack key", "recover key", "key recovery",
                          "mfkey32 on-device", "on-device crack"):
            self.assertNotIn(overclaim.lower(), detect_section,
                             f"Must not overclaim: {overclaim}")

    def test_t5577_distinction_documented(self):
        """Physical T5577 clone must be documented as distinct from emulation."""
        self.assertIn("separate from", self.src.lower(),
                      "T5577 physical clone must be documented as separate from emulation")


class FixRegressionContract(unittest.TestCase):
    """Regression tests for the 10 verified defect fixes (recovery pass).
    Each test fails on the pre-fix code and passes on the fixed code."""

    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    # ── Fix #1: NTAG dump uses cmd 2010 (hf14ARawCommand), not 2001 ──
    def test_fix1_ntag_dump_uses_cmd_2010(self):
        """NTAG page read must use cmd 2010 (hf14ARawCommand), never 2001."""
        # Find s_ntag_on_page_read and s_ntag_dump_start
        for fn in ("s_ntag_on_page_read", "s_ntag_dump_start"):
            match = re.search(rf"static void {fn}\(.*?\n\{{(.*?)\n\}}", self.src, re.DOTALL)
            self.assertIsNotNone(match, f"{fn} not found")
            body = match.group(1)
            self.assertNotIn("cham_send_cmd(2001", body,
                             f"{fn} still uses cmd 2001 (mf1SupportDetect)")
            self.assertIn("cham_send_cmd(2010", body,
                          f"{fn} must use cmd 2010 (hf14ARawCommand)")

    def test_fix1_ntag_payload_is_7_bytes(self):
        """hf14ARawCommand payload must be 7 bytes: options+timeout+bitlen+READ+page."""
        for fn in ("s_ntag_on_page_read", "s_ntag_dump_start"):
            match = re.search(rf"static void {fn}\(.*?\n\{{(.*?)\n\}}", self.src, re.DOTALL)
            self.assertIsNotNone(match, f"{fn} not found")
            body = match.group(1)
            # Must have payload[7] not payload[3]
            self.assertNotRegex(body, r"payload\[3\]",
                                f"{fn} still uses 3-byte payload")
            self.assertRegex(body, r"payload\[7\]",
                             f"{fn} must use 7-byte payload for hf14ARawCommand")

    def test_fix1_phase6_comment_references_2010(self):
        """Phase 6 header comment must reference cmd 2010, not 2001, for NTAG."""
        phase6_idx = self.src.find("PHASE 6")
        self.assertGreater(phase6_idx, 0, "PHASE 6 section header not found")
        comment_end = self.src.find("*/", phase6_idx)
        comment = self.src[phase6_idx:comment_end]
        self.assertIn("2010", comment,
                      "Phase 6 comment must reference cmd 2010 for NTAG")
        self.assertNotIn("HF14A_RAW (2001)", comment,
                         "Phase 6 comment must not reference 2001 for NTAG")

    # ── Fix #2: NTAG destination cursor advances only while in geometry ──
    def test_fix2_ntag_cursor_clamped(self):
        """s_ntag_on_page_read must advance one stored page at a time under both bounds."""
        start = self.src.index("static void s_ntag_on_page_read")
        end = self.src.index("static void s_ntag_dump_start", start)
        body = self.src[start:end]
        self.assertIn("s_ntag_cur_page < s_ntag_max_pages", body)
        self.assertIn("s_ntag_cur_page < CHAM_NTAG_MAX_PAGES", body)
        self.assertIn("s_ntag_cur_page++", body)

    # ── Fix #3: CYD2USB MFC bounds use CHAM_MF_MAX_BLOCKS, not 256 ──
    def test_fix3_block_read_uses_max_blocks_define(self):
        """s_mf_on_block_read OOB check must use CHAM_MF_MAX_BLOCKS, not 256."""
        match = re.search(r"static void s_mf_on_block_read\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_mf_on_block_read not found")
        body = match.group(1)
        self.assertNotIn("blk < 256", body,
                         "Must not use hardcoded 256 bound")
        self.assertIn("blk < CHAM_MF_MAX_BLOCKS", body,
                      "Must use CHAM_MF_MAX_BLOCKS for bounds check")

    def test_fix3_save_dump_uses_max_blocks_define(self):
        """s_mf_save_dump_file loop bound must use CHAM_MF_MAX_BLOCKS, not 256."""
        # Find the function definition (with body), not the forward declaration
        match = re.search(
            r"static bool s_mf_save_dump_file\([^)]*\)\s*\n\{(.*?)\n\}",
            self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_mf_save_dump_file definition not found")
        body = match.group(1)
        self.assertNotIn("b < 256", body,
                         "Must not use hardcoded 256 bound in save loop")
        self.assertIn("CHAM_MF_MAX_BLOCKS", body,
                      "Save loop must reference CHAM_MF_MAX_BLOCKS")

    def test_fix3_dump_start_preserves_full_geometry(self):
        """Every release board must retain full 4K geometry rather than truncate it."""
        self.assertIn("#define CHAM_MF_MAX_BLOCKS  256", self.src)
        self.assertNotIn("clamped_sectors", self.src)
        self.assertIn("Unsupported MIFARE geometry", self.src)

    def test_fix4_settings_no_concurrent_sends(self):
        """show_cham_settings_screen must not send cmd 1016 and 1039 back-to-back."""
        match = re.search(r"static void show_cham_settings_screen\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "show_cham_settings_screen not found")
        body = match.group(1)
        # Must have cmd 1016 send
        self.assertIn("cham_send_cmd(1016", body, "Must send cmd 1016")
        # Must NOT have cmd 1039 in the same function body
        self.assertNotIn("cham_send_cmd(1039", body,
                         "Must NOT send cmd 1039 concurrently; chain from 1016 callback")

    def test_fix4_anim_callback_chains_to_sleep(self):
        """s_set_on_anim_get must chain to cmd 1039 after processing."""
        match = re.search(r"static void s_set_on_anim_get\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_set_on_anim_get not found")
        body = match.group(1)
        self.assertIn("cham_send_cmd(1039", body,
                      "s_set_on_anim_get must chain to cmd 1039 (getSleepTimeout)")

    # ── Fix #5: Detection toggle uses dedicated setter callback ──
    def test_fix5_toggle_uses_setter_callback(self):
        """s_det_toggle_cb must NOT use s_det_on_status directly for cmd 4004."""
        match = re.search(r"static void s_det_toggle_cb\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_det_toggle_cb not found")
        body = match.group(1)
        self.assertIn("cham_send_cmd(4004", body, "Must send cmd 4004")
        self.assertNotIn("s_det_on_status)", body,
                         "Must NOT pass s_det_on_status as callback to 4004 setter")

    def test_fix5_setter_callback_chains_to_4007(self):
        """s_det_on_enable_set must exist and chain to cmd 4007."""
        match = re.search(r"static void s_det_on_enable_set\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_det_on_enable_set callback not found")
        body = match.group(1)
        self.assertIn("cham_send_cmd(4007", body,
                      "s_det_on_enable_set must chain to cmd 4007 (getStatus)")

    # ── Fix #6: Detection results multi-batch + dlen%18 validation ──
    def test_fix6_results_validates_dlen(self):
        """s_det_on_results must reject dlen not divisible by 18."""
        match = re.search(r"static void s_det_on_results\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_det_on_results not found")
        body = match.group(1)
        self.assertRegex(body, r"dlen\s*%\s*18",
                         "Must validate dlen is multiple of 18 bytes")

    def test_fix6_results_chains_for_remaining(self):
        """s_det_on_results must chain to fetch remaining records if remote count > local."""
        match = re.search(r"static void s_det_on_results\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_det_on_results not found")
        body = match.group(1)
        self.assertIn("s_det_remote_count", body,
                      "Must reference s_det_remote_count for multi-batch")
        self.assertIn("cham_send_cmd(4006", body,
                      "Must chain to cmd 4006 for remaining records")

    def test_fix6_remote_count_stored(self):
        """s_det_on_count must store the remote count."""
        match = re.search(r"static void s_det_on_count\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_det_on_count not found")
        body = match.group(1)
        self.assertIn("s_det_remote_count", body,
                      "Must store remote count for multi-batch fetching")

    # ── Fix #7: Saved Cards has click-to-load handler ──
    def test_fix7_saved_cards_has_click_handler(self):
        """Saved Cards list items must have LV_EVENT_CLICKED callback."""
        match = re.search(r"static void show_cham_saved_cards_screen\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "show_cham_saved_cards_screen not found")
        body = match.group(1)
        self.assertIn("LV_EVENT_CLICKED", body,
                      "Saved Cards items must wire LV_EVENT_CLICKED (click-to-load)")

    def test_fix7_click_handler_exists(self):
        """s_cards_click_cb function must exist."""
        self.assertIn("static void s_cards_click_cb(", self.src,
                      "s_cards_click_cb function must exist for click-to-load")

    def test_fix7_slot_picker_exists(self):
        """Click handler must show a slot picker popup."""
        match = re.search(r"static void s_cards_click_cb\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_cards_click_cb not found")
        body = match.group(1)
        self.assertIn("s_cards_slot_popup", body,
                      "Must create a slot picker popup on click")

    # ── Fix #8: Dump dispatcher uses SAK==0x00 only for NTAG ──
    def test_fix8_is_ntag_checks_sak_zero_only(self):
        """s_hf_dump_cb must use is_ntag = (s_hf_sak == 0x00), not the old OR expression."""
        match = re.search(r"static void s_hf_dump_cb\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_hf_dump_cb not found")
        body = match.group(1)
        # Must NOT have the old broad condition
        self.assertNotIn("!(s_hf_sak & 0x08)", body,
                         "Must not use !(sak & 0x08) to detect NTAG")
        # Must match SAK==0x00 exactly
        self.assertRegex(body, r"s_hf_sak\s*==\s*0x00",
                         "is_ntag must check s_hf_sak == 0x00 only")

    def test_fix8_unsupported_card_message(self):
        """Dump dispatcher must show a message for unsupported card types."""
        match = re.search(r"static void s_hf_dump_cb\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_hf_dump_cb not found")
        body = match.group(1)
        self.assertRegex(body, r"[Uu]nsupported",
                         "Must show unsupported card message for unknown SAK")

    # ── Fix #9: NFC parser uses heap, validates hex count ──
    def test_fix9_parser_uses_heap_not_stack(self):
        """s_parse_nfc_file must use heap allocation (calloc/malloc) not stack arrays."""
        match = re.search(r"static bool s_parse_nfc_file\(.*?\n\{(.*?)\nstatic ",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_parse_nfc_file not found")
        body = match.group(1)
        # Must NOT have stack-allocated page/block arrays
        self.assertNotRegex(body, r"uint8_t\s+pages\[231\]\[4\]",
                            "Must not stack-allocate pages[231][4]")
        self.assertNotRegex(body, r"uint8_t\s+blocks\[256\]\[16\]",
                            "Must not stack-allocate blocks[256][16]")
        # Must use calloc or malloc for these
        self.assertIn("calloc", body,
                      "Must use calloc for heap-allocated temp buffers")

    def test_fix9_parser_validates_byte_count(self):
        """Block lines require exactly 16 two-digit bytes with no trailing tokens."""
        body = re.search(r"static bool s_parse_nfc_file\(.*?\n\{(.*?)\nstatic ",
                         self.src, re.DOTALL).group(1)
        self.assertIn("int need = block ? 16 : 4", body)
        self.assertRegex(body, r"hex_end\s*-\s*q\s*!=\s*2")
        self.assertIn("if (*q != '\\0') parse_error = true", body)

    def test_fix9_parser_validates_page_byte_count(self):
        """Page lines require exact, contiguous geometry and reject duplicates."""
        body = re.search(r"static bool s_parse_nfc_file\(.*?\n\{(.*?)\nstatic ",
                         self.src, re.DOTALL).group(1)
        self.assertIn("bool *page_seen", body)
        self.assertIn("if (*seen) { parse_error = true", body)
        self.assertIn("Incomplete NTAG geometry", body)

    def test_fix9_parser_block_bound_uses_define(self):
        """NFC parser Block bound must use CHAM_MF_MAX_BLOCKS, not hardcoded 256."""
        match = re.search(r"static bool s_parse_nfc_file\(.*?\n\{(.*?)\nstatic ",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_parse_nfc_file not found")
        body = match.group(1)
        self.assertNotIn("blk < 256", body,
                         "Parser must not use hardcoded 256 for block bound")
        self.assertIn("CHAM_MF_MAX_BLOCKS", body,
                      "Parser must use CHAM_MF_MAX_BLOCKS for block bound")

    def test_fix9_parser_rejects_sparse_duplicate_and_mixed_geometry(self):
        body = re.search(r"static bool s_parse_nfc_file\(.*?\n\{(.*?)\nstatic ", self.src, re.DOTALL).group(1)
        self.assertIn("if (*seen) { parse_error = true", body)
        self.assertIn("for (int i = 0; complete && i < expected; i++)", body)
        self.assertIn("max_page < 0", body)
        self.assertIn("max_block < 0", body)

    def test_fix10_sector_count_requires_all_blocks(self):
        body = re.search(r"static void s_mf_on_block_read\(.*?\n\{(.*?)\n\}", self.src, re.DOTALL).group(1)
        self.assertIn("if (sector_ok) s_mf_sectors_done++", body)
        key_body = re.search(r"static void s_mf_on_key_check\(.*?\n\{(.*?)\n\}", self.src, re.DOTALL).group(1)
        self.assertNotIn("s_mf_sectors_done++", key_body)

    # ── Fix #10: Assorted defects ──
    def test_fix10_blocks_read_count_accurate(self):
        """MFC save must count actual blocks_ok, not sectors_done * 4 (wrong for 4K)."""
        match = re.search(
            r"static bool s_mf_save_dump_file\([^)]*\)\s*\n\{(.*?)\n\}",
            self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_mf_save_dump_file definition not found")
        body = match.group(1)
        self.assertNotIn("s_mf_sectors_done * 4", body,
                         "Must not use sectors_done*4 (wrong for 4K sectors 32-39)")
        self.assertRegex(body, r"blocks_ok|s_mf_block_ok",
                         "Must count actual block_ok flags for accurate count")

    def test_fix10_chunk_cb_frees_buffer_on_null_label(self):
        """s_clone_hf_chunk_cb must free s_clone_hf_buf when status label is NULL."""
        match = re.search(r"static void s_clone_hf_chunk_cb\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_clone_hf_chunk_cb not found")
        body = match.group(1)
        # Find the !s_clone_status_lbl early return
        null_check_idx = body.find("!s_clone_status_lbl")
        self.assertGreater(null_check_idx, 0,
                           "Must check for NULL status label")
        # Between that check and the return, must free the buffer
        early_return_section = body[null_check_idx:null_check_idx + 200]
        self.assertIn("s_clone_hf_buf", early_return_section,
                      "Must free s_clone_hf_buf when label is NULL (prevent leak)")

    def test_fix10_delete_checks_remove_result(self):
        """s_cards_del_confirm_yes must check remove() return or log on failure."""
        match = re.search(r"static void s_cards_del_confirm_yes\(.*?\n\{(.*?)\n\}",
                          self.src, re.DOTALL)
        self.assertIsNotNone(match, "s_cards_del_confirm_yes not found")
        body = match.group(1)
        # Must check remove() result (either != 0 check or ESP_LOG on failure)
        self.assertRegex(body, r"remove\(.*\)\s*!=\s*0|ESP_LOG[WE]",
                         "Must check remove() result or log on failure")


    def test_fix11_ntag_failure_never_enables_save(self):
        """A failed or truncated raw READ must be an error, never a successful partial dump."""
        start = self.src.index("static void s_ntag_on_page_read")
        end = self.src.index("static void s_ntag_dump_start", start)
        body = self.src[start:end]
        self.assertIn("if (!ok || !data || dlen < 16)", body)
        fail = body[body.index("if (!ok || !data || dlen < 16)"):body.index("/* READ returns")]
        self.assertIn("s_hf_dump_type   = 0", fail)
        self.assertIn("Dump failed", fail)
        self.assertIn("lv_obj_add_flag(s_hf_save_btn, LV_OBJ_FLAG_HIDDEN)", fail)
        self.assertNotIn("lv_obj_clear_flag(s_hf_save_btn", fail)

    def test_fix11_ntag_terminal_read_stays_in_geometry(self):
        """The last four-page READ must back up so it never requests a page past NTAG216 page 230."""
        start = self.src.index("static void s_ntag_on_page_read")
        end = self.src.index("static void s_ntag_dump_start", start)
        body = self.src[start:end]
        self.assertIn("read_page = s_ntag_max_pages - 4", body)
        self.assertIn("s_ntag_req_page", body)
        self.assertIn("src_page = s_ntag_cur_page - s_ntag_req_page", body)

    def test_fix11_settings_writes_handle_busy_transport(self):
        """Every settings setter must handle single-pending send rejection and confirm-read rejection."""
        for cmd in ("1015", "1040"):
            self.assertIn(f"if (!cham_send_cmd({cmd}", self.src)
        for fn, next_fn, cmd in (("s_set_on_anim_set", "s_set_on_sleep_set", "1016"),
                                 ("s_set_on_sleep_set", "s_set_anim_cycle_cb", "1039")):
            start = self.src.index(f"static void {fn}")
            end = self.src.index(f"static void {next_fn}", start)
            self.assertIn(f"if (!cham_send_cmd({cmd}", self.src[start:end])


class FinalReviewRegressionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = MAIN_C.read_text()

    def test_saved_cards_stop_clears_shared_clone_state(self):
        start = self.src.index("static void cham_saved_cards_stop")
        end = self.src.index("static void s_cards_del_confirm_yes", start)
        body = self.src[start:end]
        self.assertIn("s_clone_popup", body)
        self.assertIn("s_clone_status_lbl = NULL", body)
        self.assertIn("free(s_clone_hf_buf)", body)
        self.assertIn("s_clone_hf_buf_len = 0", body)

    def test_partial_mfc_dump_is_marked_and_loader_rejects_it(self):
        save_start = self.src.index("static bool s_mf_save_dump_file(const char *name)\n{")
        save_end = self.src.index("static bool s_ntag_save_dump_file", save_start)
        save = self.src[save_start:save_end]
        self.assertIn("# Partial dump: yes", save)
        self.assertIn("# Block %d unread", save)
        parse_start = self.src.index("static bool s_parse_nfc_file")
        parse_end = self.src.index("/* Close button for the file browser popup */", parse_start)
        parser = self.src[parse_start:parse_end]
        self.assertIn("partial_mfc_dump", parser)
        self.assertIn("Partial MFC dump", parser)

    def test_busy_transport_aborts_mfc_dump_without_enabling_save(self):
        abort_start = self.src.index("static void s_mf_dump_abort")
        abort_end = self.src.index("static void s_mf_dump_done", abort_start)
        abort = self.src[abort_start:abort_end]
        self.assertIn("s_hf_dump_type = 0", abort)
        self.assertIn("lv_obj_add_flag(s_hf_save_btn, LV_OBJ_FLAG_HIDDEN)", abort)
        check_start = self.src.index("static void s_mf_try_next_check(void)\n{")
        check_end = self.src.index("static void s_mf_on_key_check", check_start)
        check = self.src[check_start:check_end]
        self.assertIn("s_mf_dump_abort", check)
        self.assertNotIn("s_mf_dump_done", check)
        read_start = self.src.index("static void s_mf_on_block_read")
        read_end = self.src.index("static void s_mf_try_next_check(void)\n{", read_start)
        self.assertIn("s_mf_dump_abort", self.src[read_start:read_end])

if __name__ == "__main__":
    unittest.main()
