"""Frozen queue result identities follow the destination filesystem."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('queue_identity_subject', ROOT / 'scripts/run_queue.py')
queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queue)


class QueueResultIdentity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='queue identity ', dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {'output': 'batch', 'items': [{'id': 'SAMPLE-A', 'value': 1}, {'id': 'sample-a', 'value': 2}]}

    def test_windows_case_collision_rejected_before_callbacks_and_output(self):
        if os.name != 'nt':
            return
        calls = []
        with self.assertRaisesRegex(ValueError, 'Frozen input.*collision') as caught:
            queue.run_queue(self.config, lambda row: calls.append(row['id']) or row['value'], project_root=self.root)
        self.assertIn('SAMPLE-A', str(caught.exception))
        self.assertIn('sample-a', str(caught.exception))
        self.assertEqual(calls, [])
        self.assertFalse((self.root / 'batch').exists())

    def test_insensitive_destination_collision_on_any_platform(self):
        calls = []
        with patch.object(queue, 'result_directory_case_sensitive', return_value=False, create=True):
            with self.assertRaisesRegex(ValueError, 'Frozen input.*collision'):
                queue.run_queue(self.config, lambda row: calls.append(row), project_root=self.root)
        self.assertEqual(calls, [])
        self.assertFalse((self.root / 'batch').exists())

    def test_sensitive_destination_retains_distinct_case_ids(self):
        if os.name == 'nt':
            # A real sensitive-filesystem execution runs on POSIX; validate its
            # identity branch against uncreated distinct destinations on Windows.
            with patch.object(queue, 'result_directory_case_sensitive', return_value=True, create=True):
                self.assertIsNone(queue.validate_result_paths({'SAMPLE-A': self.root / 'results/SAMPLE-A.json',
                                                               'sample-a': self.root / 'results/sample-a.json'}))
            return
        if not queue.result_directory_case_sensitive(self.root):
            with patch.object(queue, 'result_directory_case_sensitive', return_value=True):
                self.assertIsNone(queue.validate_result_paths({'SAMPLE-A': self.root / 'results/SAMPLE-A.json',
                                                               'sample-a': self.root / 'results/sample-a.json'}))
            return
        calls = []
        result = queue.run_queue(self.config, lambda row: calls.append(row['id']) or row['value'], project_root=self.root)
        self.assertEqual((result['done'], result['total']), (2, 2))
        self.assertEqual(calls, ['SAMPLE-A', 'sample-a'])
        self.assertEqual(len(list((self.root / 'batch/results').glob('*.json'))), 2)
        calls.clear()
        queue.run_queue(self.config, lambda row: calls.append(row), project_root=self.root)
        self.assertEqual(calls, [])

    def test_preexisting_hardlink_alias_rejected_with_original_bytes_retained(self):
        results = self.root / 'batch/results'
        results.mkdir(parents=True)
        first, second = results / 'first.json', results / 'second.json'
        first.write_text('{"complete":false}', encoding='utf-8')
        os.link(first, second)
        before = first.read_bytes()
        calls = []
        with self.assertRaisesRegex(ValueError, 'Frozen input.*collision'):
            queue.run_queue({'output': 'batch', 'items': [{'id': 'first'}, {'id': 'second'}]},
                            lambda row: calls.append(row), project_root=self.root)
        self.assertEqual(calls, [])
        self.assertEqual((first.read_bytes(), second.read_bytes()), (before, before))
        self.assertFalse((self.root / 'batch/progress.json').exists())

    def test_portable_noncolliding_ids_keep_callbacks_and_restore_skip(self):
        config = {'output': 'batch', 'items': [{'id': 'SAMPLE-A'}, {'id': 'sample-b'}]}
        calls = []
        result = queue.run_queue(config, lambda row: calls.append(row['id']) or {'id': row['id']}, project_root=self.root)
        self.assertEqual((result['done'], result['total']), (2, 2))
        self.assertEqual(calls, ['SAMPLE-A', 'sample-b'])
        calls.clear()
        result = queue.run_queue(config, lambda row: calls.append(row), project_root=self.root)
        self.assertEqual(calls, [])
        self.assertEqual(result['done'], 2)

    def test_cli_rejects_collision_before_handler_module_load(self):
        if os.name != 'nt':
            return
        handler = self.root / 'handler.py'
        marker = self.root / 'handler-loaded.txt'
        handler.write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("loaded")\ndef process(row):\n    return 1\n', encoding='utf-8')
        config = dict(self.config, handler_file='handler.py')
        (self.root / 'queue.json').write_text(json.dumps(config), encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/run_queue.py'), 'queue.json',
                                 '--project-root', str(self.root)], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Frozen input', result.stderr)
        self.assertFalse(marker.exists())

    def test_probe_uses_nearest_existing_destination_and_cleans_temporary_file(self):
        directory = self.root / 'batch'
        directory.mkdir()
        before = list(directory.iterdir())
        sensitive = queue.result_directory_case_sensitive(directory / 'new/results')
        self.assertIsInstance(sensitive, bool)
        self.assertEqual(list(directory.iterdir()), before)
        self.assertFalse((directory / 'new').exists())
        if os.name == 'nt':
            self.assertFalse(sensitive)

    def test_reproduction_resume_rejects_before_touching_old_result_and_progress(self):
        if os.name != 'nt':
            return
        results = self.root / 'batch/results'
        results.mkdir(parents=True)
        result = results / 'SAMPLE-A.json'
        result.write_text(json.dumps({'id': 'sample-a', 'complete': True, 'result': 2,
                                     'input_sha256': queue.fingerprint(self.config['items'][1])}), encoding='utf-8')
        progress = results.parent / 'progress.json'
        progress.write_text('{"done":2,"total":2,"state":"complete"}', encoding='utf-8')
        before = (result.read_bytes(), progress.read_bytes())
        calls = []
        with self.assertRaisesRegex(ValueError, 'Frozen input.*collision'):
            queue.run_queue(self.config, lambda row: calls.append(row), project_root=self.root)
        self.assertEqual(calls, [])
        self.assertEqual((result.read_bytes(), progress.read_bytes()), before)


if __name__ == '__main__':
    unittest.main()
