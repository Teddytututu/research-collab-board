"""First-run choices remain local, explicit and recoverable."""
from pathlib import Path
import importlib.util, io, json, os, subprocess, tempfile, unittest
from unittest.mock import Mock, patch
from board import onboarding, project, storage, assets
from board.app import conversation

ROOT = Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(ROOT/'work/tests')


class FirstRunDefaults(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        project.initialize(self.root, 'Fictional first run')

    def tearDown(self):
        self.tmp.cleanup()

    def test_bundled_characters_satisfy_setup_without_generation(self):
        for agent in ['GPT', 'Claude']:
            result = onboarding.status(self.root, agent)
            self.assertTrue(result['checks']['artwork'])
            self.assertEqual(result['artwork']['mode'], 'bundled')
            self.assertTrue(all(row['file'].endswith('.png') for row in result['artwork']['files']))
        self.assertFalse((self.root/'attachments/generated').exists())

    def test_unanswered_prompt_uses_unicode_without_downloader_or_stdin(self):
        installer = Mock(side_effect=AssertionError('External download'))
        with patch('builtins.input', side_effect=AssertionError('Interactive input')):
            first = onboarding.configure_emotes(self.root, installer=installer)
            again = onboarding.configure_emotes(self.root, installer=installer)
        self.assertTrue(first['show_prompt'])
        self.assertFalse(again['show_prompt'])
        self.assertTrue(again['decision_required'])
        self.assertEqual(again['mode'], 'unicode')
        installer.assert_not_called()

    def test_decline_is_reused_and_existing_chat_artwork_bytes_survive(self):
        post = project.post(self.root, 'GPT', 'Existing opening')
        art = self.root/'attachments/generated/GPT/avatar.png'
        art.parent.mkdir(parents=True)
        art.write_bytes(b'prior artwork')
        ledger = project.ledger(self.root).read_bytes()
        installer = Mock()
        onboarding.configure_emotes(self.root, 'unicode', installer=installer)
        result = onboarding.configure_emotes(self.root, installer=installer)
        self.assertEqual((result['mode'], result['decision_required']), ('unicode', False))
        installer.assert_not_called()
        self.assertEqual(project.ledger(self.root).read_bytes(), ledger)
        self.assertEqual(art.read_bytes(), b'prior artwork')
        self.assertEqual(conversation(self.root)['items'][0]['id'], post['id'])

    def test_saved_permission_is_reused_and_failure_falls_back(self):
        installer = Mock(return_value={'downloaded': 225, 'reused': 0, 'failed': 0})
        result = onboarding.configure_emotes(self.root, 'download', installer=installer)
        self.assertEqual(result['mode'], 'download')
        result = onboarding.configure_emotes(self.root, installer=installer)
        self.assertEqual(installer.call_count, 2)
        self.assertEqual(result['choice'], 'download')
        installer.side_effect = OSError('Fictional download failure')
        result = onboarding.configure_emotes(self.root, installer=installer)
        self.assertEqual((result['choice'], result['mode']), ('download', 'unicode'))
        self.assertIn('Fictional download failure', result['error'])

    def test_catalog_requires_both_permission_and_successful_local_install(self):
        row = assets.emote_manifest()[0]
        path = self.root/'emotes'/row['file']
        path.parent.mkdir()
        path.write_bytes(b'local fixture')
        self.assertEqual([x for x in conversation(self.root)['reaction_catalog'] if x['key'].startswith('bili:')], [])
        onboarding.configure_emotes(self.root, 'download', installer=lambda root: dict(downloaded=1, reused=0, failed=0))
        self.assertEqual(conversation(self.root)['reaction_catalog'][0]['key'], row['key'])
        onboarding.configure_emotes(self.root, 'download', installer=lambda root: dict(downloaded=1, reused=0, failed=1))
        self.assertEqual([x for x in conversation(self.root)['reaction_catalog'] if x['key'].startswith('bili:')], [])
        onboarding.configure_emotes(self.root, 'unicode')
        self.assertTrue(path.exists())

    def test_night_watch_registration_is_injectable_and_failure_is_actionable(self):
        spec = importlib.util.spec_from_file_location('onboarding_bootstrap', ROOT/'scripts/bootstrap.py')
        bootstrap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bootstrap)
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, '{"registered":true}', ''))
        result = bootstrap.register_night_watch('local-python', self.root, runner=runner)
        self.assertEqual(result['status'], 'registered')
        command = runner.call_args.args[0]
        self.assertEqual(command[command.index('--data-dir')+1], self.root.relative_to(ROOT).as_posix())
        self.assertIn('--install', command)
        runner.side_effect = OSError('Fictional scheduler error')
        result = bootstrap.register_night_watch('local-python', self.root, runner=runner)
        self.assertEqual(result['status'], 'manual')
        self.assertIn('install_night_watch.py', result['manual_command'])
        self.assertIn('Fictional scheduler error', result['error'])


if __name__ == '__main__':
    unittest.main()
