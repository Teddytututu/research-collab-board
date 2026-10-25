import tempfile, unittest, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from board import workers
from board import storage

class WorkerTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_overlap_and_worker_exclusion(self):
        workers.claim(self.root,'A','W1',['board'],4,now=0)
        for task,worker,scope in [('B','W2','board/index.html'),('B','W1','docs')]:
            with self.assertRaises(ValueError):workers.claim(self.root,task,worker,[scope],4,now=1)
        workers.claim(self.root,'B','W2',['docs'],4,now=1)
    def test_expiry_preserves_lease_and_token_prevents_old_owner(self):
        old=workers.claim(self.root,'A','W1',['board'],4,now=0)
        new=workers.claim(self.root,'A','W2',['board'],4,now=1801)
        with self.assertRaises(ValueError):workers.update(self.root,'A',old['token'],now=1802)
        workers.update(self.root,'A',new['token'],now=2000)
        workers.update(self.root,'A',new['token'],release=True,now=2001)
        self.assertEqual(len(list((self.root/'attachments/locks/history').glob('*'))),3)
    def test_atomic_race_single_claim(self):
        def attempt(i):
            try:return workers.claim(self.root,'A','W'+str(i),['board'],4)
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=4) as ex:rows=list(ex.map(attempt,range(4)))
        self.assertEqual(sum(bool(x) for x in rows),1)
    def test_quota_and_scope_boundary(self):
        for scope in ['../private','C:/private','/private','board/*.js','board/?']:
            with self.assertRaises(ValueError):workers.claim(self.root,'A','W1',[scope],4)
        with self.assertRaises(ValueError):workers.claim(self.root,'A','W1',['board'],0)
    def test_independent_processes_share_one_claim(self):
        script=Path(__file__).resolve().parents[1]/'scripts/workers.py'
        commands=[subprocess.Popen([sys.executable,'-B',str(script),'claim','A','--worker','W'+str(i),'--scope','board','--allowed-workers','4','--data-dir',str(self.root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for i in range(4)]
        codes=[]
        for p in commands:p.communicate(timeout=20);codes.append(p.returncode)
        self.assertEqual(codes.count(0),1);self.assertEqual(codes.count(2),3)
    def test_quota_supported_worker_count(self):
        self.assertEqual(workers.quota_capacity(.03,24),0)
        self.assertEqual(workers.quota_capacity(.7,24),4)
        self.assertEqual(workers.quota_capacity(.7,24,ordinary_allowed=False),0)
    def test_claim_heartbeat_release_update_assigned_state_only(self):
        path=self.root/'attachments/state.json'
        storage.write(path,{'tasks':{'other':{'status':'ready'}},'runs':{'sample':{'done':1}}})
        old=path.read_bytes();row=workers.claim(self.root,'A','W1',['board'],now=0)
        self.assertEqual(storage.read(path)['tasks']['A']['status'],'进行中（W1）')
        workers.update(self.root,'A',row['token'],now=600)
        self.assertEqual(storage.read(path)['tasks']['A']['heartbeat_unix'],600)
        workers.update(self.root,'A',row['token'],release=True,now=601)
        state=storage.read(path)
        self.assertEqual(state['tasks']['A']['status'],'待验收')
        self.assertEqual(state['tasks']['other'],{'status':'ready'})
        self.assertEqual(state['runs'],{'sample':{'done':1}})
        self.assertIn(old,[p.read_bytes() for p in (path.parent/'history').glob('*')])

class ScopeRootTests(unittest.TestCase):
    def test_root_scope_reserves_all_descendants(self):
        self.assertTrue(workers.overlaps('.', 'board/index.html'))
        self.assertTrue(workers.overlaps('board/**', 'board/index.html'))
        self.assertFalse(workers.overlaps('board', 'board-extra'))
