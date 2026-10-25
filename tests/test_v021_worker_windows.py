"""Finite user-authorized CPU worker windows; physical-device limits stay separate."""
import tempfile,unittest
from pathlib import Path
from board import workers,storage
TEST_ROOT=Path(__file__).resolve().parents[1]/'work/tests'
TEST_ROOT.mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(TEST_ROOT)

class WorkerWindows(unittest.TestCase):
    def policy(self):
        return dict(max_workers=3,cpu_slots=8,ordinary_usage_allowed=True,
            temporary_override=dict(authorized_by='user',authorization='Explicit bounded parallel work',
                                    starts_unix=1000,expires_unix=1600,max_workers=6))
    def test_authorized_window_is_finite_and_bounded_by_cpu(self):
        p=self.policy();self.assertEqual(workers.effective_worker_limit(p,1100),6)
        p['cpu_slots']=2;self.assertEqual(workers.effective_worker_limit(p,1100),2)
    def test_future_expired_and_unapproved_windows_use_normal_limit(self):
        p=self.policy()
        for now in [999,1600,2000]:self.assertEqual(workers.effective_worker_limit(p,now),3)
        p['temporary_override']['authorized_by']='assistant';self.assertEqual(workers.effective_worker_limit(p,1100),3)
    def test_disabled_ordinary_usage_and_invalid_windows(self):
        p=self.policy();p['ordinary_usage_allowed']=False;self.assertEqual(workers.effective_worker_limit(p,1100),0)
        p=self.policy();p['temporary_override']['expires_unix']=float('inf');self.assertEqual(workers.effective_worker_limit(p,1100),3)
        p=self.policy();p['temporary_override']['max_workers']=99;self.assertEqual(workers.effective_worker_limit(p,1100),6)
    def test_claim_enforces_window_but_current_leases_survive_expiry(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);storage.write(root/'attachments/state.json',dict(worker_pool_policy=self.policy()))
            rows=[workers.claim(root,'task'+str(i),'W'+str(i),['folder'+str(i)],now=1500) for i in range(6)]
            with self.assertRaises(ValueError):workers.claim(root,'task6','W6',['folder6'],now=1501)
            workers.update(root,'task5',rows[-1]['token'],now=1600)
            with self.assertRaises(ValueError):workers.claim(root,'task6','W6',['folder6'],now=1601)
            for row in rows[:4]:workers.update(root,row['task'],row['token'],release=True,now=1602)
            workers.claim(root,'task6','W6',['folder6'],now=1603)

if __name__=='__main__':unittest.main()
