from pathlib import Path
import tempfile,threading,http.client,json,unittest,sys,base64
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));(ROOT/'work/tests').mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(ROOT/'work/tests')
from board import project,storage,contacts
from board.app import create_server,conversation

class Channels(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);project.initialize(self.root,'Fictional conversation study')
        project.post(self.root,'Claude','Explicit research fixture');project.post(self.root,'GPT','Explicit execution fixture')
    def tearDown(self):self.tmp.cleanup()
    def test_separate_ledgers_preserve_research_bytes(self):
        old=(self.root/'attachments/discussion/web-main.jsonl').read_bytes()
        p=project.post(self.root,'GPT','Study note',channel='学习')
        self.assertEqual(conversation(self.root,'study')['items'][0]['id'],p['id'])
        self.assertEqual(old,(self.root/'attachments/discussion/web-main.jsonl').read_bytes())
        self.assertEqual(len(conversation(self.root,'main')['items']),2)
    def test_bookmark_is_a_stable_reference(self):
        p=project.post(self.root,'Claude','A useful source',channel='学习');old=project.ledger(self.root,'study').read_bytes()
        a=project.bookmark(self.root,'study',p['id']);b=project.bookmark(self.root,'study',p['id'])
        self.assertEqual(a['id'],b['id']);self.assertEqual(a['reference'],dict(channel='study',message_id=p['id']))
        self.assertEqual(old,project.ledger(self.root,'study').read_bytes());self.assertEqual(len(conversation(self.root,'library')['items']),1)
    def test_reply_stays_inside_its_conversation(self):
        p=project.post(self.root,'GPT','Research note')
        with self.assertRaises(ValueError):project.post(self.root,'owner','Wrong conversation',parent_id=p['id'],channel='study')

class ChannelHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);project.initialize(self.root,'Fictional HTTP channels')
        project.post(self.root,'Claude','Explicit research fixture');project.post(self.root,'GPT','Explicit execution fixture')
        self.server=create_server(self.root,port=0);self.port=self.server.server_port;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def req(self,path,payload=None):
        h={'Host':f'127.0.0.1:{self.port}','Origin':f'http://127.0.0.1:{self.port}','Content-Type':'application/json'}
        c=http.client.HTTPConnection('127.0.0.1',self.port);c.request('GET' if payload is None else 'POST',path,json.dumps(payload) if payload is not None else None,h);r=c.getresponse();v=(r.status,r.read());c.close();return v
    def test_bookmark_channel_list_and_unread(self):
        p=project.post(self.root,'GPT','New study note',channel='study')
        code,body=self.req('/api/conversations');self.assertEqual(code,200);rows=json.loads(body)['channels'];self.assertEqual({x['id'] for x in rows},{'main','study','library'});self.assertEqual(next(x for x in rows if x['id']=='study')['unread'],1)
        self.assertEqual(self.req('/api/bookmark',dict(channel='study',message_id=p['id']))[0],201)
        code,body=self.req('/api/discussion?channel=library');self.assertEqual(len(json.loads(body)['items']),1)
    def test_w1_favorite_endpoint_and_collection_alias(self):
        source=project.post(self.root,'GPT','A reusable study result',channel='study')
        old=project.ledger(self.root,'study').read_bytes()
        code,body=self.req('/api/favorite',dict(channel='study',message_id=source['id']))
        self.assertEqual(code,201);saved=json.loads(body)['post']
        code,body=self.req('/api/discussion?channel=files')
        self.assertEqual(json.loads(body)['items'][0]['id'],saved['id'])
        self.assertEqual(contacts.ledger(self.root,'files'),project.ledger(self.root,'library'))
        self.assertEqual(old,project.ledger(self.root,'study').read_bytes())
    def test_file_attachment_can_be_downloaded(self):
        data='data:text/plain;base64,'+base64.b64encode(b'Example source note').decode()
        code,body=self.req('/api/discussion',dict(channel='文件收藏',body='',client_id='d'*32,files=[dict(name='example.txt',data=data)]))
        self.assertEqual(code,201);file=json.loads(body)['post']['files'][0]
        code,content=self.req(file['url']);self.assertEqual(code,200);self.assertEqual(content,b'Example source note')
        code,body=self.req('/api/discussion?channel=main');self.assertEqual(len(json.loads(body)['items']),2)

if __name__=='__main__':unittest.main()
