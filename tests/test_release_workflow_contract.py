from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowContract(unittest.TestCase):
    def test_main_push_packages_but_does_not_publish_release(self):
        workflow = (ROOT / ".github/workflows/esp32c5-build-master.yml").read_text()
        start = workflow.index("\n  release:\n    name: Release")
        release_job = workflow[start:workflow.index("\n  discord:", start)]
        self.assertNotIn("refs/heads/main", release_job)
        self.assertNotIn("refs/heads/master", release_job)
        self.assertIn("github.event_name == 'release'", release_job)
        self.assertIn("github.event_name == 'workflow_dispatch'", release_job)
        self.assertIn("inputs.release_tag != ''", release_job)

    def test_release_build_uses_canonical_nm_profile(self):
        workflow = (ROOT / ".github/workflows/esp32c5-build-master.yml").read_text()
        self.assertIn("bash scripts/build.sh nm-cyd-c5", workflow)
        self.assertNotIn("bash ESP32C5/.github/scripts/container_build.sh --no-docker", workflow)


if __name__ == "__main__":
    unittest.main()
