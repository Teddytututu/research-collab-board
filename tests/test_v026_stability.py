"""Fixture-only checks for assistant replies, exchange, capacity and daily state."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import os
import subprocess
import sys
import tempfile
import unittest

from board import lifecycle, project, storage

ROOT = Path(__file__).resolve().parents[1]
AT = datetime(2030, 1, 2, 12, tzinfo=timezone.utc)


class StabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        project.initialize(self.root, 'Example', 'Compare methods', 'Report')

    def room(self, author='owner', body='Please review', hours=3, parent=None, **extra):
        row = dict(id='message-' + str(len(project.raw_posts(self.root))), author=author,
                   body=body, created_at=(AT - timedelta(hours=hours)).isoformat(),
                   parent_id=parent, channel='main', **extra)
        storage.append(project.ledger(self.root), row)
        return row['id']

    def issues(self, code, **kwargs):
        return [i for i in lifecycle.check(self.root, now=AT, **kwargs) if i['code'] == code]

    def config(self, **settings):
        value = storage.read(self.root / 'project.json')
        value['stability'] = settings
        storage.write(self.root / 'project.json', value)

    def agent(self, *args):
        done = subprocess.run([sys.executable, str(ROOT / 'scripts/agent.py'),
                               '--data-dir', str(self.root), *args], cwd=ROOT,
                              capture_output=True, text=True, encoding='utf-8')
        self.assertTrue(done.stdout.strip(), done.stderr)
        return done.returncode, json.loads(done.stdout)

    def test_owner_reply_deadlines_and_exact_boundary(self):
        self.room(hours=.75)
        self.assertEqual(self.issues('owner_reply_overdue'), [])
        self.room(hours=.76)
        self.assertEqual([i['owner'] for i in self.issues('owner_reply_overdue')], ['GPT'])
        self.room(hours=2.51)
        self.assertEqual([i['owner'] for i in self.issues('owner_reply_overdue')], ['GPT', 'Claude', 'GPT'])

    def test_mentions_only_assign_the_leading_named_role(self):
        self.room(body='  @GPT 请看')
        self.room(body='@Claude: please review')
        self.room(body='This mentions @GPT in passing')
        self.room(body='@GPTish is a different name')
        self.assertEqual([i['owner'] for i in self.issues('owner_reply_overdue')],
                         ['GPT', 'Claude', 'Claude', 'GPT', 'Claude', 'GPT'])

    def test_reply_is_specific_and_withdrawn_reply_reopens_the_issue(self):
        mid = self.room(body='@GPT review')
        self.room(author='GPT', hours=1)
        self.assertEqual(len(self.issues('owner_reply_overdue')), 1)
        reply = self.room(author='GPT', hours=.5, parent=mid)
        self.assertEqual(self.issues('owner_reply_overdue'), [])
        project.delete_message(self.root, reply, 'GPT', assistant=True)
        self.assertEqual(len(self.issues('owner_reply_overdue')), 1)
        project.delete_message(self.root, mid, 'owner')
        self.assertEqual(self.issues('owner_reply_overdue'), [])

    def test_reaction_removal_reopens_only_that_assistants_issue(self):
        mid = self.room()
        reactions = self.root / 'attachments/discussion/reactions.jsonl'
        storage.append(reactions, dict(actor='GPT', message_id=mid, emoji='💡', active=True))
        self.assertEqual([i['owner'] for i in self.issues('owner_reply_overdue')], ['Claude'])
        storage.append(reactions, dict(actor='GPT', message_id=mid, emoji='💡', active=False))
        self.assertEqual(len(self.issues('owner_reply_overdue')), 2)

    def test_future_messages_and_library_copies_are_skipped(self):
        self.room(hours=-1)
        row = dict(id='copy', author='owner', body='Saved', channel='library',
                   created_at=(AT - timedelta(hours=4)).isoformat(), parent_id=None)
        storage.append(project.ledger(self.root, 'library'), row)
        self.assertEqual(self.issues('owner_reply_overdue'), [])

    def test_private_chat_uses_the_role_deadline_and_later_reply(self):
        for who in lifecycle.ROLES:
            storage.append(self.root / ('attachments/private/owner-' + who + '.jsonl'),
                           dict(id='p', author='owner', body='Review', created_at=(AT-timedelta(hours=1)).isoformat()))
        self.assertEqual([i['owner'] for i in self.issues('private_reply_overdue')], ['GPT'])
        storage.append(self.root / 'attachments/private/owner-GPT.jsonl',
                       dict(id='a', author='GPT', body='Reviewed', created_at=AT.isoformat()))
        self.assertEqual(self.issues('private_reply_overdue'), [])

    def test_custom_deadlines_apply_to_room_and_private(self):
        self.config(lead_reply_hours=4, executor_reply_minutes=240)
        self.room()
        storage.append(self.root / 'attachments/private/owner-GPT.jsonl',
                       dict(id='private', author='owner', body='Review', created_at=(AT-timedelta(hours=3)).isoformat()))
        self.assertEqual(self.issues('owner_reply_overdue'), [])
        self.assertEqual(self.issues('private_reply_overdue'), [])
        self.config(lead_reply_hours=1, executor_reply_minutes=30)
        self.assertEqual(len(self.issues('owner_reply_overdue')), 2)
        self.assertEqual([i['owner'] for i in self.issues('private_reply_overdue')], ['GPT'])

    def test_role_scoped_check_reads_only_its_private_conversation(self):
        # A broken peer ledger proves that the scoped check leaves it unopened.
        path = self.root / 'attachments/private/owner-Claude.jsonl'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'broken peer record\n')
        lifecycle.check(self.root, now=AT, owner='GPT')

    def test_bad_config_is_actionable(self):
        self.config(disk_min_free_gib=-1)
        self.assertTrue(self.issues('stability_config'))

    def test_ask_requires_two_nonempty_options_without_partial_writes(self):
        for opts in [[], ['--option', 'A'], ['--option', 'A', '--option', ' ']]:
            code, out = self.agent('--as', 'GPT', 'ask', 'Budget', 'Choose a method', *opts)
            self.assertEqual((code, out['ok']), (1, False))
        self.assertEqual(list((self.root / 'exchange').glob('*.md')), [])

    def test_ask_and_note_write_daily_headers_and_are_checkable(self):
        code, out = self.agent('--as', 'GPT', 'ask', 'Budget', 'Choose a method',
                               '--option', 'Reuse samples', '--option', 'Generate samples', '--lean', 'Reuse samples')
        self.assertEqual(code, 0, out)
        path = self.root / out['result']['file']
        text = path.read_text('utf-8')
        self.assertIn('GPT → Claude · 问：Budget', text)
        self.assertIn('A. Reuse samples', text)
        self.assertIn('B. Generate samples', text)
        self.assertIn('Reuse samples', text)
        future = datetime.now().astimezone() + timedelta(hours=3)
        self.assertTrue([i for i in lifecycle.check(self.root, now=future) if i['code']=='exchange_reply_overdue'])
        code, out = self.agent('note', 'Budget', 'Reuse samples approved', '--as', 'Claude')
        self.assertEqual(code, 0, out)
        self.assertEqual([i for i in lifecycle.check(self.root, now=future) if i['code']=='exchange_reply_overdue'], [])

    def test_exchange_deadline_is_configurable_and_legacy_headers_work(self):
        path = self.root / 'exchange/2030-01-02.md'
        path.parent.mkdir()
        path.write_text('### 2030-01-02T09:00:00+00:00 · GPT → Claude · T001\nPlease decide: A or B\n', encoding='utf-8')
        self.assertEqual(len(self.issues('exchange_reply_overdue')), 1)
        self.config(collaboration_reply_hours=4)
        self.assertEqual(self.issues('exchange_reply_overdue'), [])

    def test_exchange_append_preserves_bom_crlf_and_live_alias(self):
        from board import exchange
        day = AT.astimezone().strftime('%Y-%m-%d')
        path = self.root / ('exchange/' + day + '.md')
        path.parent.mkdir()
        before = b'\xef\xbb\xbf# exchange\r\n'
        path.write_bytes(before)
        (self.root / 'exchange.md').unlink()
        os.link(path, self.root / 'exchange.md')
        exchange.write(self.root, 'GPT', 'Budget', 'Choose a method', ask=True, options=['Reuse', 'Generate'], now=AT)
        raw = path.read_bytes()
        self.assertTrue(raw.startswith(before))
        self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))
        self.assertTrue(os.path.samefile(path, self.root / 'exchange.md'))
        self.assertEqual(len(exchange.open_questions(self.root)), 1)

    def test_exchange_fences_and_unrelated_task_notes_preserve_pending_question(self):
        from board import exchange, watch_rules
        text = ('### 2030-01-02T09:00:00+00:00 · GPT → Claude · T001\nPlease decide: A or B\n'
                '```\n### 2030-01-02T10:00:00+00:00 · Claude → GPT · T001\nQuoted example\n```\n'
                '### 2030-01-02T11:00:00+00:00 · Claude → GPT · T002\nOther task\n')
        (self.root / 'exchange.md').write_text(text, encoding='utf-8')
        self.assertEqual(list(exchange.open_questions(self.root)), ['T001'])
        self.assertEqual(list(watch_rules.open_questions(self.root)), ['T001'])

    def test_each_new_question_requires_its_own_titled_answer(self):
        from board import exchange
        exchange.write(self.root, 'GPT', 'Budget', 'Choose', ask=True, options=['Reuse', 'Generate'], now=AT-timedelta(hours=4))
        exchange.write(self.root, 'GPT', 'Format', 'Choose', ask=True, options=['Table', 'Chart'], now=AT-timedelta(hours=3))
        exchange.write(self.root, 'Claude', 'Other update', 'Ready', now=AT-timedelta(hours=2))
        self.assertEqual(len(self.issues('exchange_reply_overdue')), 2)
        exchange.write(self.root, 'Claude', 'Budget', 'Reuse', now=AT-timedelta(hours=1))
        self.assertEqual([row['title'] for row in exchange.open_questions(self.root).values()], ['问：Format'])

    def test_task_number_title_is_distinct_from_a_legacy_task_header(self):
        from board import exchange
        exchange.write(self.root, 'GPT', 'T001', 'Choose', ask=True, options=['Reuse', 'Generate'], now=AT-timedelta(hours=4))
        exchange.write(self.root, 'Claude', 'T001', 'Reuse', now=AT-timedelta(hours=1))
        self.assertEqual(exchange.open_questions(self.root), {})

    def test_disk_capacity_is_reported_and_low_space_belongs_to_executor(self):
        from board import stability
        snapshot = [{'path': 'X:/', 'free_gib': 19.9, 'total_gib': 100}]
        with patch.object(stability, 'disk_summary', return_value=snapshot):
            self.assertEqual([i['owner'] for i in self.issues('disk_low')], ['GPT'])
            self.config(disk_min_free_gib=19)
            self.assertEqual(self.issues('disk_low'), [])
        self.config(disk_min_free_gib=20)
        with patch.object(stability, 'disk_summary', return_value=[dict(path='X:/', free_gib=20, total_gib=100)]):
            self.assertEqual(self.issues('disk_low'), [])
        code, out = self.agent('--as', 'Claude', 'status')
        self.assertEqual(code, 0, out)
        self.assertIsInstance(out['result']['local_disk'], list)
        self.assertTrue(out['result']['local_disk'])

    def test_disk_enumeration_tolerates_unavailable_volumes(self):
        from board import stability
        with patch.object(stability, 'disk_roots', return_value=['A:/', 'B:/']), \
                patch.object(stability.shutil, 'disk_usage', side_effect=[OSError('offline'), SimpleNamespace(free=2**35, total=2**38)]):
            self.assertEqual(stability.disk_summary(), [{'path':'B:/', 'free_gib':32.0, 'total_gib':256.0}])

    def test_first_executor_status_greets_once_per_local_day(self):
        from board import stability
        first = stability.daily_greeting(self.root, 'GPT', now=AT)
        second = stability.daily_greeting(self.root, 'GPT', now=AT+timedelta(hours=1))
        self.assertEqual(first['id'], second['id'])
        self.assertIsNone(stability.daily_greeting(self.root, 'Claude', now=AT))
        third = stability.daily_greeting(self.root, 'GPT', now=AT+timedelta(days=1))
        self.assertNotEqual(first['id'], third['id'])
        self.assertEqual(len(project.raw_posts(self.root)), 2)
        self.assertEqual([i['owner'] for i in self.issues('greeting_reply_overdue')], [])

    def test_status_triggers_greeting_and_lead_can_acknowledge(self):
        for _ in range(2):
            code, out = self.agent('--as', 'GPT', 'status')
            self.assertEqual(code, 0, out)
        posts = project.raw_posts(self.root)
        self.assertEqual(len(posts), 1)
        later = datetime.now().astimezone() + timedelta(hours=3)
        self.assertEqual(len([i for i in lifecycle.check(self.root, now=later) if i['code']=='greeting_reply_overdue']), 1)
        storage.append(self.root / 'attachments/discussion/reactions.jsonl',
                       dict(actor='Claude', message_id=posts[0]['id'], emoji='💡', active=True))
        self.assertEqual([i for i in lifecycle.check(self.root, now=later) if i['code']=='greeting_reply_overdue'], [])

    def test_parallel_status_calls_post_one_greeting(self):
        command = [sys.executable, str(ROOT / 'scripts/agent.py'), '--data-dir', str(self.root), '--as', 'GPT', 'status']
        jobs = [subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(3)]
        for job in jobs:
            stdout, stderr = job.communicate(timeout=30)
            self.assertEqual(job.returncode, 0, stderr)
            self.assertTrue(json.loads(stdout)['ok'])
        self.assertEqual(len(project.raw_posts(self.root)), 1)

    def test_first_mood_registration_is_due_after_project_age_limit(self):
        value = storage.read(self.root / 'project.json')
        value['created_at'] = (AT-timedelta(hours=12)).isoformat()
        storage.write(self.root / 'project.json', value)
        self.assertEqual(self.issues('mood_stale'), [])
        value['created_at'] = (AT-timedelta(hours=12, seconds=1)).isoformat()
        storage.write(self.root / 'project.json', value)
        self.assertEqual([i['owner'] for i in self.issues('mood_stale')], ['Claude', 'GPT'])

    def test_mood_is_role_specific_preserves_overview_and_expires(self):
        from board import stability
        before = storage.read(self.root / 'overview.json')
        stability.set_mood(self.root, 'GPT', 'calm', 'Reviewing', now=AT-timedelta(hours=13))
        stability.set_mood(self.root, 'Claude', 'thinking', 'Comparing', now=AT-timedelta(hours=12))
        value = storage.read(self.root / 'overview.json')
        self.assertEqual(value['tree'], before['tree'])
        self.assertEqual(value['gpt_mood']['mood'], 'calm')
        self.assertEqual(value['claude_mood']['mood'], 'thinking')
        self.assertEqual([i['owner'] for i in self.issues('mood_stale')], ['GPT'])
        with self.assertRaises(ValueError):
            stability.set_mood(self.root, 'GPT', 'thinking', now=AT)
        stability.set_mood(self.root, 'GPT', 'calm', now=AT)
        self.assertEqual(self.issues('mood_stale'), [])

    def test_mood_command_uses_existing_art_and_rejects_unknown_names(self):
        code, out = self.agent('--as', 'GPT', 'mood', 'calm', 'Reviewing')
        self.assertEqual(code, 0, out)
        code, out = self.agent('--as', 'GPT', 'mood', '../new')
        self.assertEqual((code, out['ok']), (1, False))

    def test_generated_mood_is_available_only_for_its_role(self):
        from board import stability
        path = self.root / 'attachments/generated/GPT/focused.svg'
        path.parent.mkdir(parents=True)
        path.write_text('<svg/>', encoding='utf-8')
        stability.set_mood(self.root, 'GPT', 'focused', now=AT)
        with self.assertRaises(ValueError):
            stability.set_mood(self.root, 'Claude', 'focused', now=AT)


if __name__ == '__main__':
    unittest.main()
