"""Version 0.2 acceptance tests use disposable data and real HTTP requests."""
from pathlib import Path
import http.client,json,tempfile,threading,time,unittest,socket,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));(ROOT/'work/tests').mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(ROOT/'work/tests')
from board.scheduler import compute_schedule
from board.project import initialize
from board.app import create_server

def agents(r=.7,t=24):return {a:dict(remaining=r,reset_hours=t) for a in ['Claude','GPT']}

class Quota(unittest.TestCase):
    def test_both_plentiful(self):
        s=compute_schedule(agents(),{},now=1000)
        self.assertAlmostEqual(s['agents']['Claude']['interval_minutes'],102.8571,places=3)
        self.assertAlmostEqual(s['shares']['Claude'],.5)
    def test_one_tight(self):
        a=agents();a['Claude']['remaining']=.15;s=compute_schedule(a,{'Claude':{'active':1}},now=1000)
        self.assertEqual(s['agents']['Claude']['interval_minutes'],240)
        self.assertGreater(s['shares']['GPT'],s['shares']['Claude'])
    def test_one_exhausted(self):
        a=agents();a['Claude']['remaining']=.03;s=compute_schedule(a,{},now=1000)
        self.assertTrue(s['agents']['Claude']['paused']);self.assertIsNone(s['agents']['Claude']['next_wake'])
        self.assertEqual(s['handoff_to'],'GPT')
    def test_reset_does_not_create_negative_cost(self):
        a=agents();a['Claude'].update(remaining=.99,reset_hours=5,before=.03,after=.99)
        s=compute_schedule(a,{},now=1000);self.assertEqual(s['agents']['Claude']['cost'],.01)
    def test_user_mention_wakes_even_low_quota(self):
        a=agents(.03);s=compute_schedule(a,{'Claude':{'mentioned':True}},now=1000)
        self.assertEqual(s['agents']['Claude']['interval_minutes'],20)
    def test_long_idle_is_capped(self):
        s=compute_schedule(agents(.15),{},now=1000);self.assertEqual(s['agents']['GPT']['interval_minutes'],240)
    def test_urgent_deadline_uses_minimum(self):
        s=compute_schedule(agents(),{'Claude':{'deadline_unix':1500}},now=1000)
        self.assertEqual(s['agents']['Claude']['interval_minutes'],20)
    def test_pending_review_wakes_exhausted_agent(self):
        s=compute_schedule(agents(.03),{'Claude':{'review':1}},now=1000);self.assertFalse(s['agents']['Claude']['paused'])
    def test_same_input_does_not_push_wake_into_future(self):
        a=agents();s=compute_schedule(a,{},now=1000);n=compute_schedule(a,{},s,now=1100)
        self.assertEqual(s['agents']['GPT']['next_wake'],n['agents']['GPT']['next_wake'])
    def test_resume_after_sleep_gets_a_future_wake(self):
        a=agents();s=compute_schedule(a,{},now=1000);n=compute_schedule(a,{},s,now=20000)
        self.assertGreater(n['agents']['GPT']['next_wake'],20000)
    def test_share_uses_all_owned_unfinished_work(self):
        s=compute_schedule(agents(),{'Claude':{'active':1,'unfinished':4},'GPT':{'active':1,'unfinished':0}},now=1000)
        self.assertAlmostEqual(s['shares']['Claude'],.2)
        self.assertEqual(s['handoff_to'],'GPT')
    def test_nan_is_rejected(self):
        a=agents(float('nan'))
        with self.assertRaises(ValueError):compute_schedule(a,{},now=1000)
    def test_ratio_bounds_and_cost_ema(self):
        a=agents();a['Claude'].update(remaining=.001,before=.72,after=.70)
        s=compute_schedule(a,{},now=1000);self.assertAlmostEqual(s['agents']['Claude']['cost'],.013)
        self.assertGreaterEqual(s['shares']['Claude'],.2);self.assertLessEqual(s['shares']['GPT'],.8)

class Initialization(unittest.TestCase):
    def test_single_user_project_and_idempotent_start(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);initialize(p,'Example study',question='Which method helps?',deliverable='A comparison')
            raw=(p/'attachments/discussion/web-main.jsonl').read_bytes();initialize(p,'Example study')
            self.assertEqual(raw,(p/'attachments/discussion/web-main.jsonl').read_bytes())
            self.assertEqual(json.loads((p/'project.json').read_text())['user_name'],'大肥鱼')
            self.assertFalse((p/'accounts.json').exists());self.assertFalse((p/'access.json').exists())
class HTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);initialize(cls.root,'Example study')
        cls.server=create_server(cls.root,port=0);cls.port=cls.server.server_port
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def request(self,path,body=None,headers=None):
        h={'Host':f'127.0.0.1:{self.port}','Origin':f'http://127.0.0.1:{self.port}'};h.update(headers or {})
        if body is not None:h['Content-Type']='application/json'
        c=http.client.HTTPConnection('127.0.0.1',self.port);c.request('GET' if body is None else 'POST',path,json.dumps(body) if body is not None else None,h)
        r=c.getresponse();result=(r.status,r.read(),dict(r.getheaders()));c.close();return result
    def test_local_works_without_password(self):self.assertEqual(self.request('/')[0],200)
    def test_identity_is_fixed(self):
        s,b,_=self.request('/api/me');self.assertEqual(json.loads(b)['id'],'owner')
        s,b,_=self.request('/api/me',headers={'X-Board-Identity':'GPT'});self.assertEqual(json.loads(b)['id'],'owner')
    def test_cannot_forge_assistant_from_browser(self):
        self.assertEqual(self.request('/api/discussion',dict(author='GPT',body='forged',client_id='a'*32))[0],403)
    def test_discussion_reply_and_reaction(self):
        s,b,_=self.request('/api/discussion',dict(body='**Example**',client_id='a'*32));self.assertEqual(s,201);mid=json.loads(b)['post']['id']
        self.assertEqual(self.request('/api/discussion',dict(body='Reply',parent_id=mid,client_id='b'*32))[0],201)
        self.assertEqual(self.request('/api/reaction',dict(message_id=mid,emoji='👍',active=True))[0],200)
    def test_csrf_and_dns_rebinding(self):
        self.assertEqual(self.request('/api/quota',{},headers={'Origin':'http://other.invalid'})[0],403)
        self.assertEqual(self.request('/',headers={'Host':'other.invalid'})[0],403)
    def test_loopback_mode_rejects_forwarded_client(self):
        self.assertEqual(self.request('/',headers={'X-Forwarded-For':'192.0.2.8'})[0],403)
    def test_runtime_and_source_files_are_private(self):
        for path in ['/data/project.json','/project.json','/../project.json','/board/app.py','/login','/parents.html']:
            self.assertIn(self.request(path)[0],{403,404})
    def test_quota_panel_reports_both_agents(self):
        s,b,_=self.request('/api/schedule');self.assertEqual(s,200);self.assertEqual(set(json.loads(b)['agents']),{'Claude','GPT'})

if __name__=='__main__':unittest.main()
