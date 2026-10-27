"""Project-local, fixture-only night watch and queue acceptance tests."""
import contextlib
import base64
import errno
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board import storage


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class NightWatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'data/attachments/state.json'
        storage.write(self.state, {'runs': {'T001': {'done': 0, 'total': 3}}, 'keep': {'value': 7}})
        self.watch = module('night_watch')
        self.queue = module('run_queue')

    def read(self, path):
        return json.loads((self.root / path).read_text('utf-8'))

    def test_quiet_event_dedup_ack_rearm_and_completion(self):
        self.assertEqual(self.watch.patrol(self.root, now=1000), [])
        events = self.watch.patrol(self.root, now=4601)
        self.assertEqual([e['type'] for e in events], ['progress_stalled'])
        self.assertEqual(self.watch.patrol(self.root, now=5201), [])
        self.watch.acknowledge(self.root, [events[0]['id']])
        self.assertEqual(self.watch.patrol(self.root, now=5801), [])
        self.assertEqual(self.read('data/attachments/night-watch/events.json')['events'], [])
        storage.write(self.state, {'runs': {'T001': {'done': 1, 'total': 3}}})
        self.watch.patrol(self.root, now=6000)
        self.assertEqual(self.watch.patrol(self.root, now=9601)[0]['type'], 'progress_stalled')
        storage.write(self.state, {'runs': {'T001': {'done': 3, 'total': 3}}})
        self.assertEqual(self.watch.patrol(self.root, now=9700)[0]['type'], 'task_complete')
        self.assertEqual(self.watch.patrol(self.root, now=9800), [])

    def test_project_progress_updates_count_eta_preserves_other_fields(self):
        storage.write(self.root / 'work/progress.json', {'done': 1, 'total': 3, 'state': 'running', 'estimated_seconds_remaining': 120})
        storage.write(self.root / 'data/attachments/night-watch.json', {'progress_files': {'T001': 'work/progress.json'}})
        self.watch.patrol(self.root, now=1000)
        value = self.read('data/attachments/state.json')
        self.assertEqual(value['keep'], {'value': 7})
        self.assertEqual(value['runs']['T001']['done'], 1)
        self.assertEqual(value['runs']['T001']['eta']['at'], 1120)
        self.assertLessEqual(len(value['runs']['T001']['progress_text']), 14)
        from board import task_eta
        snapshot = task_eta.snapshot(value, {}, now=1000)
        self.assertEqual(task_eta.unix(snapshot['runs'][0]['eta']['at']), 1120)
        self.assertEqual(snapshot['runs'][0]['eta']['mode'], 'estimate')

    def test_escape_and_symlink_paths_preserve_neighbor(self):
        sibling = self.root / 'neighbor.json'
        sibling.write_text('{"keep":true}', encoding='utf-8')
        storage.write(self.root / 'data/attachments/night-watch.json', {'progress_files': {'T001': '../neighbor.json'}})
        with self.assertRaises(ValueError):
            self.watch.patrol(self.root, now=1000)
        self.assertEqual(sibling.read_text('utf-8'), '{"keep":true}')

    def test_missing_progress_is_actionable_and_deduplicated(self):
        storage.write(self.root / 'data/attachments/night-watch.json', {'progress_files': {'T001': 'work/missing.json'}})
        self.assertEqual(self.watch.patrol(self.root, now=1000)[0]['type'], 'observation_error')
        self.assertEqual(self.watch.patrol(self.root, now=1600), [])

    def test_queue_isolates_error_resumes_and_skips_complete_result(self):
        config = {'output': 'work/batch', 'items': [{'id': 'a'}, {'id': 'b'}, {'id': 'c'}]}
        called = []
        def first(row):
            called.append(row['id'])
            if row['id'] == 'b':
                raise ValueError('one input failed')
            return {'value': row['id']}
        self.queue.run_queue(config, first, project_root=self.root)
        self.assertEqual(self.read('work/batch/progress.json')['state'], 'awaiting_anomaly_repair')
        called.clear()
        self.queue.run_queue(config, lambda row: called.append(row['id']) or 1, project_root=self.root)
        self.assertEqual(called, ['b'])
        self.assertEqual(self.read('work/batch/progress.json')['done'], 3)
        self.assertEqual(self.read('work/batch/progress.json')['state'], 'complete')

    def test_five_consecutive_failures_pause_before_sixth(self):
        called = []
        def fail(row):
            called.append(row['id'])
            raise ValueError('bad item')
        with self.assertRaises(self.queue.QueuePaused):
            self.queue.run_queue({'output': 'work/batch', 'items': [{'id': str(i)} for i in range(7)]}, fail, project_root=self.root)
        self.assertEqual(len(called), 5)
        self.assertEqual(self.read('work/batch/progress.json')['state'], 'paused')

    def test_enospc_propagates_and_preserves_result(self):
        def fail(row):
            raise OSError(errno.ENOSPC, 'disk full')
        with self.assertRaises(OSError) as caught:
            self.queue.run_queue({'output': 'work/batch', 'items': [{'id': 'a'}]}, fail, project_root=self.root)
        self.assertEqual(caught.exception.errno, errno.ENOSPC)
        self.assertEqual(self.read('work/batch/progress.json')['state'], 'paused')
        path = self.root / 'work/preserve.json'
        path.write_text('old', encoding='utf-8')
        with patch.object(self.queue.storage, 'replace_with_retry', side_effect=OSError(errno.ENOSPC, 'disk full')):
            with self.assertRaises(OSError):
                self.queue.atomic_json(path, {'new': True})
        self.assertEqual(path.read_text('utf-8'), 'old')

    def test_complete_result_input_drift_pauses(self):
        self.queue.run_queue({'output': 'work/batch', 'items': [{'id': 'a', 'seed': 1}]}, lambda row: 1, project_root=self.root)
        with self.assertRaises(AssertionError):
            self.queue.run_queue({'output': 'work/batch', 'items': [{'id': 'a', 'seed': 2}]}, lambda row: 2, project_root=self.root)
        self.assertEqual(self.read('work/batch/progress.json')['state'], 'paused')

    def test_installer_constructs_isolated_hidden_task_and_dry_run(self):
        install = module('install_night_watch')
        plan = install.build_plan(self.root, system='Windows', python=sys.executable)
        other = install.build_plan(self.root / 'other', system='Windows', python=sys.executable)
        self.assertNotEqual(plan['task_name'], other['task_name'])
        self.assertIn('schtasks.exe', plan['command'])
        self.assertIn('PT10M', plan['task_xml'])
        self.assertIn('Hidden', plan['action'])
        invocation = base64.b64decode(plan['action'].split()[-1]).decode('utf-16le')
        self.assertIn(str(self.root), invocation)
        with patch.object(install.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install.main(['--project-root', str(self.root), '--install', '--dry-run']), 0)
        run.assert_not_called()
        self.assertIn('*/10 * * * *', install.build_plan(self.root, system='Linux', python=sys.executable)['manual_command'])

    def test_install_failure_returns_manual_command_and_success_to_bootstrap(self):
        install = module('install_night_watch')
        output = io.StringIO()
        with patch.object(install.platform, 'system', return_value='Windows'), patch.object(install.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'Access denied')), contextlib.redirect_stdout(output):
            code = install.main(['--project-root', str(self.root), '--install'])
        value = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(value['status'], 'manual_registration')
        self.assertIn('schtasks.exe', value['manual_command'])
        self.assertIn('Access denied', value['detail'])

    def test_resource_pause_exit_and_available_queue_events_clear_on_recovery(self):
        storage.write(self.state, {'runs': {'T001': {'done': 1, 'total': 3, 'state': 'paused', 'process_alive': False}},
                                   'resources': {'available_slots': 1, 'queued': 2}})
        storage.write(self.root / 'data/attachments/night-watch.json', {'disks': [{'path': '.', 'floor_bytes': 100}]})
        with patch.object(self.watch.shutil, 'disk_usage', return_value=type('Usage', (), {'free': 20})()):
            events = self.watch.patrol(self.root, now=1000)
            self.assertEqual({e['type'] for e in events}, {'task_paused', 'process_exit', 'available_slot_and_queue', 'capacity_below_floor'})
            self.assertEqual(self.watch.patrol(self.root, now=5000), [])
        storage.write(self.state, {'runs': {'T001': {'done': 1, 'total': 3, 'state': 'running', 'process_alive': True}}})
        with patch.object(self.watch.shutil, 'disk_usage', return_value=type('Usage', (), {'free': 200})()):
            self.assertEqual(self.watch.patrol(self.root, now=6000), [])
        self.assertEqual(self.read('data/attachments/night-watch/events.json')['events'], [])

    def test_partial_result_retries_and_frozen_error_stops_immediately(self):
        path = self.root / 'work/batch/results/a.json'
        storage.write(path, {'complete': False, 'id': 'a'})
        called = []
        config = {'output': 'work/batch', 'items': [{'id': 'a'}, {'id': 'b'}]}
        def process(row):
            called.append(row['id'])
            if row['id'] == 'b':
                raise RuntimeError('frozen parameters changed')
            return 42
        with self.assertRaisesRegex(RuntimeError, 'frozen'):
            self.queue.run_queue(config, process, project_root=self.root)
        self.assertEqual(called, ['a', 'b'])
        self.assertTrue(self.read('work/batch/results/a.json')['complete'])
        self.assertEqual(self.read('work/batch/progress.json')['done'], 1)

    def test_queue_escape_and_portable_ids_leave_neighbor_intact(self):
        called = []
        for config in ({'output': '../neighbor', 'items': [{'id': 'a'}]},
                       {'output': 'work/batch', 'items': [{'id': '../neighbor'}]},
                       {'output': 'work/batch', 'items': [{'id': 'CON'}]}):
            with self.assertRaises(ValueError):
                self.queue.run_queue(config, lambda row: called.append(row), project_root=self.root)
        self.assertEqual(called, [])

    def test_unchanged_patrol_keeps_cache_and_samples_eta_on_its_timer(self):
        self.watch.patrol(self.root, now=1000)
        cache = self.root / 'data/attachments/night-watch/checkpoint.json'
        previous = (cache.read_bytes(), cache.stat().st_mtime_ns, self.state.read_bytes(), self.state.stat().st_mtime_ns)
        output = io.StringIO()
        with patch.object(self.watch.time, 'time', return_value=1600), contextlib.redirect_stdout(output):
            self.watch.main(['--project-root', str(self.root)])
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(previous[:2], (cache.read_bytes(), cache.stat().st_mtime_ns))
        before = json.loads(previous[2])
        after = storage.read(self.state)
        self.assertEqual({k: v for k, v in before.items() if k != 'eta_tracking'},
                         {k: v for k, v in after.items() if k != 'eta_tracking'})
        self.assertEqual(len(after['eta_tracking']['observations']['T001']), 2)
        self.assertIn(previous[2], [p.read_bytes() for p in (self.state.parent / 'history').glob('*')])

    def test_symlinked_output_and_progress_are_rejected(self):
        target = self.root / 'real'
        target.mkdir()
        link = self.root / 'link'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            # Exercise the same containment boundary on hosts restricting symlinks.
            original = Path.is_symlink
            boundary = patch.object(Path, 'is_symlink', lambda path: path == link or original(path))
            boundary.start()
            self.addCleanup(boundary.stop)
        with self.assertRaises(ValueError):
            self.queue.run_queue({'output': 'link/batch', 'items': []}, lambda row: None, project_root=self.root)
        storage.write(self.root / 'data/attachments/night-watch.json', {'progress_files': {'T001': 'link/progress.json'}})
        with self.assertRaises(ValueError):
            self.watch.patrol(self.root)

    def test_install_xml_is_well_formed_and_preserves_quoted_unicode_paths(self):
        import xml.etree.ElementTree as ET
        install = module('install_night_watch')
        root = self.root / "project '& space"
        plan = install.build_plan(root, system='Windows', python=sys.executable)
        xml = ET.fromstring(plan['task_xml'])
        ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        self.assertEqual(xml.find('.//t:WorkingDirectory', ns).text, str(root))
        self.assertEqual(xml.find('.//t:Interval', ns).text, 'PT10M')
        self.assertEqual(xml.find('.//t:Hidden', ns).text, 'true')
        code = base64.b64decode(plan['action'].split()[-1]).decode('utf-16le')
        self.assertIn("project ''& space", code)

    def test_real_cli_queue_resume_and_quiet_watch_in_fixture(self):
        handler = self.root / 'work/handler.py'
        handler.parent.mkdir(parents=True, exist_ok=True)
        handler.write_text('def process(row):\n    return {"value": row["value"] * 2}\n', encoding='utf-8')
        storage.write(self.root / 'work/queue.json', {'handler_file': 'work/handler.py', 'output': 'work/batch',
                                                   'items': [{'id': 'a', 'value': 2}]})
        args = [sys.executable, '-B', str(ROOT / 'scripts/run_queue.py'), 'work/queue.json', '--project-root', str(self.root)]
        first = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)['done'], 1)
        result = self.root / 'work/batch/results/a.json'
        stamp = result.stat().st_mtime_ns
        handler.write_text('def process(row):\n    raise RuntimeError("handler should be skipped")\n', encoding='utf-8')
        resumed = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(result.stat().st_mtime_ns, stamp)
        watch = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/night_watch.py'), '--project-root', str(self.root)],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(watch.returncode, 0, watch.stderr)
        self.assertEqual(watch.stdout, '')

    def test_progress_file_resumes_after_pause_and_preserves_operator_eta(self):
        progress = self.root / 'work/progress.json'
        storage.write(self.root / 'data/attachments/night-watch.json', {'progress_files': {'T001': 'work/progress.json'}})
        storage.write(progress, {'done': 1, 'total': 3, 'state': 'paused', 'estimated_seconds_remaining': 120})
        self.watch.patrol(self.root, now=1000)
        self.assertFalse(self.read('data/attachments/state.json')['runs']['T001']['active'])
        storage.write(progress, {'done': 1, 'total': 3, 'state': 'running', 'estimated_seconds_remaining': 120})
        self.watch.patrol(self.root, now=2000)
        state = self.read('data/attachments/state.json')
        self.assertTrue(state['runs']['T001']['active'])
        self.assertEqual(state['runs']['T001']['eta']['at'], 2120)
        operator = {'source': 'operator', 'remaining_seconds': 900, 'basis': 'operator forecast'}
        state['eta_tracking']['manual']['T001'] = operator
        storage.write(self.state, state)
        self.watch.patrol(self.root, now=2200)
        self.assertEqual(self.read('data/attachments/state.json')['eta_tracking']['manual']['T001'], operator)


if __name__ == '__main__':
    unittest.main()
