#!/usr/bin/env python3
"""Contract for the Modern Attack-category authorization gate."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "ESP32C5/main/main.c").read_text()


class ModernAttackDisclaimerContract(unittest.TestCase):
    def test_modern_attack_tile_uses_shared_warning(self):
        self.assertIn(
            'if      (strcmp(key, "CAT:Attack") == 0) show_attack_warning(show_cat_attack);',
            SOURCE,
        )

    def test_other_modern_categories_remain_direct(self):
        self.assertIn('strcmp(key, "CAT:Defend") == 0) show_cat_defend();', SOURCE)
        self.assertIn('strcmp(key, "CAT:Recon")  == 0) show_cat_recon();', SOURCE)
        self.assertIn('strcmp(key, "CAT:Tools")  == 0) show_cat_tools();', SOURCE)

    def test_warning_title_is_plural(self):
        self.assertIn(
            'lv_label_set_text(title, LV_SYMBOL_WARNING " ACTIVE ATTACKS " LV_SYMBOL_WARNING);',
            SOURCE,
        )

    def test_warning_copy_covers_authorization_and_law(self):
        start = SOURCE.index("static void show_attack_warning(void (*proceed_fn)(void))\n{")
        end = SOURCE.index("// Proceed wrappers", start)
        popup = SOURCE[start:end]
        match = re.search(r'lv_label_set_text\(msg,\s*(.*?)\);', popup, re.DOTALL)
        self.assertIsNotNone(match)
        literals = re.findall(r'"((?:\\.|[^"\\])*)"', match.group(1))
        message = "".join(literals).replace(r"\n", " ")
        self.assertIn("explicit authorization", message)
        self.assertIn("laws that apply in your country", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
