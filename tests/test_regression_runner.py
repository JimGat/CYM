"""Runner control-plane tests use synthetic scripts, never firmware or serial I/O."""
from pathlib import Path
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import run_regression as runner


class RunnerContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def entry(self, text):
        script = self.root/'fixture.py'
        script.write_text(text)
        output = self.root/'output'
        output.mkdir()
        return dict(kind='script', path=str(script), requires=[]), output

    def test_real_failure_exit(self):
        entry, output = self.entry('raise SystemExit(7)\n')
        result = runner.execute_entry(entry, output, 5)
        self.assertEqual((result['status'], result['exit_code']), ('FAIL', 7))

    def test_generated_build_prerequisite(self):
        with patch.object(runner, 'ROOT', self.root):
            self.assertIn('generated board config absent', runner.missing('generated-tick-configs'))

    def test_required_dependency_is_not_run(self):
        entry, output = self.entry('raise AssertionError("must not execute")\n')
        entry['requires']=['idf-nimble']
        with patch.dict(os.environ, {}, clear=True):
            result=runner.execute_entry(entry, output, 5)
        self.assertEqual(result['status'], 'NOT_RUN')
        self.assertIn('IDF_PATH',result['reason'])
        self.assertFalse((output/'run.log').exists())

    def test_optional_capture_skip_is_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            result=runner.execute_entry(dict(kind='private'), self.root, 5)
        self.assertEqual(result['status'],'SKIP')
        self.assertIn('private captures',result['reason'])

    def test_empty_and_all_skip_are_not_green(self):
        module=types.ModuleType('synthetic_runner_empty')
        with patch.dict(sys.modules,{module.__name__:module}), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runner.unit_worker(module.__name__,self.root),3)
            class Skipped(unittest.TestCase):
                @unittest.skip('synthetic optional dependency')
                def test_skip(self):pass
            module.Skipped=Skipped
            self.assertEqual(runner.unit_worker(module.__name__,self.root),3)
        summary=json.loads((self.root/'unittest.json').read_text())
        self.assertEqual(summary['passed'],0)
        self.assertEqual(len(summary['skips']),1)

    def test_real_timeout_reaps_process_group(self):
        output=self.root/'timeout';output.mkdir()
        code,reason=runner.run_process([sys.executable,'-c','import time;time.sleep(30)'],output,os.environ.copy(),1)
        self.assertEqual(reason,'per-gate timeout')
        self.assertNotEqual(code,0)

    def test_real_log_size_bound(self):
        output=self.root/'large-log';output.mkdir()
        code,reason=runner.run_process([sys.executable,'-c',"import sys;sys.stdout.write('x'*(9*1024*1024))"],output,os.environ.copy(),5)
        self.assertEqual(reason,'log exceeded 8 MiB limit')
        self.assertLessEqual((output/'run.log').stat().st_size,8*1024*1024)

    def test_existing_output_preserved(self):
        output=self.root/'existing';output.mkdir();sentinel=output/'sentinel';sentinel.write_bytes(b'preserve\x00exact')
        with patch.object(sys,'argv',['run_regression.py','--output',str(output)]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:runner.main()
        self.assertEqual(caught.exception.code,2)
        self.assertEqual(sentinel.read_bytes(),b'preserve\x00exact')
        self.assertEqual(sorted(p.name for p in output.iterdir()),['sentinel'])

    def test_fail_fast_records_later_not_run(self):
        # Fake manifest only, not a copy of a CYM checkout.
        (self.root/'tests').mkdir();(self.root/'ESP32C5/main').mkdir(parents=True)
        (self.root/'ESP32C5/main/main.c').write_text('synthetic control-plane fixture\n')
        entries=[dict(id=n,suite='portable',taxonomy='synthetic',kind='script',path='unused',requires=[]) for n in ['first','second']]
        (self.root/'tests/regression-manifest.json').write_text(json.dumps(dict(entries=entries)))
        output=self.root/'report'
        with patch.object(runner,'ROOT',self.root), patch.object(runner,'execute_entry',return_value=dict(status='FAIL',exit_code=7)) as execute, patch.object(sys,'argv',['run_regression.py','--output',str(output)]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(),1)
        self.assertEqual(execute.call_count,1)
        report=json.loads((output/'results.json').read_text())
        self.assertEqual([r['status'] for r in report['results']],['FAIL','NOT_RUN'])
        self.assertEqual(report['counts']['NOT_RUN'],1)


if __name__=='__main__':unittest.main()
