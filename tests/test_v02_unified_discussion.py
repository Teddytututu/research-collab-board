from pathlib import Path
import tempfile,unittest
from board import project,storage
from board.app import conversation

class UnifiedDiscussion(unittest.TestCase):
    def test_default_timeline_preserves_legacy_ledgers_and_cross_channel_reply(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);project.initialize(root,'Unified discussion fixture')
            a=project.post(root,'GPT','Research')
            b=project.post(root,'Claude','Study',channel='study')
            c=project.bookmark(root,'study',b['id'])
            original={x:project.ledger(root,x).read_bytes() for x in project.CHANNELS}
            result=conversation(root)
            self.assertTrue(result['unified']);self.assertEqual([x['id'] for x in result['items']],[a['id'],b['id'],c['id']])
            self.assertEqual(len(conversation(root,'main')['items']),1)
            for x,raw in original.items():self.assertEqual(project.ledger(root,x).read_bytes(),raw)
            reply=project.post(root,'owner','Reply to study',parent_id=b['id'])
            self.assertEqual(reply['channel'],'main');self.assertEqual(reply['parent_id'],b['id'])
            self.assertEqual(project.ledger(root,'study').read_bytes(),original['study'])

if __name__=='__main__':unittest.main()
