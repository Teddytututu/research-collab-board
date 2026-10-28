"""One agent entry point: identity, JSON output, lifecycle wrapping and the owner-facing board edits."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from board import storage, project
from board.lifecycle import check, declared_eta, TAIPEI
from board.writing import validate_message

ROOT = Path(__file__).resolve().parents[1]


class AgentCommand(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        project.initialize(self.root, 'Example', 'Compare methods', 'Report')
        (self.root / 'tasks').mkdir()
        (self.root / 'tasks/T001-example.md').write_text('# Example\n\nGoal and acceptance criteria.\n', encoding='utf-8')
        storage.write(self.root / 'overview.json', {'tree': [{'title': 'Study', 'status': 'todo', 'tasks': []}]})

    def agent(self, *argv):
        done = subprocess.run([sys.executable, str(ROOT / 'scripts/agent.py'), *argv, '--data-dir', str(self.root)],
                              capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
        return json.loads(done.stdout), done.returncode

    def test_commands_list_needs_no_identity(self):
        out, code = self.agent('commands')
        self.assertEqual(code, 0)
        self.assertIn('status', out['result'])
        self.assertIn('task', out['result'])

    def test_identity_is_required(self):
        out, code = self.agent('status')
        self.assertEqual((out['ok'], code), (False, 1))
        self.assertIn('--as', out['error'])

    def test_lifecycle_through_one_entry_with_flags_after_the_command(self):
        out, code = self.agent('task', 'new', 'T001', '--as', 'Claude', '--title', 'Example', '--when', 'Inputs ready', '--node', 'Study')
        self.assertTrue(out['ok'], out)
        out, code = self.agent('task', 'start', 'T001', '--as', 'GPT', '--status', '0/2 · 约 23:00')
        self.assertTrue(out['ok'], out)
        out, code = self.agent('task', 'queue', 'T001', '--as', 'GPT', '--when', 'nobody is working on it')
        self.assertTrue(out['ok'], out)
        self.assertIn('queued: nobody is working on it', (self.root / 'board.md').read_text('utf-8'))
        out, code = self.agent('task', 'accept', 'T001', '--as', 'GPT', '--summary', 'x')
        self.assertFalse(out['ok'])

    def test_status_gathers_my_view(self):
        self.agent('task', 'new', 'T001', '--as', 'Claude', '--title', 'Example', '--when', 'Inputs ready')
        out, code = self.agent('status', '--as', 'GPT')
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['result']['as'], 'GPT')
        self.assertEqual([t['task'] for t in out['result']['tasks']], ['T001'])
        self.assertIn('pending_events', out['result'])

    def test_file_cards_and_owner_todos(self):
        out, _ = self.agent('file', 'add', '--as', 'GPT', '--title', 'Report A', '--path', 'attachments/a.html', '--cat', '研究')
        self.assertTrue(out['ok'], out)
        out, _ = self.agent('file', 'add', '--as', 'GPT', '--title', 'Report B', '--path', 'b.html', '--cat', 'misc')
        self.assertFalse(out['ok'])
        out, _ = self.agent('file', 'archive', '--as', 'GPT', '--title', 'Report A')
        self.assertTrue(out['ok'], out)
        links = storage.read(self.root / 'overview.json')['links']
        self.assertEqual([(l['title'], l['archived']) for l in links], [('Report A', True)])
        out, _ = self.agent('todo', 'add', '--as', 'Claude', '--what', 'Send the draft', '--when', 'Friday')
        self.assertTrue(out['ok'], out)
        out, _ = self.agent('todo', 'done', '--as', 'Claude', '--what', 'Send the draft')
        self.assertTrue(out['ok'], out)
        overview = storage.read(self.root / 'overview.json')
        self.assertEqual(overview['todo'], [])
        self.assertEqual(overview['todo_done'][0]['what'], 'Send the draft')

    def test_unreadable_status_is_reported_to_the_executor(self):
        self.agent('task', 'new', 'T001', '--as', 'Claude', '--title', 'Example', '--when', 'Inputs ready')
        self.agent('task', 'start', 'T001', '--as', 'GPT', '--status', '0/2 · attempt0 准入 RAM82 接线 · 约 23:00')
        codes = [i['code'] for i in check(self.root, owner='GPT')]
        self.assertIn('status_unreadable', codes)


class StatusRules(unittest.TestCase):
    def test_only_a_trailing_eta_segment_counts(self):
        from datetime import datetime
        updated = datetime(2030, 1, 2, 10, tzinfo=TAIPEI)
        self.assertIsNone(declared_eta('134/200 · screening ends 约17:05; full text waits for disk', updated))
        self.assertEqual(declared_eta('4/20 · scoring · 约 14:00', updated).hour, 14)
        self.assertEqual(declared_eta('4/20 · scoring · 约 1-05 09:15', updated).month, 1)

    def test_internal_process_words_are_rejected_in_messages(self):
        self.assertTrue(validate_message('颜色实验20组已全部生成并收回；大预算早筛已收回54/60组'))
        self.assertEqual(validate_message('320 档收到 54/60 组，凌晨 1 点出全表。'), [])


if __name__ == '__main__':
    unittest.main()
