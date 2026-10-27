"""Source-only report grouping contracts; browser geometry is covered separately."""
from pathlib import Path
import subprocess,unittest

class FileGroups(unittest.TestCase):
    def test_active_category_course_filter_and_original_open_index(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node','--test','tests/file-groups.test.cjs'],cwd=root,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
