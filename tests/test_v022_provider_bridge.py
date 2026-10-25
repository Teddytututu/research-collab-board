"""Provider observations remain factual, private and usable during onboarding."""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
from board.project import initialize
from board import provider_bridge as bridge
ROOT = Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True,exist_ok=True)
tempfile.tempdir = str(ROOT/'work/tests')

class ProviderBridge(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def observed(self,used=30,now=1000):
        return bridge.observe_codex(self.root,{'accountId':'private-account','accessToken':'private-token',
            'rateLimits':{'primary':{'usedPercent':used,'resetsAt':1000+7*24*3600,'windowDurationMins':10080},
                          'secondary':{'usedPercent':5,'resetsAt':1000+3600,'windowDurationMins':300}}},now=now)
    def test_native_observation_uses_most_constrained_window_and_strips_identity(self):
        self.observed();value=bridge.quota(self.root,'GPT',now=1001)
        self.assertAlmostEqual(value['remaining'],.7);self.assertAlmostEqual(value['reset_hours'],(7*24*3600-1)/3600)
        self.assertEqual(value['precision'],'provider_percent');self.assertEqual(value['source'],'codex-app-server')
        self.assertNotIn('private-',(self.root/'attachments/provider-observations.json').read_text())
    def test_native_image_metadata_omits_payload_and_preserves_completed_job_on_replay(self):
        bridge.observe_image(self.root,dict(type='imageGeneration',id='native-job',status='completed',savedPath='generated/example.png',revisedPrompt='Original character',result='fake-large-image-payload',accessToken='private-token'))
        bridge.observe_image(self.root,dict(type='imageGeneration',id='native-job',status='in_progress',savedPath=None))
        raw=(self.root/'attachments/provider-images.json').read_text();record=json.loads(raw)['native-job']
        self.assertEqual(record['status'],'completed');self.assertEqual(record['revised_prompt'],'Original character')
        self.assertNotIn('private-token',raw);self.assertNotIn('fake-large-image-payload',raw)
    def test_second_distinct_observation_keeps_observed_before_after(self):
        self.observed();self.observed(31,now=1100);value=bridge.quota(self.root,'GPT',now=1101)
        self.assertEqual((value['observed_before'],value['observed_after']),(.7,.69))
        self.assertNotIn('before',value)
    def test_expired_observation_uses_labelled_band_and_estimated_reset(self):
        self.observed();value=bridge.quota(self.root,'GPT',now=1000+bridge.MAX_AGE+1)
        self.assertEqual(value['precision'],'band');self.assertEqual(value['source'],'configured-band-estimate')
        self.assertIn('estimate',value['reset_source']);self.assertNotIn('before',value)
    def test_invalid_provider_numbers_fail_before_writing(self):
        with self.assertRaises(ValueError):self.observed(float('nan'))
        self.assertFalse((self.root/'attachments/provider-observations.json').exists())
    def test_goal_request_and_actual_ack_preserve_request_identity(self):
        req=bridge.request_goal(self.root,'GPT','Complete this project setup')
        self.assertEqual(bridge.pending(self.root),[req])
        bridge.acknowledge(self.root,req['id'],{'provider':'codex-app-server','thread_id':'test-context','status':'active'})
        self.assertEqual(bridge.pending(self.root),[])
        self.assertEqual(bridge.controls(self.root)['GPT']['thread_id'],'test-context')
    def test_arbitrary_provider_actions_are_rejected(self):
        with self.assertRaises(ValueError):bridge.request_goal(self.root,'Other','test')
        with self.assertRaises(ValueError):bridge.request_goal(self.root,'GPT','test',status='paused')
    def test_patrol_auto_reports_native_values_into_unchanged_scheduler(self):
        initialize(self.root,'Fictional study');bridge.observe_codex(self.root,{'rateLimits':{'primary':{
            'usedPercent':30,'resetsAt':__import__('time').time()+7200,'windowDurationMins':300}}})
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/patrol.py'),'GPT','--auto','--data-dir',str(self.root)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        row=json.loads((self.root/'attachments/agents.json').read_text())['GPT']
        self.assertEqual(row['remaining'],.7);self.assertEqual(row['source'],'codex-app-server')
        self.assertAlmostEqual(row['reset_hours'],2,places=2)
    def test_fallback_is_operational_without_host_or_private_configuration(self):
        initialize(self.root,'Fictional study')
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/patrol.py'),'Claude','--auto','--data-dir',str(self.root)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        row=json.loads((self.root/'attachments/agents.json').read_text())['Claude']
        self.assertEqual((row['precision'],row['source']),('band','configured-band-estimate'))
    def test_host_registers_native_goal_and_fires_only_its_due_session_patrol(self):
        initialize(self.root,'Fictional study')
        from board import scheduler
        schedule=scheduler.refresh(self.root);when=schedule['agents']['GPT']['next_wake']
        req=bridge.request_goal(self.root,'GPT','Complete setup');calls=[]
        def rpc(method,params):
            calls.append((method,params));return {'goal':{'threadId':'test-context','status':'active'}}
        host=bridge.CodexSessionHost(self.root,'test-context',rpc);host.apply()
        self.assertEqual(calls[0][0],'thread/goal/set')
        self.assertEqual(bridge.controls(self.root)['GPT']['patrol_status'],'scheduled-session')
        wakes=[];self.assertFalse(host.dispatch_due(wakes.append,now=when-1));self.assertTrue(host.dispatch_due(wakes.append,now=when))
        self.assertIn('docs/patrol.md',wakes[0]);host.close()
        self.assertEqual(bridge.controls(self.root)['GPT']['patrol_status'],'stopped-with-host')
    def test_native_rpc_error_leaves_a_reviewable_error_and_empty_control(self):
        bridge.request_goal(self.root,'GPT','Complete setup')
        def rpc(method,params):raise RuntimeError('simulated provider failure')
        host=bridge.CodexSessionHost(self.root,'test-context',rpc);host.apply()
        self.assertEqual(bridge.controls(self.root),{});self.assertEqual(bridge.pending(self.root),[])
    def test_request_reader_waits_for_an_in_progress_coordinated_append(self):
        import threading,time
        from board import storage
        first=threading.Event();path=self.root/'attachments/provider-requests.jsonl';path.parent.mkdir(parents=True)
        row={'id':'concurrent-request','agent':'GPT','action':'goal','status':'active','objective':'Finish setup'}
        raw=(json.dumps(row)+'\n').encode()
        def write():
            with storage.locked(self.root),path.open('ab') as f:
                cut=len(raw)//2;f.write(raw[:cut]);f.flush();first.set();time.sleep(.05);f.write(raw[cut:]);f.flush()
        writer=threading.Thread(target=write);writer.start();self.assertTrue(first.wait(2))
        try:self.assertEqual(bridge.pending(self.root),[row])
        finally:writer.join(2)

if __name__=='__main__':unittest.main()
