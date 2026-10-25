"""Every shipped page dependency must exist in both HTTP routes and the source ZIP."""
from html.parser import HTMLParser
from pathlib import Path
import ast,http.client,runpy,tempfile,threading,unittest
from board.project import initialize
from board.app import create_server
ROOT=Path(__file__).resolve().parents[1]
TEST_ROOT=ROOT/'work/tests';TEST_ROOT.mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(TEST_ROOT)

class Dependencies(HTMLParser):
    def __init__(self):super().__init__();self.urls=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        url=attrs.get('src') if tag=='script' else attrs.get('href') if tag=='link' and attrs.get('rel')=='stylesheet' else None
        if url and url.startswith('/'):self.urls.add(url)

class BundleAssets(unittest.TestCase):
    def test_all_page_scripts_and_styles_are_served_and_allowlisted(self):
        parser=Dependencies();parser.feed((ROOT/'board/index.html').read_text(encoding='utf-8'))
        release=runpy.run_path(str(ROOT/'scripts/release.py'));names=set(release['files']())
        self.assertTrue(parser.urls)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);initialize(root,'Fictional asset check')
            server=create_server(root,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                for url in sorted(parser.urls):
                    with self.subTest(url=url):
                        self.assertIn('board/'+url.lstrip('/'),names)
                        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                        connection.request('GET',url);response=connection.getresponse();body=response.read();connection.close()
                        self.assertEqual(response.status,200);self.assertTrue(body)
            finally:server.shutdown();server.server_close();thread.join()
    def test_allowlist_has_readable_python_and_excludes_runtime_roots(self):
        release=runpy.run_path(str(ROOT/'scripts/release.py'));names=release['files']()
        self.assertEqual(len(names),len(set(names)))
        for name in names:
            self.assertTrue((ROOT/name).is_file(),name)
            self.assertNotIn(Path(name).parts[0],{'data','.venv','work','.git'})
            if name.endswith('.py'):ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name)

if __name__=='__main__':unittest.main()
