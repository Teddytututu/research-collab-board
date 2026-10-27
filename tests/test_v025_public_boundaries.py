"""Generic read/write ownership, text encoding and worker lifecycle boundaries."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from board import app, lifecycle, project, storage, task_eta, workers

ROOT = Path(__file__).resolve().parents[1]


def watch_module():
    spec = importlib.util.spec_from_file_location('boundary_watch', ROOT / 'scripts/night_watch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


class ReadOwnership(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        project.initialize(self.root, 'Example', 'Compare options', 'Review')
        storage.write(self.root / 'attachments/state.json', {
            'runs': {'sample': {'done': 1, 'total': 4, 'source_at': 1000}},
            'tasks': {}, 'keep': {'value': 7}})

    def test_three_snapshots_retain_every_persisted_byte_and_history(self):
        before = files(self.root)
        for _ in range(3):
            self.assertIn('overview', app.snapshot(self.root))
        self.assertEqual(files(self.root), before)

    def test_project_uses_persisted_observations_without_sampling(self):
        before = files(self.root)
        result = task_eta.project(self.root, {'tree': []}, now=1100)
        self.assertEqual(result['runs'][0]['done'], 1)
        self.assertEqual(files(self.root), before)

    def test_project_absent_state_retains_supplied_overview(self):
        with tempfile.TemporaryDirectory() as directory:
            overview = {'tree': [{'title': 'Example'}]}
            self.assertEqual(task_eta.project(Path(directory), overview, now=1000), overview)
            self.assertEqual(files(Path(directory)), {})

    def test_snapshot_carries_explicit_task_stage_to_the_public_formatter(self):
        stage = {'label': 'Review', 'done': 2, 'total': 8}
        storage.write(self.root / 'attachments/state.json', {
            'tasks': {'T001': {'status': 'daily 10/27', 'current_stage': stage}}, 'runs': {}})
        before = files(self.root)
        task = next(t for t in app.snapshot(self.root)['tasks'] if t['id'] == 'T001')
        self.assertEqual(task['current_stage'], stage)
        self.assertEqual(files(self.root), before)

    def test_timed_patrol_samples_and_second_identical_poll_is_throttled(self):
        watch = watch_module()
        parent = self.root.parent
        data = self.root.name
        watch.patrol(parent, data_dir=data, now=1000)
        state = storage.read(self.root / 'attachments/state.json')
        self.assertEqual(state['eta_tracking']['observations']['sample'][0]['done'], 1)
        self.assertEqual(state['keep'], {'value': 7})
        first = (self.root / 'attachments/state.json').read_bytes()
        watch.patrol(parent, data_dir=data, now=1100)
        self.assertEqual((self.root / 'attachments/state.json').read_bytes(), first)
        self.assertEqual(len(storage.read(self.root / 'attachments/state.json')
                             ['eta_tracking']['observations']['sample']), 1)

    def test_patrol_calls_eta_writer_after_registry_lock_releases(self):
        watch = watch_module()
        active = []
        original = storage.locked
        from contextlib import contextmanager
        @contextmanager
        def locked(root):
            with original(root):
                active.append(root)
                try:
                    yield
                finally:
                    active.pop()
        def refresh(root, overview, now=None):
            self.assertEqual(active, [])
            self.assertEqual(root, self.root)
            self.assertEqual(now, 1000)
            return overview
        with patch.object(watch.storage, 'locked', locked), patch.object(task_eta, 'refresh', side_effect=refresh) as writer:
            watch.patrol(self.root.parent, data_dir=self.root.name, now=1000)
        writer.assert_called_once()


class EncodedLifecycle(unittest.TestCase):
    def test_board_spec_and_archive_keep_each_encoding_through_all_actions(self):
        for newline in ('\n', '\r\n'):
            for bom in (b'', b'\xef\xbb\xbf'):
                with self.subTest(newline=newline, bom=bool(bom)), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    project.initialize(root, 'Example', 'Question', 'Result')
                    (root / 'tasks').mkdir()
                    spec = root / 'tasks/T001-example.md'
                    archive = root / 'tasks/archive.md'
                    originals = {}
                    for path, text in ((root / 'board.md', '# Example\n\n| ID | Task | Status | Owner | Updated |\n| --- | --- | --- | --- | --- |\n'),
                                       (spec, '# Example\n\nScope and evidence.\n'),
                                       (archive, '# Task archive\n\n| ID | Task | Status | Owner | Updated |\n| --- | --- | --- | --- | --- |\n')):
                        raw = bom + text.replace('\n', newline).encode()
                        path.write_bytes(raw)
                        originals[path] = raw
                    def move(action, **fields):
                        return lifecycle.transition(root, action, 'T001', by='Claude' if action in {'new', 'accept'} else 'GPT', **fields)
                    move('new', title='Example', when='Ready')
                    move('start', status='0/2 · 估不了：fixture')
                    move('progress', status='1/2')
                    evidence = root / 'attachments/result.md'
                    evidence.write_bytes(b'Example evidence\n')
                    move('deliver', evidence='attachments/result.md')
                    move('accept', summary='Reviewed')
                    for path in originals:
                        raw = path.read_bytes()
                        self.assertEqual(raw.startswith(b'\xef\xbb\xbf'), bool(bom), path.name)
                        body = raw.removeprefix(b'\xef\xbb\xbf')
                        if newline == '\r\n':
                            self.assertNotIn(b'\n', body.replace(b'\r\n', b''), path.name)
                        else:
                            self.assertNotIn(b'\r', body, path.name)
                        self.assertIn(originals[path], [p.read_bytes() for p in (path.parent / 'history').glob('*')])
                    self.assertTrue(spec.read_bytes().startswith(originals[spec]))
                    self.assertTrue(archive.read_bytes().startswith(originals[archive]))

    def test_untouched_mixed_newlines_and_final_line_keep_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project.initialize(root, 'Example', 'Question', 'Result')
            (root / 'tasks').mkdir()
            (root / 'tasks/T001-example.md').write_bytes(b'# Example\n')
            prefix = b'\xef\xbb\xbf# Board\r\n\r\n| ID | Task | Status | Owner | Updated |\n| --- | --- | --- | --- | --- |\r\n'
            row = b'| T001 | Example | queued: ready | GPT | 2030-01-01T00:00:00+00:00 |\r\n'
            tail = b'\nUntouched footer with trailing spaces  '
            board = root / 'board.md'
            board.write_bytes(prefix + row + tail)
            lifecycle.transition(root, 'start', 'T001', by='GPT', status='0/2 · 估不了：fixture')
            changed = board.read_bytes()
            self.assertTrue(changed.startswith(prefix))
            self.assertTrue(changed.endswith(tail))
            self.assertEqual(changed.split(b'| T001 |')[1].split(b'\r\n', 1)[1], tail)


class WorkerEntry(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_unmanaged_claim_and_release_use_single_lifecycle_entry(self):
        with patch.object(lifecycle, '_worker_transition', wraps=lifecycle._worker_transition) as entry:
            lease = workers.claim(self.root, 'sample-task', 'W1', ['output'], now=1000)
            workers.update(self.root, 'sample-task', lease['token'], now=1100)
            workers.update(self.root, 'sample-task', lease['token'], release=True, now=1200)
        self.assertEqual([call.args[1] for call in entry.call_args_list], ['claim', 'heartbeat', 'release'])
        state = storage.read(self.root / 'attachments/state.json')['tasks']['sample-task']
        self.assertEqual(state['status'], '待验收')
        records = storage.lines(self.root / 'attachments/task-flow.jsonl')
        self.assertEqual([r['action'] for r in records], ['claim', 'release'])
        self.assertTrue(all(r['by'] == 'GPT' and r['source'] == 'workers' for r in records))

    def test_managed_worker_release_keeps_review_and_role_boundaries(self):
        project.initialize(self.root, 'Example', 'Question', 'Result')
        (self.root / 'tasks').mkdir()
        (self.root / 'tasks/T001-example.md').write_bytes(b'# Example\n')
        lifecycle.transition(self.root, 'new', 'T001', by='Claude', title='Example', when='Ready')
        lifecycle.transition(self.root, 'start', 'T001', by='GPT', status='0/2 · 估不了：fixture')
        before = (self.root / 'board.md').read_bytes()
        lease = workers.claim(self.root, 'T001', 'W1', ['output'])
        workers.update(self.root, 'T001', lease['token'], release=True)
        self.assertEqual((self.root / 'board.md').read_bytes(), before)
        task = storage.read(self.root / 'attachments/state.json')['tasks']['T001']
        self.assertEqual(task['status'], '0/2 · 估不了：fixture')
        self.assertEqual(task['worker_state'], 'handoff')
        self.assertNotIn('claim', lifecycle.ACTIONS)
        self.assertNotIn('release', lifecycle.ACTIONS)
        with self.assertRaises(ValueError):
            lifecycle.transition(self.root, 'accept', 'T001', by='GPT', summary='Ready')

    def test_failed_lifecycle_publication_preserves_unpublished_claim(self):
        with patch.object(lifecycle, '_worker_transition', side_effect=ValueError('fixture publication')):
            with self.assertRaisesRegex(ValueError, 'fixture publication'):
                workers.claim(self.root, 'sample-task', 'W1', ['output'])
        self.assertEqual(list((self.root / 'attachments/locks').glob('*.lock')), [])
        self.assertEqual(len(list((self.root / 'attachments/locks/history').glob('*.unpublished'))), 1)

    def test_bad_release_token_and_status_keep_active_lease(self):
        lease = workers.claim(self.root, 'sample-task', 'W1', ['output'], now=1000)
        before = files(self.root)
        before.pop('.write.lock', None)
        for token, status in [('foreign', 'review'), (lease['token'], 'review\nforged'),
                              (lease['token'], 'review|forged')]:
            with self.subTest(token=token, status=status), self.assertRaises(ValueError):
                workers.update(self.root, 'sample-task', token, release=True, now=1100, status=status)
            after = files(self.root)
            after.pop('.write.lock', None)
            self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main()
