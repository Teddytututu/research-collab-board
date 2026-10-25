"""Run the package regressions with its own dependencies and scoped temp dirs."""
from pathlib import Path
import os,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]

def main():
    env=ROOT/'.venv';python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if python.exists() and Path(sys.prefix).resolve()!=env.resolve():
        return subprocess.run([str(python),'-B',str(Path(__file__).resolve())],cwd=ROOT).returncode
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
    from install_deps import project_temp
    if os.name=='nt' and sys.version_info>=(3,13):tempfile.mkdtemp=project_temp
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_v02*.py')
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
