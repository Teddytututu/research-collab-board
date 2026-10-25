from pathlib import Path
import tempfile,unittest
from board import storage,workers

class SharedWrites(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_target_board_row_and_previous_bytes(self):
        p=self.root/'board.md';old=b'# Board\r\n| T1 | First | ready | GPT |\r\n| T2 | Second | ready | Claude |\r\n';p.write_bytes(old)
        workers.update_board(self.root,'T1','review')
        self.assertEqual(p.read_bytes(),old.replace(b'First | ready',b'First | review'))
        self.assertIn(old,[x.read_bytes() for x in (self.root/'history').glob('*')])
    def test_json_field_and_append_preserve_other_data(self):
        p=self.root/'attachments/state.json';storage.write(p,{'tasks':{'A':{'done':1},'B':{'done':2}}});old=p.read_bytes()
        storage.update_json(self.root,'attachments/state.json',lambda v:v['tasks']['A'].update(done=3))
        self.assertEqual(storage.read(p)['tasks']['B'],{'done':2})
        self.assertIn(old,[x.read_bytes() for x in (p.parent/'history').glob('*')])
        log=self.root/'exchange.md';log.write_bytes(b'Original\r\n')
        workers.append_shared(self.root,'exchange.md','New\n')
        self.assertEqual(log.read_bytes(),b'Original\r\nNew\n')
    def test_shared_relative_path_boundary(self):
        with self.assertRaises(ValueError):workers.append_shared(self.root,'../outside.md','text')
        with self.assertRaises(ValueError):storage.update_json(self.root,'../outside.json',lambda v:v.update(x=1))
