"""Synthetic projects exercise role-bound moods, catalog assets and HTTP ownership."""
from pathlib import Path
from datetime import datetime
import http.client
import json
import subprocess
import sys
import tempfile
import threading
import unittest

from board import app, assets, project, stability, storage

ROOT = Path(__file__).resolve().parents[1]


class Expressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        project.initialize(self.data, 'Expression example', 'Compare', 'Table')

    def test_catalog_contains_all_sixty_new_images_and_original_expressions(self):
        from board import expressions
        rows = expressions.catalog()
        new = [r for r in rows if r.get('collection') == 'original-60']
        self.assertEqual(len(new), 60)
        for role in ('owner', 'claude', 'gpt'):
            self.assertEqual(len([r for r in new if r['role']==role]), 20)
            self.assertGreater(len([r for r in rows if r['role']==role]), 20)
        self.assertEqual(len({r['key'] for r in rows}), len(rows))
        for row in rows:
            path = ROOT / 'board/expressions' / row['file']
            self.assertTrue(path.is_file(), row)
            self.assertLessEqual(path.stat().st_size, 200000)
            self.assertNotIn('source', row)
            self.assertIn('avatar_crop',row)
            if row['collection']=='original-60':
                self.assertEqual((row['width'],row['height']),(1254,1254))
                self.assertEqual(row['license'],'MIT')

    def test_both_assistants_can_register_new_mood_with_role_isolation(self):
        for who in ('Claude','GPT'):
            done = subprocess.run([sys.executable, str(ROOT/'scripts/agent.py'), '--as',who,
                                   '--data-dir',str(self.data),'mood','expression:insight','Comparing'],
                                  capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(done.returncode, 0, done.stderr+done.stdout)
            self.assertTrue(json.loads(done.stdout)['ok'])
        overview = storage.read(self.data/'overview.json')
        self.assertEqual(overview['gpt_mood']['mood'],'expression:insight')
        before = (self.data/'overview.json').read_bytes()
        with self.assertRaises(ValueError):
            stability.set_mood(self.data,'GPT','expr:claude-insight')
        self.assertEqual((self.data/'overview.json').read_bytes(),before)

    def test_mood_tokens_accept_labels_and_preserve_other_people(self):
        from board import expressions
        storage.update_json(self.data,'overview.json',lambda o:o.update(owner_mood={'mood':'keep'},claude_mood={'mood':'calm'}))
        stability.set_mood(self.data,'GPT','表情:洞见')
        o=storage.read(self.data/'overview.json')
        self.assertEqual(o['owner_mood'],{'mood':'keep'})
        self.assertEqual(o['claude_mood'],{'mood':'calm'})
        self.assertEqual(expressions.resolve('GPT',o['gpt_mood']['mood'])['role'],'gpt')

    def test_legacy_names_keep_priority_and_new_prefix_selects_new_artwork(self):
        from board import expressions
        for token in ['shy','害羞','proud','得意']:
            self.assertEqual(expressions.resolve('Claude',token)['collection'],'legacy')
            self.assertEqual(expressions.resolve('Claude','expression:'+token)['collection'],'original-60')

    def test_character_reactions_are_available_without_an_optional_download(self):
        from board import expressions
        mid=project.post(self.data,'GPT','A fixture message')['id']
        data=app.conversation(self.data)
        self.assertIn('expr:gpt-insight',data['reaction_emoji'])
        self.assertTrue(any(r['key']=='expr:gpt-insight' for r in data['reaction_catalog']))
        storage.append(self.data/'attachments/discussion/reactions.jsonl',
                       dict(message_id=mid,actor='GPT',emoji='expr:gpt-insight',active=True))
        self.assertEqual(app.conversation(self.data)['items'][0]['reactions'][0]['emoji'],'expr:gpt-insight')

    def test_http_owner_mood_is_self_only_and_persistent(self):
        server=app.create_server(self.data,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(thread.join,3);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def request(method,path,payload=None):
            port=server.server_address[1]; conn=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
            try:
                body=json.dumps(payload) if payload is not None else None
                conn.request(method,path,body,{'Content-Type':'application/json','Origin':f'http://127.0.0.1:{port}'})
                response=conn.getresponse();raw=response.read();return response.status,json.loads(raw)
            finally:conn.close()
        code,data=request('GET','/api/expressions')
        self.assertEqual(code,200);self.assertTrue(data['items'])
        before=(self.data/'overview.json').read_bytes()
        self.assertEqual(request('POST','/api/mood',{'role':'GPT','mood':'expression:insight'})[0],400)
        self.assertEqual((self.data/'overview.json').read_bytes(),before)
        code,data=request('POST','/api/mood',{'mood':'expr:owner-insight'})
        self.assertEqual(code,200,data)
        self.assertEqual(storage.read(self.data/'overview.json')['owner_mood']['mood'],'expr:owner-insight')
        self.assertEqual(request('GET','/api/expressions')[1]['moods']['owner']['mood'],'expr:owner-insight')


if __name__=='__main__':unittest.main()
