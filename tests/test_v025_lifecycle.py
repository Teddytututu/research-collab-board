from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from board import storage, project, workers
from board.lifecycle import transition, check, log_patrol, fix_tree


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        project.initialize(self.root, 'Example', 'Compare methods', 'Report')
        (self.root / 'tasks').mkdir()
        (self.root / 'tasks/T001-example.md').write_text('# Example\n\nGoal and acceptance criteria.\n', encoding='utf-8')
        storage.write(self.root / 'overview.json', {'tree': [{'title': 'Study', 'status': 'todo', 'tasks': []}]})
        self.now = datetime(2030, 1, 2, 12, tzinfo=timezone.utc)
        # Lifecycle counts are independent of host disk capacity and project age.
        capacity = patch('board.stability.disk_summary', return_value=[])
        capacity.start()
        self.addCleanup(capacity.stop)
        value = storage.read(self.root / 'project.json')
        value['created_at'] = self.now.isoformat()
        storage.write(self.root / 'project.json', value)

    def move(self, action, by='GPT', **kwargs):
        return transition(self.root, action, 'T001', by=by, now=self.now, **kwargs)

    def new(self):
        self.move('new', 'Claude', title='Example', when='Inputs ready', node='Study')

    def evidence(self):
        path = self.root / 'attachments/evidence.md'
        path.write_text('Expected counts and test output.\n', encoding='utf-8')
        return 'attachments/evidence.md'

    def test_complete_lifecycle_archives_and_cannot_resurrect_snapshot(self):
        self.new()
        self.move('start', status='0/2 · 估不了：fixture setup')
        self.move('block', wait='waiting for researcher to review inputs')
        self.move('deliver', evidence=self.evidence())
        with self.assertRaisesRegex(ValueError, 'research lead'):
            self.move('accept', summary='Ready')
        self.move('accept', 'Claude', summary='Two cases ready', node_summary='Comparison ready')
        self.assertNotIn('| T001 |', (self.root / 'board.md').read_text('utf-8'))
        self.assertIn('accepted: Two cases ready', (self.root / 'tasks/archive.md').read_text('utf-8'))
        tree = storage.read(self.root / 'overview.json')['tree'][0]
        self.assertEqual((tree['status'], tree['summary']), ('done', 'Comparison ready'))
        self.assertNotIn('T001', storage.read(self.root / 'attachments/state.json')['tasks'])
        self.assertEqual(len(storage.lines(self.root / 'attachments/task-flow.jsonl')), 5)

    def test_authority_evidence_and_state_guards_preserve_board(self):
        before = (self.root / 'board.md').read_bytes()
        for action in ['new', 'accept', 'reject', 'stop']:
            with self.assertRaises(ValueError):
                self.move(action)
        self.assertEqual((self.root / 'board.md').read_bytes(), before)
        self.new()
        before = (self.root / 'board.md').read_bytes()
        for action, fields in [('accept', {'summary': 'Ready'}), ('deliver', {'evidence': '../outside.md'}),
                               ('start', {'status': '3/2'}), ('start', {'status': '0/0'})]:
            with self.assertRaises(ValueError):
                self.move(action, 'Claude', **fields)
        self.assertEqual((self.root / 'board.md').read_bytes(), before)

    def test_reject_resume_stop_and_duplicate_ids(self):
        self.new()
        self.move('start', status='0/2 · 估不了：fixture setup')
        self.move('deliver', evidence=self.evidence())
        self.move('reject', 'Claude', reason='Add second case')
        self.move('start', status='1/2 · 估不了：fixture setup')
        self.move('stop', 'Claude', reason='Scope changed')
        with self.assertRaises(ValueError):
            self.new()
        self.assertEqual(storage.read(self.root / 'overview.json')['tree'][0]['status'], 'done')

    def test_shared_node_finishes_only_after_all_tasks_are_archived(self):
        self.new()
        overview = storage.read(self.root / 'overview.json')
        overview['tree'][0]['tasks'].append('T002')
        storage.write(self.root / 'overview.json', overview)
        self.move('stop', 'Claude', reason='Merged into sibling')
        self.assertEqual(storage.read(self.root / 'overview.json')['tree'][0]['status'], 'doing')

    def test_checks_deadlines_patrol_grace_and_owner(self):
        self.new()
        self.move('start', status='0/2 · 估不了：fixture setup')
        late = self.now + timedelta(hours=4)
        issues = check(self.root, now=late)
        self.assertTrue(any(i['code'] == 'running_stale' and i['owner'] == 'GPT' for i in issues))
        record = log_patrol(self.root, 'GPT', 'Updated comparison', every=30, now=late)
        self.assertEqual(record['open_issues'], 1)
        self.assertFalse(any(i['code'] == 'patrol_overdue' and i['owner'] == 'GPT'
                             for i in check(self.root, now=late + timedelta(minutes=45))))
        self.assertTrue(any(i['code'] == 'patrol_overdue' and i['owner'] == 'GPT'
                            for i in check(self.root, now=late + timedelta(minutes=46))))

    def test_existing_bytes_preserved_and_missing_evidence_directory_rejected(self):
        before = (self.root / 'board.md').read_bytes()
        self.new()
        self.move('start', status='0/2 · 估不了：fixture setup')
        with self.assertRaises(ValueError):
            self.move('deliver', evidence='attachments')
        self.assertIn(before, [p.read_bytes() for p in (self.root / 'history').glob('*')])

    def test_unknown_node_and_missing_spec_leave_board_intact(self):
        before = (self.root / 'board.md').read_bytes()
        with self.assertRaises(ValueError):
            self.move('new', 'Claude', title='Example', when='Ready', node='Missing')
        with self.assertRaises(ValueError):
            transition(self.root, 'new', 'T002', by='Claude', title='Other', when='Ready')
        self.assertEqual((self.root / 'board.md').read_bytes(), before)

    def test_tree_repair_requires_lead_and_preserves_live_nodes(self):
        self.new()
        self.move('stop', 'Claude', reason='Merged')
        overview = storage.read(self.root / 'overview.json')
        overview['tree'][0]['status'] = 'doing'
        storage.write(self.root / 'overview.json', overview)
        with self.assertRaises(ValueError):
            fix_tree(self.root, by='GPT')
        self.assertEqual(fix_tree(self.root, by='Claude'), ['Study'])
        self.assertEqual(fix_tree(self.root, by='Claude'), [])

    def test_worker_lease_keeps_managed_status_until_evidence_delivery(self):
        self.new()
        self.move('start', status='0/2 · 估不了：fixture setup')
        lease = workers.claim(self.root, 'T001', 'W1', ['work/output'])
        workers.update(self.root, 'T001', lease['token'], release=True)
        self.assertEqual(storage.read(self.root / 'attachments/state.json')['tasks']['T001']['status'], '0/2 · 估不了：fixture setup')
        with self.assertRaisesRegex(ValueError, 'task_flow'):
            workers.update_board(self.root, 'T001', 'delivered')
        self.move('deliver', evidence=self.evidence())

    def test_archived_task_stays_closed_when_an_old_worker_releases(self):
        self.new()
        lease = workers.claim(self.root, 'T001', 'W1', ['work/output'])
        self.move('stop', 'Claude', reason='Scope merged')
        workers.update(self.root, 'T001', lease['token'], release=True)
        self.assertNotIn('T001', storage.read(self.root / 'attachments/state.json')['tasks'])
        with self.assertRaises(ValueError):
            workers.claim(self.root, 'T001', 'W2', ['work/output'])


if __name__ == '__main__':
    unittest.main()
