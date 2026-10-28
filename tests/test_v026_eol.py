"""Exercise the staged-blob EOL guard in disposable Git repositories."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture')
        for name, raw in {'lf.txt': b'a\nb\n', 'crlf.txt': b'a\r\nb\r\n',
                          'mixed.txt': b'a\r\nb\n', 'binary.dat': b'a\0\r\nb',
                          'space name.txt': b'first\n' + b'unchanged line\n' * 50}.items():
            (self.root / name).write_bytes(raw)
        self.git('add', '.')
        self.git('commit', '-qm', 'Fixture')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True).stdout

    def guard(self):
        done = subprocess.run([sys.executable, str(ROOT / 'scripts/check_eol.py'),
                               '--repo', str(self.root)], capture_output=True,
                              text=True, encoding='utf-8')
        self.assertTrue(done.stdout.strip(), done.stderr)
        return done.returncode, json.loads(done.stdout)

    def test_reports_lf_to_crlf_and_crlf_to_lf_with_paths(self):
        (self.root / 'lf.txt').write_bytes(b'a\r\nchanged\r\n')
        (self.root / 'crlf.txt').write_bytes(b'a\nchanged\n')
        self.git('add', '.')
        code, out = self.guard()
        self.assertEqual(code, 1, out)
        self.assertEqual({i['path'] for i in out['changes']}, {'lf.txt', 'crlf.txt'})

    def test_only_staged_content_counts_and_binary_is_skipped(self):
        (self.root / 'lf.txt').write_bytes(b'a\nchanged\n')
        (self.root / 'binary.dat').write_bytes(b'a\0\nb')
        self.git('add', '.')
        (self.root / 'lf.txt').write_bytes(b'a\r\nchanged\r\n')
        self.assertEqual(self.guard()[0], 0)

    def test_added_deleted_and_renamed_files(self):
        self.git('mv', 'space name.txt', 'renamed name.txt')
        (self.root / 'renamed name.txt').write_bytes(b'first\r\n' + b'unchanged line\n' * 50)
        (self.root / 'new.txt').write_bytes(b'new\r\n')
        self.git('rm', 'crlf.txt')
        self.git('add', '.')
        code, out = self.guard()
        self.assertEqual(code, 1, out)
        self.assertEqual([i['path'] for i in out['changes']], ['renamed name.txt'])

    def test_mixed_eols_are_detected_and_counts_can_change(self):
        (self.root / 'mixed.txt').write_bytes(b'a\nb\n')
        (self.root / 'lf.txt').write_bytes(b'a\nb\nc\n')
        self.git('add', '.')
        self.assertEqual([i['path'] for i in self.guard()[1]['changes']], ['mixed.txt'])

    def test_fresh_repository_has_no_prior_style(self):
        other = self.root / 'fresh'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True, capture_output=True)
        (other / 'file.txt').write_bytes(b'first\n')
        subprocess.run(['git', '-C', str(other), 'add', '.'], check=True, capture_output=True)
        done = subprocess.run([sys.executable, str(ROOT / 'scripts/check_eol.py'), '--repo', str(other)], capture_output=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_verify_and_release_abort_before_other_work_when_guard_fails(self):
        from unittest.mock import patch
        for name in ('verify', 'release'):
            spec = importlib.util.spec_from_file_location('guarded_' + name, ROOT / 'scripts' / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with patch.object(module, 'check_eol', return_value=1, create=True), \
                    patch('unittest.defaultTestLoader.discover', side_effect=AssertionError('Tests ran before EOL check')):
                if name == 'release':
                    with self.assertRaises(SystemExit) as result:
                        module.main()
                    self.assertEqual(result.exception.code, 1)
                else:
                    self.assertEqual(module.main(), 1)


if __name__ == '__main__':
    unittest.main()
