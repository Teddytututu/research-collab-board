"""First-run output and emote filesystem boundaries use local fixtures only."""
from pathlib import Path
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from board import onboarding

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work/t162-independent-review/test-fixtures'
WORK.mkdir(parents=True, exist_ok=True)


def module(name):
    spec = importlib.util.spec_from_file_location('boundary_' + name, ROOT / 'scripts' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class BootstrapBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=WORK)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bootstrap = module('bootstrap')
        self.installer = module('install_emotes')
        self.url = 'https://i0.hdslb.com/bfs/emote/' + 'a' * 40 + '.png'
        self.row = {'file': '123.png', 'url': self.url}
        image = io.BytesIO()
        Image.new('RGBA', (8, 8), (20, 90, 180, 255)).save(image, format='PNG')
        self.png = image.getvalue()

    def opener(self, *args, **kwargs):
        response = io.BytesIO(self.png)
        response.geturl = lambda: self.url
        return response

    def link_directory(self, link, target):
        link.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            env = dict(os.environ, RESEARCH_TEST_LINK=str(link), RESEARCH_TEST_TARGET=str(target))
            subprocess.run([shutil.which('powershell.exe') or 'pwsh', '-NoProfile', '-NonInteractive',
                            '-Command', '$null = New-Item -ItemType Junction -Path $env:RESEARCH_TEST_LINK -Target $env:RESEARCH_TEST_TARGET'],
                           env=env, check=True, capture_output=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        else:
            link.symlink_to(target, target_is_directory=True)

    def test_first_run_cp1252_keeps_prompt_choices_and_continues_registration(self):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding='cp1252', errors='strict')
        with patch.object(self.bootstrap, 'register_night_watch', return_value={'status': 'registered'}), contextlib.redirect_stdout(stream):
            result = self.bootstrap.first_run_options(sys.executable, self.root / 'data')
        stream.flush()
        text = raw.getvalue().decode(stream.encoding)
        self.assertEqual(result['night_watch']['status'], 'registered')
        self.assertTrue(result['emotes']['decision_required'])
        self.assertIn('225', text)
        self.assertIn('--download-emotes', text)
        self.assertIn('--unicode-emotes', text)
        self.assertIn('Unicode', text)

    def test_first_run_utf8_preserves_chinese_prompt(self):
        stream = io.StringIO()
        with patch.object(self.bootstrap, 'register_night_watch', return_value={'status': 'registered'}), contextlib.redirect_stdout(stream):
            self.bootstrap.first_run_options(sys.executable, self.root / 'data')
        self.assertIn(onboarding.EMOTE_PROMPT, stream.getvalue())

    def test_cp1252_download_failure_and_manual_registration_remain_actionable(self):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding='cp1252', errors='strict')
        watch = {'status': 'manual', 'manual_command': 'python scripts/install_night_watch.py --install',
                 'error': '调度错误', 'report': {'detail': '需手动接续'}}
        preferences = {'show_prompt': False, 'status': 'fallback', 'mode': 'unicode'}
        with patch.object(onboarding, 'configure_emotes', return_value=preferences), patch.object(self.bootstrap, 'register_night_watch', return_value=watch), contextlib.redirect_stdout(stream):
            result = self.bootstrap.first_run_options(sys.executable, self.root / 'data')
        stream.flush()
        text = raw.getvalue().decode(stream.encoding)
        self.assertEqual(result['night_watch']['status'], 'manual')
        self.assertIn('Unicode', text)
        self.assertIn('install_night_watch.py', text)

    def test_cp1252_unicode_manual_command_has_an_exact_local_record(self):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding='cp1252', errors='strict')
        command = 'python scripts/install_night_watch.py --project-root "研究目录" --install'
        watch = {'status': 'manual', 'manual_command': command}
        data = self.root / 'data'
        with patch.object(self.bootstrap, 'register_night_watch', return_value=watch), contextlib.redirect_stdout(stream):
            self.bootstrap.first_run_options(sys.executable, data)
        stream.flush()
        text = raw.getvalue().decode(stream.encoding)
        self.assertIn('attachments/onboarding.json', text)
        self.assertIn('install_night_watch.py', text)
        import json
        saved = json.loads((data / 'attachments/onboarding.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['night_watch']['manual_command'], command)

    def assert_redirect_rejected(self, data, link, target):
        self.link_directory(link, target)
        sentinel = target / 'keep.txt'
        sentinel.write_text('neighbor project sentinel', encoding='utf-8')
        opener = Mock(side_effect=self.opener)
        with patch.object(self.installer, 'emote_manifest', return_value=[self.row]):
            with self.assertRaises(ValueError):
                self.installer.install(data, opener=opener)
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'neighbor project sentinel')
        self.assertEqual(list(target.glob('*.png')), [])
        opener.assert_not_called()

    def test_emote_directory_junction_preserves_neighbor_project(self):
        data = self.root / 'project-A/data'
        self.assert_redirect_rejected(data, data / 'emotes', self.root / 'project-B/emotes')

    def test_data_root_junction_preserves_neighbor_project(self):
        data = self.root / 'project-A/data'
        self.assert_redirect_rejected(data, data, self.root / 'project-B/data')

    def test_data_ancestor_junction_preserves_neighbor_project(self):
        alias = self.root / 'alias'
        target = self.root / 'project-B'
        self.assert_redirect_rejected(alias / 'data', alias, target)
        self.assertFalse((target / 'data/emotes/123.png').exists())

    def test_png_path_junction_preserves_neighbor_project(self):
        data = self.root / 'project-A/data'
        self.assert_redirect_rejected(data, data / 'emotes/123.png', self.root / 'project-B/png-target')

    def test_partial_path_junction_preserves_neighbor_project(self):
        data = self.root / 'project-A/data'
        self.assert_redirect_rejected(data, data / 'emotes/123.partial', self.root / 'project-B/partial-target')

    def test_valid_public_png_download_and_reuse_stay_local(self):
        data = self.root / 'data'
        opener = Mock(side_effect=self.opener)
        with patch.object(self.installer, 'emote_manifest', return_value=[self.row]):
            first = self.installer.install(data, opener=opener)
            again = self.installer.install(data, opener=opener)
        self.assertEqual(first, {'downloaded': 1, 'reused': 0, 'failed': 0})
        self.assertEqual(again, {'downloaded': 0, 'reused': 1, 'failed': 0})
        self.assertEqual((data / 'emotes/123.png').read_bytes(), self.png)
        self.assertEqual(opener.call_count, 1)

    def test_stale_regular_partial_is_preserved_while_download_finishes(self):
        data = self.root / 'data'
        partial = data / 'emotes/123.partial'
        partial.parent.mkdir(parents=True)
        partial.write_bytes(b'prior partial')
        with patch.object(self.installer, 'emote_manifest', return_value=[self.row]):
            result = self.installer.install(data, opener=self.opener)
        self.assertEqual(result['downloaded'], 1)
        self.assertEqual(partial.read_bytes(), b'prior partial')
        self.assertEqual((data / 'emotes/123.png').read_bytes(), self.png)
        self.assertEqual(list(partial.parent.glob('123.png.*.partial')), [])

    def test_directory_redirection_during_response_keeps_download_inside_data(self):
        data = self.root / 'project-A/data'
        target = data / 'emotes'
        neighbor = self.root / 'project-B/emotes'
        def redirect(*args, **kwargs):
            target.rename(data / 'emotes-before-response')
            self.link_directory(target, neighbor)
            return self.opener()
        with patch.object(self.installer, 'emote_manifest', return_value=[self.row]):
            result = self.installer.install(data, opener=redirect)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(list(neighbor.iterdir()), [])
        self.assertEqual(list((data / 'emotes-before-response').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
