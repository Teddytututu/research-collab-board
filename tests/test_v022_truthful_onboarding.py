"""First-use facts remain distinct from defaults and initialization examples."""
from pathlib import Path
import http.client,json,shutil,subprocess,tempfile,threading,time,unittest
from board import project,storage,scheduler,provider_bridge,onboarding
from board.app import conversation,create_server

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(ROOT/'work/tests')

class TruthfulFirstUse(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        project.initialize(self.root,'Fictional first use')
    def tearDown(self):self.tmp.cleanup()
    def legacy_seed(self):
        old=next((p for p in project.all_posts(self.root) if p.get('client_id')=='project-kickoff-v2'),None)
        return old or project.post(self.root,'Claude','Legacy automatic introduction',client_id='project-kickoff-v2')
    def test_new_regular_project_has_zero_assistant_messages(self):
        self.assertEqual(project.all_posts(self.root),[])
        self.assertEqual(conversation(self.root)['items'],[])
        self.assertEqual(project.ledger(self.root).read_bytes(),b'')
    def test_demo_examples_are_explicit_and_separate_from_session_opening(self):
        other=self.root/'demo';project.initialize(other,'Fictional demo',demo=True)
        rows=conversation(other)['items'];self.assertEqual(len(rows),2)
        self.assertTrue(all(p.get('message_kind')=='demo' and p.get('source_label')=='示例' for p in rows))
        self.assertTrue(all('示例' in p['body'] for p in rows))
        self.assertFalse(onboarding.status(other,'Claude')['checks']['opening'])
    def test_legacy_seed_gets_a_display_label_and_preserves_ledger_bytes(self):
        self.legacy_seed();path=project.ledger(self.root);before=path.read_bytes()
        view=conversation(self.root)['items'];seed=next(p for p in view if p['author']=='Claude')
        self.assertEqual((seed.get('message_kind'),seed.get('source_label')),('initialization','初始化说明'))
        project.initialize(self.root,'Fictional first use')
        self.assertEqual(path.read_bytes(),before)
    def test_seed_reply_and_reaction_do_not_satisfy_real_counterpart_exchange(self):
        seed=self.legacy_seed();project.post(self.root,'GPT','Actual session opening')
        project.post(self.root,'GPT','Reply to the old introduction',parent_id=seed['id'])
        storage.append(self.root/'attachments/discussion/reactions.jsonl',dict(message_id=seed['id'],actor='GPT',emoji='💡',active=True))
        result=onboarding.status(self.root,'GPT')
        self.assertTrue(result['checks']['opening']);self.assertFalse(result['checks']['reply']);self.assertFalse(result['checks']['reaction'])
        self.assertEqual(result.get('waiting_on'),'Claude')
    def test_real_counterpart_message_reply_and_active_reaction_are_counted(self):
        p=project.post(self.root,'Claude','Actual counterpart opening')
        project.post(self.root,'GPT','Actual response',parent_id=p['id'])
        reaction=self.root/'attachments/discussion/reactions.jsonl'
        storage.append(reaction,dict(message_id=p['id'],actor='GPT',emoji='💡',active=True))
        result=onboarding.status(self.root,'GPT');self.assertTrue(result['checks']['reply']);self.assertTrue(result['checks']['reaction'])
        storage.append(reaction,dict(message_id=p['id'],actor='GPT',emoji='💡',active=False))
        self.assertFalse(onboarding.status(self.root,'GPT')['checks']['reaction'])
    def test_initial_band_remains_unreported_in_schedule(self):
        row=scheduler.refresh(self.root)['agents']['Claude']
        self.assertIsNone(row['reported_at']);self.assertEqual(row.get('quota',{}).get('status'),'unreported')
        self.assertAlmostEqual(row['remaining'],.7)
    def test_configured_fallback_and_native_observation_have_distinct_provenance(self):
        fallback=scheduler.report(self.root,'Claude',**provider_bridge.quota(self.root,'Claude'))['agents']['Claude']
        self.assertEqual(fallback.get('quota',{}).get('status'),'configured-estimate')
        now=time.time();provider_bridge.observe_codex(self.root,{'rateLimits':{'primary':{'usedPercent':31,'resetsAt':now+86400,'windowDurationMins':1440}}},now=now)
        native=scheduler.report(self.root,'GPT',**provider_bridge.quota(self.root,'GPT',now=now+1))['agents']['GPT']
        self.assertEqual(native.get('quota',{}).get('status'),'native')
        self.assertEqual(native['quota']['source'],'codex-app-server');self.assertAlmostEqual(native['quota']['observed_at'],now)
    def test_historical_sourceless_band_is_a_reported_estimate(self):
        storage.update_json(self.root,'attachments/agents.json',lambda rows:rows['Claude'].update(updated_at='2026-01-01T00:00:00+00:00'))
        self.assertEqual(scheduler.refresh(self.root)['agents']['Claude'].get('quota',{}).get('status'),'reported-estimate')
    def test_manual_http_report_replaces_native_source_and_observation_stamp(self):
        now=time.time();provider_bridge.observe_codex(self.root,{'rateLimits':{'primary':{'usedPercent':31,'resetsAt':now+86400}}},now=now)
        scheduler.report(self.root,'GPT',**provider_bridge.quota(self.root,'GPT',now=now+1))
        server=create_server(self.root,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            port=server.server_port;c=http.client.HTTPConnection('127.0.0.1',port)
            c.request('POST','/api/quota',json.dumps(dict(agent='GPT',tier='normal',reset_hours=24)),{'Host':f'127.0.0.1:{port}','Origin':f'http://127.0.0.1:{port}','Content-Type':'application/json'})
            response=c.getresponse();row=json.loads(response.read())['agents']['GPT'];c.close();self.assertEqual(response.status,200)
            self.assertEqual(row.get('quota',{}).get('status'),'manual-estimate')
            record=storage.read(self.root/'attachments/agents.json')['GPT']
            self.assertEqual(record.get('source'),'manual-band-estimate');self.assertIsNone(record.get('observed_at'))
        finally:server.shutdown();server.server_close();thread.join()
    @unittest.skipUnless(shutil.which('node'),'Node runs real quota-panel behaviour')
    def test_quota_panel_behavior(self):
        result=subprocess.run(['node','--test','--test-isolation=none','tests/quota-truth.test.cjs'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

if __name__=='__main__':unittest.main()
