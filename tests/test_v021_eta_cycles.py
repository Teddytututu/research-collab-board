"""A newly claimed task cycle keeps prior delivery clocks as history."""
import unittest
from board import task_eta as eta
from board import workers,storage
from pathlib import Path
import tempfile
TEST_ROOT=Path(__file__).resolve().parents[1]/'work/tests'
TEST_ROOT.mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(TEST_ROOT)

class TaskCycles(unittest.TestCase):
    def reclaimed(self):
        return dict(state='in_progress',claimed_at='2030-01-01T15:00:00+08:00',
            actual_completed_at='2030-01-01T13:00:00+08:00',released_at='2030-01-01T13:01:00+08:00',
            estimated_completion='2030-01-01T16:00:00+08:00',eta_confidence='medium',eta_basis='Current revision')
    def test_new_claim_uses_current_forecast_after_a_previous_delivery(self):
        result=eta.task_estimate(self.reclaimed(),{},eta.unix('2030-01-01T15:10:00+08:00'))
        self.assertEqual(result['mode'],'estimate')
        self.assertEqual(eta.unix(result['at']),eta.unix('2030-01-01T16:00:00+08:00'))
    def test_current_cycle_completion_still_displays_its_actual_delivery(self):
        task=self.reclaimed();task.update(state='review',actual_completed_at='2030-01-01T15:50:00+08:00')
        result=eta.task_estimate(task,{},eta.unix('2030-01-01T16:00:00+08:00'))
        self.assertEqual(result['mode'],'complete')
        self.assertEqual(eta.unix(result['actual_at']),eta.unix('2030-01-01T15:50:00+08:00'))
    def test_reclaim_keeps_history_and_records_a_fresh_prediction(self):
        task=self.reclaimed()
        old=dict(at='2030-01-01T13:00:00+08:00',issued_at='2030-01-01T12:00:00+08:00',kind='manual:T001')
        state=dict(tasks={'T001':task},eta_tracking=dict(predictions={'T001':[old.copy()]}))
        eta.record(state,eta.unix('2030-01-01T15:10:00+08:00'))
        predictions=state['eta_tracking']['predictions']['T001']
        self.assertEqual(predictions[0],old)
        self.assertEqual(eta.unix(predictions[-1]['at']),eta.unix(task['estimated_completion']))
        self.assertGreaterEqual(eta.unix(predictions[-1]['issued_at']),eta.unix(task['claimed_at']))
        self.assertEqual(state['tasks']['T001']['actual_completed_at'],'2030-01-01T13:00:00+08:00')

    def test_public_worker_claim_and_release_publish_the_current_cycle(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            old=self.reclaimed();old.update(state='review',claimed_at='2030-01-01T12:00:00+08:00')
            storage.write(root/'attachments/state.json',dict(tasks={'T001':old}))
            row=workers.claim(root,'T001','W1',['board'],now=eta.unix('2030-01-01T15:00:00+08:00'),eta='2030-01-01T16:00:00+08:00')
            task=storage.read(root/'attachments/state.json')['tasks']['T001']
            self.assertEqual(eta.task_estimate(task,{},eta.unix('2030-01-01T15:10:00+08:00'))['mode'],'estimate')
            workers.update(root,'T001',row['token'],release=True,now=eta.unix('2030-01-01T15:20:00+08:00'))
            task=storage.read(root/'attachments/state.json')['tasks']['T001']
            result=eta.task_estimate(task,{},eta.unix('2030-01-01T16:00:00+08:00'))
            self.assertEqual(result['mode'],'complete')
            self.assertEqual(eta.unix(result['actual_at']),eta.unix('2030-01-01T15:20:00+08:00'))
            self.assertEqual(task['actual_completed_at'],'2030-01-01T13:00:00+08:00')

if __name__=='__main__':unittest.main()
