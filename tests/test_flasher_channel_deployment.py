import os, subprocess, tempfile, textwrap, unittest
from pathlib import Path
R = Path(__file__).resolve().parents[1]
class ChannelDeployment(unittest.TestCase):
    def test_root_tracks_dev_and_beta_pins_revision(self):
        workflow = (R / '.github/workflows/deploy-flasher.yml').read_text()
        block = workflow.split("          python3 - <<'PY'\n")[-1].split('\n          PY')[0]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '_site/beta').mkdir(parents=True)
            (root / '_site/beta/index.html').write_bytes((R / 'ESP32C5/docs/index.html').read_bytes())
            sha = 'a' * 40
            subprocess.run(['python3', '-B', '-c', textwrap.dedent(block)], cwd=d,
                           env=dict(os.environ, GITHUB_SHA=sha), check=True)
            normal = (root / '_site/index.html').read_text()
            beta = (root / '_site/beta/index.html').read_text()
            self.assertIn('const BRANCH = { stable: "main", dev: "Jimgat_Dev" };', normal)
            self.assertIn('dev: "' + sha + '"', beta)
            self.assertIn('const betaUnlock = true;', beta)
            self.assertIn('cache: "no-store"', normal)
if __name__ == '__main__': unittest.main()
