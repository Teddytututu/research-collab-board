"""Install pinned-range dependencies in this project's venv, including on Windows.

Python 3.13+ mode-0700 temporary directories lose the restricted-token SID on
Windows. Only this installation process uses inherited directory permissions,
and only beneath the authorized project. The OS and interpreter stay intact.
"""
from pathlib import Path
import os, runpy, sys, tempfile, uuid
ROOT=Path(__file__).resolve().parents[1]

def project_temp(suffix=None,prefix=None,dir=None):
    folder=Path(os.fsdecode(dir)) if dir else ROOT/'work/dependency-temp'
    folder=folder.resolve()
    if not folder.is_relative_to(ROOT):raise ValueError('Dependency temporary directory stays in the project')
    folder.mkdir(parents=True,exist_ok=True)
    name=os.fsdecode(prefix or 'tmp')+uuid.uuid4().hex+os.fsdecode(suffix or '')
    result=folder/name
    if result.parent.resolve()!=folder or not result.resolve().is_relative_to(ROOT):raise ValueError('Project-local temporary basename required')
    os.mkdir(result,0o777)
    return os.fsencode(result) if isinstance(dir,bytes) or isinstance(prefix,bytes) or isinstance(suffix,bytes) else str(result)

def main():
    folder=ROOT/'work/dependency-temp';folder.mkdir(parents=True,exist_ok=True)
    os.environ.update(TEMP=str(folder),TMP=str(folder),PIP_CACHE_DIR=str(ROOT/'work/pip-cache'))
    tempfile.tempdir=str(folder)
    if os.name=='nt' and sys.version_info>=(3,13):tempfile.mkdtemp=project_temp
    import ensurepip
    wheels=sorted((Path(ensurepip.__file__).parent/'_bundled').glob('pip-*.whl'))
    if not wheels:raise RuntimeError('This Python installation needs its standard ensurepip wheel')
    wheel=wheels[-1];sys.path.insert(0,str(wheel))
    sys.argv=['pip','install','--disable-pip-version-check','--no-input',str(wheel),'-r',str(ROOT/'requirements.txt')]
    runpy.run_module('pip',run_name='__main__',alter_sys=True)

if __name__=='__main__':main()
