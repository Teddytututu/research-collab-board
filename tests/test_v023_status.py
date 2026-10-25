"""Compact status presentation and both existing paper themes."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from urllib.request import urlopen

from board import app, project

ROOT = Path(__file__).resolve().parents[1]


class CompactStatus(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node enables formatter and DOM fixtures')
    def test_formatter_and_task_details(self):
        result = subprocess.run(
            ['node', '--test', 'tests/eta-view.test.cjs'], cwd=ROOT,
            capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_theme_status_cascade_and_hover(self):
        css = (ROOT / 'board/eta-view.css').read_text(encoding='utf-8')
        def declarations(selector):
            rules = re.findall(re.escape(selector) + r'\{([^}]+)\}', css)
            self.assertTrue(rules, selector)
            return rules[-1]
        for theme, colors in {
            'default': ['#16a34a', '#2563eb', '#f59e0b'],
            'pink': ['#3aa676', '#e0558f', '#e8a33d'],
        }.items():
            for state, color in zip(['done', 'doing', 'todo'], colors):
                self.assertIn('border-left-color:' + color + '!important',
                              declarations(f'html.theme-{theme} body .nd.st-{state}'))
                self.assertIn('background:', declarations(f'html.theme-{theme} body .nd .s-{state}'))
                self.assertIn('color:', declarations(f'html.theme-{theme} body .nd.st-{state} .st'))
        self.assertIn('background:#ffe3ee!important', declarations('html.theme-pink body .nd.lv0'))
        self.assertIn('transform:translateY(-50%)!important', declarations('html body .tog,html body .tog:hover'))
        self.assertIn('transform:none!important', declarations('html body .nd:hover'))
        for status in ['run', 'review', 'queue', 'blocked']:
            self.assertIn(f'.chip.task-{status}', css)
        for rule in ['.task-summary', '.tt-bar', '.tt-text', '@media(max-width:600px)']:
            self.assertIn(rule, css)

    def test_loopback_serves_current_sources(self):
        # A disposable project exercises the actual HTTP handler without deployment.
        work = ROOT / 'work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='t162-http-', dir=work) as directory:
            project.initialize(Path(directory), 'Status fixture', 'Example question', 'Example result')
            server = app.create_server(Path(directory), port=0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                for name in ['eta-view.js', 'eta-view.css', 'index.html']:
                    with urlopen(base + '/' + name, timeout=5) as response:
                        self.assertEqual(response.status, 200)
                        body = response.read()
                        content = body.decode('utf-8')
                        if name == 'index.html':
                            self.assertIn('EtaView.task({...t,eta:t.eta||o.task_etas?.[t.id]}', content)
                            self.assertIn("if (now) add('现在', now)", content)
                            self.assertIn('task-timing', content)
                        else:
                            self.assertEqual(body, (ROOT / 'board' / name).read_bytes())
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
