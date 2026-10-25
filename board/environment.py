"""Route public entry commands through this project's installed interpreter."""
from pathlib import Path
import os, subprocess, sys

def use_project_environment(script=None, *, module=None):
    root=Path(__file__).resolve().parents[1];env=root/'.venv'
    python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if python.is_file() and (Path(sys.prefix).resolve()!=env.resolve() or sys.flags.no_site):
        target=['-m',module] if module else [str(Path(script).resolve())]
        raise SystemExit(subprocess.run([str(python),'-B',*target,*sys.argv[1:]]).returncode)
