from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from board import storage
from scripts.night_watch import patrol


class WatchRules(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        storage.write(self.root / 'data/attachments/state.json', {
            'allocation': {'effective_cap': 3, 'actual_cards': [1], 'loading_cards': [1], 'reserved_cards': [2]}})
        (self.root / 'data/board.md').write_text('| T001 | Example | 1/3 | GPT | 2030-01-01T10:00:00+00:00 |\n', encoding='utf-8')
        self.at = datetime(2030, 1, 1, 12, tzinfo=timezone.utc).timestamp()

    def test_three_rules_deduplicate_and_recover(self):
        (self.root / 'data/exchange.md').write_text('### 2030-01-01T10:00:00+00:00 · GPT → Claude · T001\nPlease decide: A or B. Recommend A.\n', encoding='utf-8')
        first = patrol(self.root, now=self.at)
        self.assertTrue({'idle_cards_unfinished_work', 'question_unanswered_30min', 'flow_issue'} <= {e['type'] for e in first})
        self.assertEqual(patrol(self.root, now=self.at + 600), [])
        with (self.root / 'data/exchange.md').open('a', encoding='utf-8') as stream:
            stream.write('### 2030-01-01T12:11:00+00:00 · Claude → GPT · T001\nUse A.\n')
        storage.write(self.root / 'data/attachments/state.json', {'allocation': {'effective_cap': 2, 'actual_cards': [1, 2]}})
        patrol(self.root, now=self.at + 1200)
        pending = storage.read(self.root / 'data/attachments/night-watch/events.json')['events']
        self.assertFalse(any(e['type'] in {'idle_cards_unfinished_work', 'question_unanswered_30min'} for e in pending))

    def test_blocked_delivered_and_stopped_tasks_do_not_consume_free_slots(self):
        for status in ['blocked: waiting for owner approval', 'delivered · awaiting review', 'stopped: scope changed']:
            (self.root / 'data/board.md').write_text('| T001 | Example | ' + status + ' | GPT | 2030-01-01T10:00:00+00:00 |\n', encoding='utf-8')
            self.assertFalse(any(e['type'] == 'idle_cards_unfinished_work' for e in patrol(self.root, now=self.at)))

    def test_question_threshold_and_unrelated_lead_reply(self):
        (self.root / 'data/exchange.md').write_text(
            '### 2030-01-01T11:30:00+00:00 · GPT → Claude · T001\nPlease decide: A or B. Recommend A.\n'
            '### 2030-01-01T11:35:00+00:00 · Claude → GPT · T002\nOther task ready.\n', encoding='utf-8')
        self.assertFalse(any(e['type'] == 'question_unanswered_30min' for e in patrol(self.root, now=self.at - 1)))
        self.assertTrue(any(e['type'] == 'question_unanswered_30min' for e in patrol(self.root, now=self.at)))


if __name__ == '__main__':
    unittest.main()
