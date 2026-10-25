"""Interaction contracts for the unified discussion collection menu."""
import shutil,subprocess,unittest
from pathlib import Path
@unittest.skipUnless(shutil.which('node'),'Node supplies optional JavaScript checks')
class Sidebar(unittest.TestCase):
    def test_sidebar_and_eta_interactions(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node','--test','--test-isolation=none','tests/room-collection.test.cjs','tests/eta-view.test.cjs'],cwd=root,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
