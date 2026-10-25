"""First-use script paths in a clean copy with real site-packages disabled."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OptionalArtwork(unittest.TestCase):
    def setUp(self):
        folder = ROOT / 'work/tests'
        folder.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(self.tmp.cleanup)
        self.package = Path(self.tmp.name) / 'clean-package'
        self.package.mkdir()
        for name in ['board', 'scripts', 'assets', 'demo']:
            shutil.copytree(ROOT / name, self.package / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.write.lock'))
        self.data = self.package / 'work/fixture-data'
        self.python = getattr(sys, '_base_executable', sys.executable)
        self.env = {k: v for k, v in os.environ.items() if k not in ['PYTHONPATH', 'PYTHONHOME']}
        self.assertFalse((self.package / '.venv').exists())

    def run_python(self, *args, isolated=True):
        flags = ['-I', '-S'] if isolated else ['-S']
        return subprocess.run([self.python, *flags, '-X', 'utf8', '-B', *args], cwd=self.package,
                              env=self.env, capture_output=True, text=True, encoding='utf-8', timeout=30)

    def script(self, name, *args):
        return self.run_python(str(self.package / 'scripts' / name), *args)

    def test_status_checks_report_pillow_requirement_and_keep_existing_art_bytes(self):
        probe = self.run_python('-c', "import importlib.util,sys; assert importlib.util.find_spec('PIL') is None; assert sys.prefix == sys.base_prefix")
        self.assertEqual(probe.returncode, 0, probe.stderr)
        image = self.data / 'attachments/generated/GPT/avatar.png'
        image.parent.mkdir(parents=True)
        raw = b'preserved custom PNG fixture'
        image.write_bytes(raw)
        result = self.script('onboarding.py', 'status', 'GPT', '--data-dir', str(self.data))
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(result.stdout)
        self.assertFalse(status['checks']['artwork'])
        self.assertIn('artwork', status['pending'])
        for row in status['artwork']['files']:
            self.assertIn('Pillow', row['reason'])
            self.assertIn('python -m pip install -r requirements.txt', row['reason'])
            self.assertFalse(row['valid'])
        custom = next(row for row in status['generated_artwork']['files'] if Path(row['file']).parts[-2:] == ('GPT', 'avatar.png'))
        self.assertIn('Pillow', custom['reason'])
        self.assertEqual(image.read_bytes(), raw)
        self.assertTrue((self.data / 'attachments/state.json').is_file())

    def test_artwork_list_preserves_job_records_without_loading_pixels(self):
        ledger = self.data / 'attachments/provider-images.json'
        ledger.parent.mkdir(parents=True)
        raw = b'{"fixture-job":{"status":"completed","saved_path":"fixture.png"}}'
        ledger.write_bytes(raw)
        result = self.script('artwork.py', 'list', '--data-dir', str(self.data))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads(raw))
        self.assertEqual(ledger.read_bytes(), raw)

    def test_deploy_explains_dependency_before_any_image_write(self):
        result = self.script('artwork.py', 'deploy', 'GPT', '--ids', *['job-' + str(i) for i in range(7)],
                             '--data-dir', str(self.data))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('Pillow', result.stderr)
        self.assertIn('python -m pip install -r requirements.txt', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse(self.data.exists())

    def test_optional_emotes_keep_unicode_and_report_missing_image_dependency(self):
        # -I -S guarantees the dependency check runs before the real downloader.
        result = self.script('onboarding.py', 'emotes', '--download-emotes', '--data-dir', str(self.data))
        self.assertEqual(result.returncode, 0, result.stderr)
        preferences = json.loads(result.stdout)
        self.assertEqual(preferences['mode'], 'unicode')
        self.assertEqual(preferences['status'], 'fallback')
        self.assertIn('Pillow', preferences['error'])
        self.assertIn('python -m pip install -r requirements.txt', preferences['error'])
        self.assertFalse((self.data / 'emotes').exists())

    def test_help_and_text_commands_use_actual_first_use_entries(self):
        for script in ['onboarding.py', 'artwork.py', 'post_message.py']:
            result = self.script(script, '--help')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage:', result.stdout)
        result = self.run_python('-m', 'board', '--help', isolated=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_python('-m', 'board', 'schedule', '--data-dir', str(self.data), isolated=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('agents', json.loads(result.stdout))
        posted = self.script('post_message.py', 'GPT', 'Disposable text fixture', '--root', str(self.data))
        self.assertEqual(posted.returncode, 0, posted.stderr)
        recent = self.script('post_message.py', '--recent', '--root', str(self.data))
        self.assertEqual(recent.returncode, 0, recent.stderr)
        self.assertEqual(json.loads(recent.stdout)[0]['body'], 'Disposable text fixture')


if __name__ == '__main__':
    unittest.main()
