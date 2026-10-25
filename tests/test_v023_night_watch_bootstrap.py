"""Exercise the actual bootstrap installer contract in isolated space-path copies."""
import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board import storage


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class BootstrapNightWatchIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='watch interface ', dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "study 空格 '& project"
        self.root.mkdir()
        self.data_dir = "runtime/custom 空格 '& data"
        self.data = self.root / self.data_dir
        for relative in ('scripts/bootstrap.py', 'scripts/night_watch.py', 'scripts/run_queue.py',
                         'scripts/install_night_watch.py', 'scripts/install-night-watch.ps1',
                         'board/__init__.py', 'board/environment.py', 'board/storage.py'):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        self.bootstrap = load(self.root / 'scripts/bootstrap.py', 'bootstrap_watch_interface')
        self.installer = load(self.root / 'scripts/install_night_watch.py', 'installer_watch_interface')
        self.scheduler_calls = []
        self.scheduler_returncode = 0

    def mock_install_runner(self, command, **kwargs):
        self.assertEqual(Path(command[2]), self.root / 'scripts/install_night_watch.py')
        self.assertEqual(command[command.index('--data-dir') + 1], Path(self.data_dir).as_posix())
        output = io.StringIO()
        def scheduler(args, **options):
            self.scheduler_calls.append(args)
            return subprocess.CompletedProcess(args, self.scheduler_returncode,
                                               'Mock registered' if self.scheduler_returncode == 0 else '',
                                               'Mock access denied' if self.scheduler_returncode else '')
        with patch.object(self.installer.platform, 'system', return_value='Windows'), \
             patch.object(self.installer.subprocess, 'run', side_effect=scheduler), contextlib.redirect_stdout(output):
            code = self.installer.main(command[3:])
        return subprocess.CompletedProcess(command, code, output.getvalue(), '')

    def test_actual_bootstrap_dry_run_has_zero_scheduler_calls_and_zero_writes(self):
        result = self.bootstrap.register_night_watch(sys.executable, self.data, runner=self.mock_install_runner, dry_run=True)
        self.assertEqual(result['status'], 'preview')
        self.assertEqual(result['report']['status'], 'preview')
        self.assertEqual(self.scheduler_calls, [])
        self.assertFalse(self.data.exists())
        self.assertFalse((self.root / 'data').exists())

    def test_actual_bootstrap_install_xml_uses_custom_data_and_hidden_action(self):
        result = self.bootstrap.register_night_watch(sys.executable, self.data, runner=self.mock_install_runner)
        self.assertEqual(result['status'], 'registered')
        self.assertEqual(len(self.scheduler_calls), 1)
        plan = result['report']
        xml_path = Path(plan['xml_path'])
        self.assertEqual(xml_path, self.data / 'attachments/night-watch/install-task.xml')
        xml = ET.parse(xml_path)
        ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        self.assertEqual(xml.find('.//t:Interval', ns).text, 'PT10M')
        self.assertEqual(xml.find('.//t:Hidden', ns).text, 'true')
        self.assertEqual(xml.find('.//t:WorkingDirectory', ns).text, str(self.root))
        self.assertEqual(xml.find('.//t:MultipleInstancesPolicy', ns).text, 'IgnoreNew')
        invocation = base64.b64decode(plan['action'].split()[-1]).decode('utf-16le')
        self.assertIn("'--data-dir' '" + self.data_dir.replace("'", "''") + "'", invocation)
        self.assertFalse((self.root / 'data').exists())

    def test_bootstrap_real_installer_dry_run_subprocess(self):
        result = self.bootstrap.register_night_watch(sys.executable, self.data, dry_run=True)
        self.assertEqual(result['status'], 'preview', result)
        self.assertEqual(result['report']['status'], 'preview')
        self.assertIn('Hidden', result['report']['action'])
        self.assertFalse(self.data.exists())

    def test_bootstrap_receives_manual_retry_after_mock_scheduler_failure(self):
        self.scheduler_returncode = 1
        result = self.bootstrap.register_night_watch(sys.executable, self.data, runner=self.mock_install_runner)
        self.assertEqual(result['status'], 'manual')
        self.assertEqual(result['report']['status'], 'manual_registration')
        self.assertEqual(len(self.scheduler_calls), 1)
        self.assertIn('Mock access denied', result['report']['detail'])
        self.assertIn('schtasks.exe', result['manual_command'])
        self.assertIn(str(self.data).replace("'", "''"), result['manual_command'])
        self.assertTrue(Path(result['report']['xml_path']).is_file())

    def test_installer_machine_json_is_utf8_compatible_under_legacy_console(self):
        env = dict(os.environ, PYTHONIOENCODING='cp1252')
        result = subprocess.run([sys.executable, '-B', str(self.root / 'scripts/install_night_watch.py'),
                                 '--project-root', str(self.root), '--data-dir', self.data_dir, '--install', '--dry-run'],
                                capture_output=True, env=env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        value = json.loads(result.stdout.decode('utf-8'))
        self.assertEqual(value['status'], 'preview')
        self.assertFalse(self.data.exists())

    def test_powershell_wrapper_real_dry_run_with_custom_data(self):
        powershell = shutil.which('pwsh') or shutil.which('powershell.exe')
        if powershell is None:
            self.assertNotEqual(os.name, 'nt')
            return
        result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-File',
                                 str(self.root / 'scripts/install-night-watch.ps1'), '-ProjectRoot', str(self.root),
                                 '-DataDir', self.data_dir, '-Python', sys.executable, '-Install', '-DryRun'],
                                capture_output=True, text=True, encoding='utf-8', timeout=30,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['status'], 'preview')
        self.assertEqual(Path(value['xml_path']), self.data / 'attachments/night-watch/install-task.xml')
        self.assertFalse(self.data.exists())

    def test_real_hidden_action_runs_only_fixture_with_custom_data(self):
        if os.name != 'nt':
            return
        storage.write(self.data / 'attachments/state.json', {'runs': {'T001': {'done': 2, 'total': 2}}})
        plan = self.installer.build_plan(self.root, system='Windows', python=sys.executable, data_dir=self.data_dir)
        log = self.data / 'attachments/night-watch/patrol.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        action = subprocess.run(plan['action'].split(), cwd=self.root, capture_output=True,
                                timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(action.returncode, 0, action.stderr.decode(errors='replace'))
        events = storage.read(self.data / 'attachments/night-watch/events.json')
        self.assertEqual([row['type'] for row in events['events']], ['task_complete'])
        self.assertTrue(log.exists())
        self.assertFalse((self.root / 'data').exists())

    def test_real_queue_to_watch_cli_uses_custom_data_and_preserves_default_data(self):
        default_state = self.root / 'data/attachments/state.json'
        storage.write(default_state, {'keep': 'default data sentinel'})
        original = default_state.read_bytes()
        handler = self.root / 'work/handler.py'
        handler.parent.mkdir(parents=True)
        handler.write_text('def process(row):\n    return {"value": row["value"] * 2}\n', encoding='utf-8')
        output = Path(self.data_dir) / 'batch results'
        storage.write(self.root / 'work/queue.json', {'handler_file': 'work/handler.py', 'output': output.as_posix(),
                                                   'items': [{'id': 'a', 'value': 3}, {'id': 'b', 'value': 4}]})
        storage.write(self.data / 'attachments/state.json', {'runs': {'T001': {'done': 0, 'total': 2}}})
        storage.write(self.data / 'attachments/night-watch.json',
                      {'progress_files': {'T001': (output / 'progress.json').as_posix()}})
        commands = ([sys.executable, '-B', str(self.root / 'scripts/run_queue.py'), 'work/queue.json', '--project-root', str(self.root)],
                    [sys.executable, '-B', str(self.root / 'scripts/night_watch.py'), '--project-root', str(self.root), '--data-dir', self.data_dir])
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=30,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(result.returncode, 0, result.stderr)
        state = storage.read(self.data / 'attachments/state.json')
        self.assertEqual((state['runs']['T001']['done'], state['runs']['T001']['total']), (2, 2))
        events = storage.read(self.data / 'attachments/night-watch/events.json')['events']
        self.assertEqual([row['type'] for row in events], ['task_complete'])
        ack = subprocess.run([*commands[1], '--ack', events[0]['id']], capture_output=True,
                             text=True, encoding='utf-8', timeout=30)
        self.assertEqual(ack.returncode, 0, ack.stderr)
        quiet = subprocess.run(commands[1], capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual((quiet.returncode, quiet.stdout), (0, ''))
        self.assertEqual(default_state.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
