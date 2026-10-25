"""Independent-review behaviours: asynchronous wakes, restrictions and entry routing."""
from pathlib import Path
import json, os, subprocess, sys, tempfile, unittest
from board import provider_bridge as bridge, project, scheduler, storage, onboarding

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True,exist_ok=True)
tempfile.tempdir=str(ROOT/'work/tests')

class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        project.initialize(self.root,'Fictional review');scheduler.refresh(self.root)
    def tearDown(self):self.tmp.cleanup()
    def host(self):
        bridge.request_goal(self.root,'GPT','Finish finite setup')
        host=bridge.CodexSessionHost(self.root,'review-thread',lambda m,p:{'goal':{'threadId':p['threadId'],'status':p['status']}})
        host.apply();self.addCleanup(host.close);return host
    def test_async_turn_rearms_after_the_later_schedule_report(self):
        host=self.host();when=host.timer['when'];turns=[]
        self.assertTrue(host.dispatch_due(turns.append,now=when))
        self.assertFalse(host.dispatch_due(turns.append,now=when+1))
        storage.update_json(self.root,'attachments/schedule.json',lambda s:s['agents']['GPT'].update(next_wake=when+3600))
        host.apply()
        self.assertTrue(host.dispatch_due(turns.append,now=when+3600));self.assertEqual(len(turns),2)
        self.assertEqual(bridge.controls(self.root)['GPT']['patrol_status'],'running-session')
    def test_pause_revokes_previously_armed_timer_before_dispatch(self):
        host=self.host();when=host.timer['when']
        scheduler.report(self.root,'GPT',remaining=.03,reset_hours=24,source='operator-report')
        self.assertFalse(host.dispatch_due(lambda _:self.fail('Paused patrol started a turn'),now=when))
        self.assertIsNone(host.timer)
        self.assertEqual(bridge.controls(self.root)['GPT']['patrol_status'],'paused-quota')
    def test_changed_future_wake_replaces_the_previous_due_time(self):
        host=self.host();when=host.timer['when']
        storage.update_json(self.root,'attachments/schedule.json',lambda s:s['agents']['GPT'].update(next_wake=when+1000))
        self.assertFalse(host.dispatch_due(lambda _:self.fail('Old wake fired'),now=when))
        self.assertEqual(host.timer['when'],when+1000)
    def test_provider_disable_revokes_timer_before_a_new_patrol_report(self):
        host=self.host();when=host.timer['when']
        bridge.observe_codex(self.root,{'ordinaryUsageAllowed':False})
        self.assertFalse(host.dispatch_due(lambda _:self.fail('Provider disabled ordinary work'),now=when))
        self.assertEqual(bridge.controls(self.root)['GPT']['patrol_status'],'paused-quota')
    def test_closed_host_preserves_goal_and_stops_its_patrol(self):
        host=self.host();host.close()
        self.assertEqual(host.apply(),[])
        self.assertEqual(bridge.controls(self.root)['GPT']['goal']['thread_id'],'review-thread')
        self.assertEqual(bridge.controls(self.root)['GPT']['patrol']['status'],'stopped-with-host')
    def test_replaced_host_cancels_its_timer_and_preserves_new_host_receipt(self):
        old=self.host();when=old.timer['when']
        bridge.request_goal(self.root,'GPT','Continue setup in the replacement host')
        new=bridge.CodexSessionHost(self.root,'replacement-thread',lambda m,p:{'goal':{'threadId':p['threadId'],'status':p['status']}})
        self.addCleanup(new.close);new.apply()
        receipt=(self.root/'attachments/provider-controls.json').read_bytes()
        self.assertFalse(old.dispatch_due(lambda _:self.fail('Replaced host started a patrol'),now=when))
        self.assertIsNone(old.timer);old.close()
        self.assertEqual((self.root/'attachments/provider-controls.json').read_bytes(),receipt)
    def test_expired_disabled_observation_stays_restricted_until_positive_refresh(self):
        payload={'ordinaryUsageAllowed':False,'rateLimits':{'primary':{'usedPercent':40,'resetsAt':87400,'windowDurationMins':10080}}}
        bridge.observe_codex(self.root,payload,now=1000)
        for now in [1001,1000+bridge.MAX_AGE+1,87401]:
            value=bridge.quota(self.root,'GPT',now=now)
            self.assertEqual(value['remaining'],0);self.assertFalse(value['ordinary_usage_allowed'])
        bridge.observe_codex(self.root,{'rateLimits':payload['rateLimits']},now=2000)
        self.assertEqual(bridge.quota(self.root,'GPT',now=2001)['remaining'],0)
        bridge.observe_codex(self.root,dict(payload,ordinaryUsageAllowed=True),now=2002)
        self.assertEqual(bridge.quota(self.root,'GPT',now=2003)['remaining'],.6)
    def test_disabled_without_windows_also_latches(self):
        bridge.observe_codex(self.root,{'ordinaryUsageAllowed':False},now=1000)
        self.assertEqual(bridge.quota(self.root,'GPT',now=5000)['remaining'],0)
    def test_expired_low_observation_is_a_conservative_bound_through_reset(self):
        bridge.observe_codex(self.root,{'rateLimits':{'primary':{'usedPercent':97,'resetsAt':87400}}},now=1000)
        value=bridge.quota(self.root,'GPT',now=1901)
        self.assertEqual(value['remaining'],.03)
        self.assertTrue(scheduler.compute_schedule({'GPT':value},{},now=1901)['agents']['GPT']['paused'])
    def test_desktop_goal_and_patrol_keep_both_ids_in_either_order(self):
        for agent in ['GPT','Claude']:
            for kinds in [('goal','scheduled-task'),('scheduled-task','goal')]:
                for kind in kinds:
                    result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/onboarding.py'),'native-result',agent,
                        '--kind',kind,'--id',agent+'-'+kind,'--data-dir',str(self.root)],capture_output=True,text=True,encoding='utf-8')
                    self.assertEqual(result.returncode,0,result.stderr)
                row=bridge.controls(self.root)[agent]
                self.assertEqual(row['goal']['thread_id'],agent+'-goal')
                self.assertEqual(row['patrol']['id'],agent+'-scheduled-task')
                checks=onboarding.status(self.root,agent)['checks']
                self.assertTrue(checks['native_control']);self.assertTrue(checks['patrol'])
    def test_documented_commands_route_from_a_dependency_free_launcher(self):
        for script,args in [('onboarding.py',['status','GPT','--data-dir',str(self.root)]),
                            ('artwork.py',['list','--data-dir',str(self.root)]),
                            ('post_message.py',['--recent','--root',str(self.root)])]:
            result=subprocess.run([sys.executable,'-B','-S',str(ROOT/'scripts'/script),*args],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
