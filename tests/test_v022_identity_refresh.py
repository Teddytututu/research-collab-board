"""Execute account refresh lifecycle and deployed-avatar behaviour regressions."""
from pathlib import Path
import shutil,subprocess,unittest
@unittest.skipUnless(shutil.which('node'),'Node supplies JavaScript behaviour checks')
class IdentityRefresh(unittest.TestCase):
    def test_live_identity_refresh(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node','--test','--test-isolation=none','tests/identity-refresh.test.cjs'],cwd=root,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
