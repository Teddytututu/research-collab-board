"""Synthetic lifecycle forecast boundaries in a disposable, candidate-only data root."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import subprocess,sys,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from board import project,storage
from board.lifecycle import transition,check,estimate_progress,declared_eta


class Forecast(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work/tests')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        project.initialize(self.root,'Example','Compare methods','Report')
        (self.root/'tasks').mkdir()
        (self.root/'tasks/T001-example.md').write_text('# Example\n',encoding='utf-8')
        self.now=datetime(2030,1,2,10,tzinfo=timezone(timedelta(hours=8)))
        transition(self.root,'new','T001',by='Claude',title='Example',when='Inputs ready',now=self.now)

    def start(self):
        return transition(self.root,'start','T001',by='GPT',status='0/10 · 估不了：baseline setup',now=self.now)

    def progress(self,status,minutes=60):
        return transition(self.root,'progress','T001',by='GPT',status=status,now=self.now+timedelta(minutes=minutes))

    def test_start_requires_clock_or_reason_before_any_write(self):
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError,'Start requires'):
            transition(self.root,'start','T001',by='GPT',status='0/10',now=self.now)
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_speed_forecast_written_consistently_into_each_projection(self):
        self.start();row=self.progress('5/10 · 估不了：review batches')
        self.assertEqual(row['status'],'5/10 · review batches · 约 12:00')
        expected=row['status']
        self.assertIn(expected,(self.root/'board.md').read_text('utf-8'))
        self.assertIn(expected,(self.root/'tasks/T001-example.md').read_text('utf-8'))
        self.assertEqual(storage.read(self.root/'attachments/state.json')['tasks']['T001']['status'],expected)
        self.assertEqual(storage.lines(self.root/'attachments/task-flow.jsonl')[-1]['status'],expected)

    def test_explicit_clock_keeps_user_estimate(self):
        self.start();self.assertEqual(self.progress('5/10 · 约 明天 08:00')['status'],'5/10 · 约 明天 08:00')

    def test_counter_phase_and_twelve_hour_boundaries(self):
        self.start()
        self.assertIsNone(estimate_progress(self.root,'T001','5/20',self.now+timedelta(hours=1)))
        self.assertIsNone(estimate_progress(self.root,'T001','5/10',self.now+timedelta(hours=13)))
        self.progress('8/10');self.progress('1/10 · 估不了：new phase',90)
        self.assertIsNone(estimate_progress(self.root,'T001','0/10',self.now+timedelta(hours=2)))
        self.assertIsNotNone(estimate_progress(self.root,'T001','2/10',self.now+timedelta(hours=2)))

    def test_counter_full_retains_phase_and_checker_requests_delivery(self):
        self.start();row=self.progress('10/10')
        self.assertEqual(row['status'],'10/10')
        self.assertIn('counter_complete',{i['code'] for i in check(self.root,now=self.now+timedelta(hours=1))})

    def test_checker_missing_invalid_and_overdue(self):
        self.start()
        # Legacy rows remain readable and receive scoped actionable diagnostics.
        for status,code in [('1/10','eta_missing'),('1/10 · 约 99:99','eta_invalid'),('1/10 · 约 10:10','eta_overdue')]:
            path=self.root/'board.md';text=path.read_text('utf-8')
            lines=text.splitlines()
            for index,line in enumerate(lines):
                if line.startswith('| T001 |'):
                    cells=line.split('|');cells[3]=' '+status+' ';lines[index]='|'.join(cells)
            path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            self.assertIn(code,{i['code'] for i in check(self.root,now=self.now+timedelta(minutes=41))})

    def test_clock_dates_midnight_and_invalid_dates(self):
        self.assertEqual(declared_eta('约 明天 08:00',self.now),self.now.replace(hour=8)+timedelta(days=1))
        self.assertEqual(declared_eta('约 01-04 13:00',self.now),self.now.replace(day=4,hour=13))
        self.assertEqual(declared_eta('约 09:00',self.now),self.now.replace(hour=9)+timedelta(days=1))
        self.assertIsNone(declared_eta('约 02-31 13:00',self.now))
        self.assertIsNone(declared_eta('约 24:00',self.now))

    def test_authority_and_archived_task_protection_survive_forecast(self):
        self.start();self.progress('5/10')
        before=(self.root/'board.md').read_bytes()
        with self.assertRaises(ValueError):transition(self.root,'accept','T001',by='GPT',summary='Ready',now=self.now)
        self.assertEqual((self.root/'board.md').read_bytes(),before)
        transition(self.root,'stop','T001',by='Claude',reason='Scope complete',now=self.now)
        with self.assertRaises(ValueError):self.progress('6/10')

    def test_declared_clock_display_contracts(self):
        result=subprocess.run(['node','--test',str(ROOT/'tests/forecast.test.cjs')],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
