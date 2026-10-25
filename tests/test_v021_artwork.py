"""Generated PNG and SVG sets are selected by the same avatar/mood paths."""
from pathlib import Path
import http.client,json,tempfile,threading,unittest,os,time
from board.project import initialize
from board.app import create_server
TEST_ROOT=Path(__file__).resolve().parents[1]/'work/tests'
TEST_ROOT.mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(TEST_ROOT)

SVG=b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><circle cx="20" cy="20" r="16" fill="#3188ba"/></svg>'

class GeneratedArtwork(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        initialize(self.root,'Original artwork example')
        self.server=create_server(self.root,port=0);self.port=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5);c.request('GET',path)
        r=c.getresponse();result=(r.status,r.read(),dict(r.getheaders()));c.close();return result
    def asset(self,who,name,data):
        path=self.root/'attachments/generated'/who/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path
    def test_svg_avatar_is_advertised_and_served(self):
        self.asset('Claude','avatar.svg',SVG)
        status,body,_=self.request('/api/accounts');self.assertEqual(status,200)
        avatar=next(x for x in json.loads(body)['accounts'] if x['id']=='Claude')['avatar']['file']
        self.assertEqual(avatar,'generated/Claude/avatar.svg')
        status,body,headers=self.request('/'+avatar)
        self.assertEqual((status,body),(200,SVG));self.assertEqual(headers['Content-Type'],'image/svg+xml')
        self.assertIn('sandbox',headers['Content-Security-Policy'])
    def test_newer_format_wins_while_both_files_remain(self):
        png=self.asset('GPT','avatar.png',b'example-png');svg=self.asset('GPT','avatar.svg',SVG)
        os.utime(png,ns=(1000000000,1000000000));os.utime(svg,ns=(2000000000,2000000000))
        _,body,_=self.request('/api/accounts')
        self.assertEqual(next(x for x in json.loads(body)['accounts'] if x['id']=='GPT')['avatar']['file'],'generated/GPT/avatar.svg')
        os.utime(png,ns=(3000000000,3000000000));_,body,_=self.request('/api/accounts')
        self.assertEqual(next(x for x in json.loads(body)['accounts'] if x['id']=='GPT')['avatar']['file'],'generated/GPT/avatar.png')
        self.assertTrue(png.exists() and svg.exists())
    def test_all_six_svg_expressions_and_mood_alias_use_generated_files(self):
        for mood in ['calm','surprised','wink','smile','shy','teary']:
            self.asset('Claude',mood+'.svg',SVG)
            for suffix in ['', '.png', '.svg']:
                status,body,headers=self.request('/generated/Claude/'+mood+suffix)
                self.assertEqual((status,body),(200,SVG))
                self.assertEqual(headers['Content-Type'],'image/svg+xml')
        self.assertEqual(self.request('/generated/Claude/thinking')[1],SVG)
        self.assertEqual(self.request('/generated/Claude/happy.png')[1],SVG)
    def test_original_placeholder_remains_when_generated_set_is_absent(self):
        status,body,headers=self.request('/generated/GPT/calm')
        self.assertEqual(status,200);self.assertIn(b'<svg',body)
        self.assertEqual(headers['Content-Type'],'image/svg+xml')
        self.assertEqual(self.request('/generated/Other/avatar.svg')[0],404)

if __name__=='__main__':unittest.main()
