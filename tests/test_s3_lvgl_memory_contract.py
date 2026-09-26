#!/usr/bin/env python3
"""Regression contract for ES3C35P LVGL allocation capacity."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class S3LvglMemoryContract(unittest.TestCase):
    def test_s3_uses_shared_psram_backed_lvgl_allocator(self):
        defaults = (ROOT / "ESP32S3/sdkconfig.defaults").read_text()
        self.assertIn("CONFIG_LV_MEM_CUSTOM=y", defaults)
        self.assertIn('CONFIG_LV_MEM_CUSTOM_INCLUDE="lvgl_memory.h"', defaults)

        cmake = (ROOT / "ESP32S3/main/CMakeLists.txt").read_text()
        self.assertIn('"${C5_MAIN}/lvgl_memory.c"', cmake)

        allocator = (ROOT / "ESP32C5/main/lvgl_memory.c").read_text()
        self.assertIn("MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT", allocator)


if __name__ == "__main__":
    unittest.main(verbosity=2)
