"""Default artwork, optional emotes and release boundaries work together."""
from pathlib import Path
import http.client, io, json, runpy, tempfile, threading, unittest
from PIL import Image
from board import assets, onboarding
from board.app import create_server
from board.project import initialize, post

ROOT=Path(__file__).resolve().parents[1]


class PublicAssets(unittest.TestCase):
    def test_default_avatar_mood_emote_and_reaction_are_served(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work/tests') as folder:
            root=Path(folder)
            initialize(root,'Character board')
            message=post(root,'GPT','Ready')
            row=assets.emote_manifest()[0]
            path=root/'emotes'/row['file']
            path.parent.mkdir()
            image=io.BytesIO()
            Image.new('RGBA',(4,4),(30,80,120,255)).save(image,format='PNG')
            path.write_bytes(image.getvalue())
            onboarding.configure_emotes(root,'download',installer=lambda data:dict(downloaded=0,reused=1,failed=0))
            server=create_server(root,port=0)
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()

            def request(url,value=None):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                headers={'Content-Type':'application/json','Origin':f'http://127.0.0.1:{server.server_port}'}
                connection.request('GET' if value is None else 'POST',url,None if value is None else json.dumps(value),headers)
                response=connection.getresponse()
                result=response.status,response.read(),dict(response.getheaders())
                connection.close()
                return result

            try:
                _,raw,_=request('/api/accounts')
                self.assertEqual(next(x for x in json.loads(raw)['accounts'] if x['id']=='Claude')['avatar']['file'],'avatar-claude.png')
                for url in ['/generated/Claude/calm','/art/trio-atlas.png','/room-reactions/'+row['file']]:
                    code,raw,headers=request(url)
                    self.assertEqual((code,headers['Content-Type']),(200,'image/png'))
                    self.assertTrue(raw.startswith(b'\x89PNG'))
                code,raw,_=request('/api/reaction',dict(message_id=message['id'],emoji=row['key'],active=True))
                self.assertEqual(code,200)
                self.assertEqual(json.loads(raw)['reactions'][0]['emoji'],row['key'])
                _,raw,_=request('/api/discussion')
                self.assertEqual(json.loads(raw)['reaction_catalog'][0]['key'],row['key'])
                path.unlink()
                _,raw,_=request('/api/discussion')
                self.assertEqual(json.loads(raw)['reaction_catalog'],[])
                self.assertIn('👍',json.loads(raw)['reaction_emoji'])
            finally:
                server.shutdown()
                server.server_close()
                worker.join()

    def test_public_manifest_and_archive_keep_media_scopes(self):
        installer=runpy.run_path(str(ROOT/'scripts/install_emotes.py'))
        rows=assets.emote_manifest()
        self.assertEqual(len(rows),225)
        self.assertTrue(all(installer['public_url'](x['url']) for x in rows))
        for bad in ['http://i0.hdslb.com/bfs/emote/'+'a'*40+'.png','https://localhost/image.png','https://i0.hdslb.com/private/file.png']:
            self.assertFalse(installer['public_url'](bad))
        release=runpy.run_path(str(ROOT/'scripts/release.py'))
        names=release['files']()
        self.assertEqual(sum(x.startswith('board/art/') and x.endswith('.png') for x in names),33)
        self.assertTrue(all(not x.startswith('data/') for x in names))
        self.assertIn('assets/public-emotes.json',names)
        self.assertIn('private_media_reference',release['scan'](b'/chat-img/'+b'a'*32+b'.png','assets/public-emotes.json'))


if __name__=='__main__':
    unittest.main()
