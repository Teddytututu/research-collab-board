from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from board.writing import validate_message

ROOT = Path(__file__).resolve().parents[1]


class Writing(unittest.TestCase):
    def test_concrete_results_pass_in_both_languages(self):
        for text in ['全部六组完成，报告展示三种方法。', 'All six groups are ready. The report compares three methods.']:
            self.assertEqual(validate_message(text), [])

    def test_filler_internal_details_and_length_are_rejected(self):
        for text in ['你说得对，需要注意的是形成闭环', 'You are right, it is worth noting the end-to-end evidence chain.',
                     'T169 done in output.json', 'PID 123 exited', 'x' * 121, 'One\nTwo\nThree']:
            self.assertTrue(validate_message(text), text)

    def test_cli_validates_before_upload_and_preserves_existing_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / 'data'
            cmd = [sys.executable, '-B', str(ROOT / 'scripts/post_message.py'), 'GPT', '闭环',
                   '--root', str(data), '--file', str(Path(folder) / 'missing.pdf')]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(data.exists())
            self.assertNotIn('FileNotFoundError', result.stderr)


if __name__ == '__main__':
    unittest.main()
