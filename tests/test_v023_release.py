"""Release contains its offline setup and retains private-data boundaries."""
from pathlib import Path
import runpy
import unittest
import contextlib
import hashlib
import io
import json
import tempfile
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RELEASE = runpy.run_path(str(ROOT / 'scripts/release.py'))


class ReleaseBoundary(unittest.TestCase):
    def test_required_installation_and_report_assets_are_shipped(self):
        names = RELEASE['files']()
        for name in ['当前指令.md', 'scripts/night_watch.py', 'scripts/run_queue.py',
                     'scripts/install_night_watch.py', 'scripts/install-night-watch.ps1',
                     'docs/night-watch.md', 'protocol/writing.md',
                     'skills/research-report-writing/SKILL.md',
                     'skills/research-report-writing/templates/report_helpers.py']:
            self.assertIn(name, names)
        self.assertTrue(all((ROOT / name).is_file() for name in names))
        self.assertTrue(all(not name.startswith(('data/', 'work/', '.venv/')) for name in names))
        self.assertEqual(sum(name.startswith('board/art/') and name.endswith('.png') for name in names), 33)

    def test_public_optional_emote_documentation_is_allowed(self):
        for name in ['README.md', 'README.zh-CN.md', 'scripts/bootstrap.py']:
            self.assertEqual(RELEASE['scan'](b'Optional Bilibili emotes use bili:42 after consent.', name), [])

    def test_public_words_preserve_credential_and_private_media_checks(self):
        scan = RELEASE['scan']
        self.assertIn('private_media_reference', scan(b'Bilibili /chat-img/' + b'a' * 32 + b'.png', 'README.md'))
        self.assertIn('literal_credential', scan(b'password="' + b'A' * 30 + b'"', 'README.md'))
        self.assertIn('private_key', scan(b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----', 'README.md'))
        self.assertIn('email', scan(b'person' + b'@' + b'example.org', 'README.md'))

    def test_report_skill_work_files_stay_outside_release(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work/tests') as folder:
            root=Path(folder)
            private=root/'skills/research-report-writing/work/local-notes.json'
            private.parent.mkdir(parents=True)
            private.write_text('{"local":"private fixture"}',encoding='utf-8')
            with patch.dict(RELEASE['files'].__globals__,ROOT=root):
                self.assertNotIn(private.relative_to(root).as_posix(),RELEASE['files']())

    def test_archive_uses_the_exact_scanned_bytes_during_concurrent_edit(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work/tests') as folder:
            root=Path(folder);source=root/'README.md';clean=b'Public fixture\n'
            source.write_bytes(clean)
            def edit_after_scan(blob,name):
                source.write_text('Concurrent local draft',encoding='utf-8')
                return []
            with patch.dict(RELEASE['main'].__globals__,ROOT=root,files=lambda:['README.md'],scan=edit_after_scan),contextlib.redirect_stdout(io.StringIO()):
                RELEASE['main']()
            report=json.loads((root/'work/releases/privacy-scan.json').read_text('utf-8'))
            archive=root/'work/releases'/('research-collab-board-'+RELEASE['VERSION']+'.zip')
            with zipfile.ZipFile(archive) as z:
                packed=z.read('research-collab-board/README.md')
            self.assertEqual(packed,clean)
            self.assertEqual(hashlib.sha256(packed).hexdigest(),report['manifest'][0]['sha256'])


if __name__ == '__main__':
    unittest.main()
