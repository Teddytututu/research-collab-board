"""Process-safe local updates with original bytes retained in runtime history."""
from pathlib import Path
from contextlib import contextmanager
import json,os,threading,time,uuid
_lock=threading.RLock()

@contextmanager
def locked(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with _lock,(root/'.write.lock').open('a+b') as f:
        f.seek(0);f.write(b'0');f.flush();f.seek(0)
        end=time.monotonic()+10
        while True:
            try:
                if os.name=='nt':
                    import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl;fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()>end:raise TimeoutError('Local workspace is busy')
                time.sleep(.02)
        try:yield
        finally:
            if os.name=='nt':
                import msvcrt;f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl;fcntl.flock(f,fcntl.LOCK_UN)

def read(path,default=None):
    path=Path(path)
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

def replace_with_retry(temp,path,timeout=2):
    """Preserve atomic writes while transient Windows readers release handles."""
    deadline=time.monotonic()+timeout
    while True:
        try:
            Path(temp).replace(path)
            return
        except PermissionError as error:
            if os.name!='nt' or getattr(error,'winerror',None) not in {5,32,33} or time.monotonic()>=deadline:raise
            time.sleep(.025)

def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    if path.exists():
        old=path.read_bytes()
        if old==raw:return
        history=path.parent/'history';history.mkdir(exist_ok=True)
        (history/(path.name+'.'+str(time.time_ns())+'.before')).write_bytes(old)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    replace_with_retry(tmp,path)

def append(path,row):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('ab') as f:
        f.write((json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n').encode());f.flush();os.fsync(f.fileno())

def lines(path):
    p=Path(path)
    return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()] if p.exists() else []

def relative_file(root,relative):
    root=Path(root).resolve();part=Path(relative);path=root/part
    if part.is_absolute() or not path.resolve().is_relative_to(root):raise ValueError('Project-relative file required')
    current=path
    while current!=root:
        if current.is_symlink():raise ValueError('Project file required')
        current=current.parent
    return path

def write_bytes(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        old=path.read_bytes()
        if old==raw:return
        history=path.parent/'history';history.mkdir(exist_ok=True)
        (history/(path.name+'.'+str(time.time_ns())+'.before')).write_bytes(old)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    replace_with_retry(temp,path)

def update_json(root,relative,transform):
    with locked(root):
        path=relative_file(root,relative);value=read(path,{})
        transform(value);write(path,value);return value
