"""Actual production NTP/Clock host regressions (socket/RTOS boundary fakes)."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class NtpLifecycleHost(unittest.TestCase):
    def test_production_server(self):
        subprocess.run([sys.executable, str(ROOT / "tests/run_ntp_lifecycle_host.py")], check=True)

    def test_production_clock_owner(self):
        subprocess.run([sys.executable, str(ROOT / "tests/run_ntp_clock_owner_host.py")], check=True)
