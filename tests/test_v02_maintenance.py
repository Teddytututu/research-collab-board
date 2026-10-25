from pathlib import Path
import tempfile,unittest,subprocess,sys
from board import maintenance,workers

class Maintenance(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_number_reservations_are_unique_across_processes_and_archives(self):
        (self.root/'tasks').mkdir();(self.root/'tasks/archive.md').write_text('| T049 | old | accepted | GPT |\n')
        script=Path(__file__).resolve().parents[1]/'scripts/task_number.py'
        jobs=[subprocess.Popen([sys.executable,'-B',str(script),'--data-dir',str(self.root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(4)]
        values=[]
        for p in jobs:
            out,err=p.communicate(timeout=20);self.assertEqual(p.returncode,0,err);values.append(out.decode().strip())
        self.assertEqual(set(values),{'T050','T051','T052','T053'})
    def test_compaction_preserves_original_rows_and_is_idempotent(self):
        p=self.root/'board.md';old=b'# Tasks\r\n| T1 | ready | accepted | GPT |\r\n| T2 | run | doing | GPT |\r\n';p.write_bytes(old)
        self.assertEqual(maintenance.compact_board(self.root)['moved'],['T1'])
        self.assertIn(b'| T1 | ready | accepted | GPT |\r\n',(self.root/'tasks/archive.md').read_bytes())
        self.assertEqual(p.read_bytes(),b'# Tasks\r\n| T2 | run | doing | GPT |\r\n')
        self.assertEqual(maintenance.compact_board(self.root)['moved'],[])
        self.assertIn(old,[x.read_bytes() for x in (self.root/'history').glob('*')])
    def test_daily_split_keeps_raw_bytes_and_hardlink_after_append(self):
        raw=b'# Exchange\r\n### 2030-01-01 10:00\r\nOld\r\n### 2030-01-02 10:00\r\nToday\r\n';p=self.root/'exchange.md';p.write_bytes(raw)
        r=maintenance.split_exchange(self.root,'2030-01-02')
        self.assertEqual((self.root/r['source_archive']).read_bytes(),raw)
        daily=self.root/'exchange/2030-01-02.md';self.assertTrue(p.samefile(daily))
        workers.append_shared(self.root,'exchange.md','Added\n')
        self.assertTrue(p.samefile(daily));self.assertTrue(daily.read_bytes().endswith(b'Added\n'))
        self.assertTrue(maintenance.split_exchange(self.root,'2030-01-02')['already_daily'])
    def test_dated_heading_in_code_fence_stays_with_its_message(self):
        raw=b'### 2030-01-01 10:00\n```\n### 2099-01-01 10:00\n```\nbody\n'
        self.assertEqual(maintenance.blocks(raw)[1],[('2030-01-01',raw)])
