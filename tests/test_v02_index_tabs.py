"""Keep report navigation assets present in installable source packages."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReportNavigationPackageTests(unittest.TestCase):
    def test_linked_navigation_assets_ship_in_source_package(self):
        spec = importlib.util.spec_from_file_location('report_navigation_release', ROOT / 'scripts/release.py')
        release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release)
        members = release.files()
        for name in ('index-tabs.css', 'index-tabs.js'):
            with self.subTest(asset=name):
                self.assertIn('board/' + name, members)
                self.assertTrue((ROOT / 'board' / name).is_file())
                self.assertIn('/' + name, (ROOT / 'board/index.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
