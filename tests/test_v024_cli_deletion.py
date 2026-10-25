"""The packaged assistant helper preserves originals and projects withdrawals."""
from pathlib import Path
import json,subprocess,sys,tempfile,unittest
from board import project
ROOT=Path(__file__).resolve().parents[1]

class AssistantHelper(unittest.TestCase):
    def test_own_withdrawal_cross_channel_and_safe_recent(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            root=Path(temp);project.initialize(root,'CLI fixture')
            message=project.post(root,'GPT','WITHDRAWAL_FIXTURE_SECRET',channel='study')
            other=project.post(root,'Claude','Other assistant message')
            raw=project.ledger(root,'study').read_bytes()
            def invoke(*args):
                return subprocess.run([sys.executable,'-B',str(ROOT/'发言.py'),*args,'--root',str(root)],capture_output=True,text=True,encoding='utf-8',timeout=30)
            denied=invoke('Claude','--delete',message['id']);self.assertNotEqual(denied.returncode,0)
            own=invoke('GPT','--delete',message['id']);self.assertEqual(own.returncode,0,own.stderr)
            self.assertTrue(json.loads(own.stdout)['deleted'])
            recent=invoke('--recent');self.assertEqual(recent.returncode,0,recent.stderr)
            self.assertNotIn('WITHDRAWAL_FIXTURE_SECRET',recent.stdout)
            rows=json.loads(recent.stdout);self.assertTrue(next(r for r in rows if r['id']==message['id'])['deleted'])
            self.assertEqual(next(r for r in rows if r['id']==other['id'])['body'],'Other assistant message')
            self.assertEqual(project.ledger(root,'study').read_bytes(),raw)

if __name__=='__main__':unittest.main()
