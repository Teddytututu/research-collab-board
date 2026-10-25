"""Adapted frozen ETA regressions; all project/task examples are fictional."""
import copy,json,tempfile,unittest
from pathlib import Path
from board import task_eta as e
TEST_ROOT=Path(__file__).resolve().parents[1]/'work/tests'
TEST_ROOT.mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(TEST_ROOT)
class EtaTests(unittest.TestCase):
 def rows(self):return [dict(at=t,done=d,total=100,active=True,phase='p') for t,d in [(0,0),(900,10),(1800,20),(2700,30),(3600,40)]]

 def test_recent_30_to_60_minute_speed(self):
  speed=e.speed(self.rows(),3600);self.assertEqual(speed['source'],'recent');self.assertAlmostEqual(speed['rate'],1/90)
  eta=e.estimate(dict(at=3600,done=40,total=100,active=True,phase='p'),self.rows(),3600)
  self.assertAlmostEqual(e.unix(eta['at']),9000);self.assertEqual(eta['confidence'],'中')

 def test_zero_recent_increment_uses_history(self):
  samples=self.rows()+[dict(at=t,done=40,total=100,active=True,phase='p') for t in [4500,5400,6300,7200]]
  result=e.speed(samples,7200);self.assertEqual(result['source'],'historical');self.assertGreater(result['rate'],0)

 def test_paused_intervals_and_long_gaps_are_excluded(self):
  rows=self.rows();rows[2]['active']=False
  self.assertEqual(len(e.valid_intervals(rows)),2)
  rows=[dict(at=0,done=0,total=100,active=True,phase='p'),dict(at=11000,done=1,total=100,active=True,phase='p')]
  self.assertIsNone(e.speed(rows,11000)['rate'])

 def test_pause_returns_remaining_instead_of_calendar_deadline(self):
  eta=e.estimate(dict(at=3600,done=40,total=100,active=False,phase='p'),self.rows(),3600)
  self.assertEqual(eta['mode'],'paused');self.assertIsNone(eta['at']);self.assertAlmostEqual(eta['remaining_seconds'],5400)

 def test_counter_reset_and_phase_change_do_not_blend(self):
  rows=self.rows()+[dict(at=4500,done=1,total=100,active=True,phase='p'),dict(at=5400,done=11,total=100,active=True,phase='q')]
  self.assertEqual(len(e.valid_intervals(rows)),4)

 def test_explicit_active_seconds_used(self):
  rows=self.rows()[:2];rows[0]['active_seconds']=0;rows[1]['active_seconds']=300
  self.assertEqual(e.valid_intervals(rows)[0]['seconds'],300)

 def test_no_measured_rate_uses_low_confidence_manual_condition(self):
  eta=e.estimate(dict(at=100,done=5,total=10,active=False,phase='p'),[],100,manual=dict(remaining_seconds=7200,basis='两小时人工估计'))
  self.assertEqual(eta['confidence'],'低');self.assertEqual(eta['remaining_seconds'],7200);self.assertEqual(eta['mode'],'paused')

 def test_overdue_and_completed_task_states(self):
  eta=e.task_estimate(dict(estimated_completion='2026-10-23 18:30 HKT'),{},e.unix('2026-10-23T19:00:00+08:00'))
  self.assertTrue(eta['overdue'])
  eta=e.task_estimate(dict(completed_at='2026-10-23T21:06:00+08:00'),{},0)
  self.assertEqual(eta['mode'],'complete')

 def test_calibration_uses_distinct_tasks_and_excludes_interruption(self):
  rows=[dict(task_id=str(i),kind='experiment',issued_at=1,ratio=1.4,valid_for_calibration=True) for i in range(3)]
  rows.append(dict(task_id='old',kind='experiment',issued_at=1,ratio=8,valid_for_calibration=False))
  factor,n=e.correction(rows);self.assertEqual(n,3);self.assertAlmostEqual(factor,1.4)
  eta=e.estimate(dict(at=3600,done=40,total=100,active=True,phase='p'),self.rows(),3600,factor,n)
  self.assertAlmostEqual(eta['remaining_seconds'],7560);self.assertIn('1.4',eta['basis'])

 def test_completed_csv_export_is_idempotent(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'attachments/eta').mkdir(parents=True)
   row=e.calibration_row('T001',dict(issued_at=100,at=200),210)
   e.export_csv(root,[row]);path=root/'attachments/eta/estimates.csv';before=path.read_bytes()
   e.export_csv(root,[row]);self.assertEqual(path.read_bytes(),before);self.assertEqual(row['delay_seconds'],10)

 def test_mixed_hkt_and_iso_dates(self):
  self.assertEqual(e.unix('预计完成2026-10-23 21:25（把握：中）'),e.unix('2026-10-23T21:25:00+08:00'))
  self.assertIsNone(e.unix('等独立盲数完成后约2小时'))

 def test_delivered_package_uses_release_as_actual(self):
  eta=e.task_estimate(dict(state='review',released_at='2026-10-23T21:20:42+08:00',eta=dict(at='2026-10-23T21:25:00+08:00')),{},0)
  self.assertEqual(eta['mode'],'complete');self.assertIn('21:20:42',eta['actual_at'])

 def test_historical_forecast_with_unknown_issue_time_keeps_delay_only(self):
  row=e.calibration_row('T002',dict(issued_at=None,at='2026-10-23T18:30:00+08:00'),'2026-10-23T21:20:00+08:00')
  self.assertEqual(row['delay_seconds'],10200);self.assertFalse(row['valid_for_calibration']);self.assertIsNone(row['ratio'])

 def test_worker_field_aliases_and_explicit_actual_completion(self):
  eta=e.task_estimate(dict(estimated_completion='2026-10-23 22:00',eta_confidence='high',eta_basis='局部回归与截图'),{},0)
  self.assertEqual(eta['confidence'],'高');self.assertIn('局部回归',eta['basis'])
  tagged=e.task_estimate(dict(estimated_completion='2026-10-23 23:50（中）· 先做小对照再整理报告'),{},0)
  self.assertEqual(tagged['confidence'],'中');self.assertIn('先做小对照',tagged['basis'])
  eta=e.task_estimate(dict(state='review',actual_completed_at='2026-10-23 21:20:14',released_at='2026-10-23 21:20:42'),{},0)
  self.assertIn('21:20:14',eta['actual_at'])

 def test_board_refresh_throttles_and_retains_other_fields(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'attachments/eta').mkdir(parents=True)
   path=root/'attachments/state.json';path.write_text(json.dumps(dict(tasks={},unrelated={'value':7})),encoding='utf-8')
   e.refresh(root,{},10000);first=path.read_bytes()
   e.refresh(root,{},10020);self.assertEqual(first,path.read_bytes())
   e.refresh(root,{},10301);self.assertNotEqual(first,path.read_bytes())
   self.assertEqual(json.loads(path.read_text())['unrelated'],{'value':7})

 def test_empty_project_has_no_master_experiment_rows(self):
  self.assertEqual(e.snapshot(dict(tasks={}),{},100)['runs'],[])

 def test_revised_task_prediction_uses_revision_issue_time(self):
  state=dict(tasks={'X':dict(started_at=100,estimated_completion=e.iso(1000))})
  e.record(state,200);state['tasks']['X']['estimated_completion']=e.iso(2000);e.record(state,500)
  self.assertEqual(state['eta_tracking']['predictions']['X'][-1]['issued_at'],500)

class GenericStages(unittest.TestCase):
 def stage(self,**values):
  row=dict(id='comparison',name='Fictional comparison',phase='generate',done=4,total=10,at=3600,active=True)
  row.update(values);return row
 def test_separate_generation_and_scoring_stages(self):
  stages=[self.stage(id='generate',done=10),self.stage(id='score',phase='score',done=9,active=False)]
  state=dict(tasks={'T001':dict(eta_stages=stages)})
  result=e.snapshot(state,{},3600)
  self.assertEqual(next(r for r in result['runs'] if r['id']=='generate')['eta']['mode'],'complete')
  self.assertEqual(next(r for r in result['runs'] if r['id']=='score')['eta']['mode'],'paused')
 def test_latest_counts_replace_old_projection_without_mutating_source(self):
  state=dict(tasks={},runs={'comparison':self.stage(done=6)})
  before=copy.deepcopy(state);result=e.snapshot(state,dict(runs=[self.stage(done=2)]),3600)
  self.assertEqual(result['runs'][0]['done'],6);self.assertEqual(state,before)
 def test_fixed_prediction_with_unchanged_counter(self):
  samples=[dict(at=t,done=d,total=41,active=True,phase='generate') for t,d in [(0,0),(900,10),(1800,20),(2700,30),(3600,40)]]
  state=dict(tasks={},runs={'comparison':self.stage(done=40,total=41)},eta_tracking=dict(observations={'comparison':samples}))
  e.record(state,3600);before=state['eta_tracking']['run_estimates']['comparison']['eta']['at']
  e.record(state,3900);self.assertEqual(state['eta_tracking']['run_estimates']['comparison']['eta']['at'],before)
  self.assertTrue(e.snapshot(state,{},4000)['runs'][0]['eta']['overdue'])
 def test_explicit_sample_label_and_stale_stage(self):
  state=dict(tasks={'T001':dict(completed_at='2030-01-01 12:00',completion_label='已交示例')},runs={'comparison':self.stage(at=100)})
  result=e.snapshot(state,{},3600)
  self.assertEqual(result['task_etas']['T001']['completion_label'],'已交示例')
  self.assertEqual(result['runs'][0]['eta']['mode'],'conditional')
 def test_comparable_kind_calibration_keeps_groups_separate(self):
  rows=[dict(task_id=str(i),kind='manual:analysis',issued_at=1,ratio=1.4,valid_for_calibration=True) for i in range(3)]
  self.assertAlmostEqual(e.correction(rows,'manual:analysis')[0],1.4)
  self.assertEqual(e.correction(rows,'manual:implementation'),(1.0,0))
if __name__=='__main__':unittest.main()
