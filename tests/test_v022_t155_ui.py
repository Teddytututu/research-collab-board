"""Collection retirement keeps archives intact and attachment downloads available."""
from pathlib import Path
import shutil,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]

class CollectionRetirement(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node enables browser-helper regressions')
    def test_archive_filter_and_independent_attachment_downloads(self):
        result=subprocess.run(['node','--test','tests/room-collection.test.cjs'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_active_assets_keep_collection_entry_points_retired(self):
        for name in ['index.html','discussion.js','room-extras.js','room-collection.js']:
            value=(ROOT/'board'/name).read_text(encoding='utf-8')
            for marker in ['/api/favorite','RoomCollection.favorite','RoomCollection.init','room-collection.js"></script>']:
                self.assertNotIn(marker,value,name)
        source=(ROOT/'board/discussion.js').read_text(encoding='utf-8')
        self.assertIn('RoomExtras.discussionItems(data.items)',source)
        self.assertIn('RoomExtras.fileLink(file)',source)
        self.assertIn('html.theme-pink #nav .brand{flex-direction:row', (ROOT/'board/index.html').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
