"""Environment-selected ports and local initialization are real entry contracts."""
import contextlib,importlib.util,io,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from board import __main__ as cli
ROOT=Path(__file__).resolve().parents[1]
TEST_ROOT=ROOT/'work/tests';TEST_ROOT.mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(TEST_ROOT)
spec=importlib.util.spec_from_file_location('board_bootstrap_under_test',ROOT/'scripts/bootstrap.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)

class StartupDefaults(unittest.TestCase):
    def parse_both(self,extra=()):
        return [cli.parse_args(['start','Fictional project',*extra]),bootstrap.parse_args(['Fictional project',*extra])]
    def test_regular_default_stays_8780(self):
        with patch.dict(os.environ,{},clear=True):self.assertEqual([a.port for a in self.parse_both()],[8780,8780])
    def test_environment_port_is_used_by_both_entries(self):
        with patch.dict(os.environ,{'RESEARCH_BOARD_PORT':'8790'}):self.assertEqual([a.port for a in self.parse_both()],[8790,8790])
    def test_explicit_port_overrides_environment(self):
        with patch.dict(os.environ,{'RESEARCH_BOARD_PORT':'8790'}):self.assertEqual([a.port for a in self.parse_both(['--port','8782'])],[8782,8782])
    def test_invalid_environment_port_is_rejected_before_initialization(self):
        for value in ['wrong','80','65536']:
            with patch.dict(os.environ,{'RESEARCH_BOARD_PORT':value}),contextlib.redirect_stderr(io.StringIO()):
                for parse,args in [(cli.parse_args,['start','Fictional project']),(bootstrap.parse_args,['Fictional project'])]:
                    with self.assertRaises(SystemExit):parse(args)
    def test_cli_initialization_creates_the_local_project(self):
        with tempfile.TemporaryDirectory() as folder:
            args=['board','start','Fictional local project','--data-dir',folder,'--init-only',
                  '--question','Does the local project initialize?','--deliverable','A small local check']
            output=io.StringIO()
            with patch.object(sys,'argv',args),contextlib.redirect_stdout(output):
                cli.main()
            self.assertTrue(json.loads(output.getvalue())['initialized'])
            self.assertTrue((Path(folder)/'project.json').is_file())

if __name__=='__main__':unittest.main()
