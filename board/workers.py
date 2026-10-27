"""Local task leases: serialized claims, overlapping scopes and finite heartbeats."""
from pathlib import Path, PurePosixPath
import json, os, re, time, uuid, math
from . import storage, lifecycle

TTL = 1800

def quota_capacity(remaining, reset_hours, cost=.01, ordinary_allowed=True):
    """Conservative worker limit from finite observed quota inputs."""
    if not all(math.isfinite(float(v)) for v in [remaining,reset_hours,cost]):raise ValueError('Finite quota inputs required')
    if not 0<=remaining<=1 or cost<0:raise ValueError('Quota fraction and cost out of range')
    if not ordinary_allowed or remaining < .1:return 0
    budget=remaining/max(reset_hours,.5)
    allowance=.3*budget*min(24,max(reset_hours,.5))
    return max(0,min(4,math.floor(allowance/max(cost,.0001))))

def effective_worker_limit(policy,at=None):
    """User-authorized finite windows affect new claims, with a CPU ceiling."""
    at=time.time() if at is None else at
    normal=max(0,min(4,int(policy.get('max_workers',1))))
    cpu=max(0,int(policy.get('cpu_slots',6)))
    if not policy.get('ordinary_usage_allowed',True):return 0
    temporary=policy.get('temporary_override') or {}
    try:
        start=float(temporary.get('starts_unix',0));end=float(temporary.get('expires_unix',0))
        requested=int(temporary.get('max_workers',normal))
        authorized=temporary.get('authorized_by')=='user' and bool(temporary.get('authorization'))
        if authorized and math.isfinite(start) and math.isfinite(end) and start<=at<end:
            return min(cpu,max(normal,min(6,requested)))
    except (TypeError,ValueError,OverflowError):pass
    return min(cpu,normal)

def scope(value):
    value = str(value).replace('\\', '/').casefold()
    if value.startswith('/'):raise ValueError('Use a project-relative write scope')
    value=value.rstrip('/').removesuffix('/**').removesuffix('/*')
    if not value or '..' in PurePosixPath(value).parts or ':' in value or '*' in value or '?' in value:
        raise ValueError('Use a project-relative write scope')
    return str(PurePosixPath(value))

def overlaps(a, b):
    a, b = scope(a), scope(b)
    return a == '.' or b == '.' or a == b or a.startswith(b + '/') or b.startswith(a + '/')

def archived_task(root, task):
    from .lifecycle import data_file, parse_board
    root=Path(root).resolve();path=data_file(root,'tasks/archive.md')
    return path.exists() and any(row['task']==task for row in parse_board(path.read_text('utf-8-sig')))


def claim(root, task, worker, scopes, allowed_workers=1, now=None, eta=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', task) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', worker):
        raise ValueError('Use a task and worker identifier')
    if not scopes: raise ValueError('Declare write scopes')
    scopes = [scope(s) for s in scopes]
    now = time.time() if now is None else now
    folder = Path(root) / 'attachments/locks'
    with storage.locked(root):
        if archived_task(root,task):raise ValueError('Task is archived; register a new task through task_flow.py')
        folder.mkdir(parents=True, exist_ok=True)
        active = []
        for path in folder.glob('*.lock'):
            row = storage.read(path)
            if now - row['heartbeat'] > TTL:
                history = folder / 'history'; history.mkdir(exist_ok=True)
                path.replace(history / (path.name + '.' + uuid.uuid4().hex + '.expired'))
            else: active.append(row)
        state=storage.read(Path(root)/'attachments/state.json',{})
        policy=state.get('worker_pool_policy',dict(max_workers=allowed_workers))
        limit=effective_worker_limit(policy,now)
        if len(active) >= limit: raise ValueError('Worker quota reached')
        for row in active:
            if row['worker'] == worker or row['task'] == task or any(overlaps(a, b) for a in scopes for b in row['scopes']):
                raise ValueError('Task, worker or write scope is occupied')
        row = dict(task=task, worker=worker, scopes=scopes, started=now, heartbeat=now, token=uuid.uuid4().hex)
        if eta:row['estimated_completion']=eta
        with (folder / (task + '.lock')).open('x', encoding='utf-8') as f:
            json.dump(row, f, ensure_ascii=False); f.flush(); os.fsync(f.fileno())
        try:
            lifecycle._worker_transition(root,'claim',row,status='进行中（'+worker+'）')
        except Exception:
            history=folder/'history';history.mkdir(exist_ok=True)
            (folder/(task+'.lock')).replace(history/(task+'.'+uuid.uuid4().hex+'.unpublished'))
            raise
        return row

def update(root, task, token, release=False, now=None, status='待验收'):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', task): raise ValueError('Task identifier')
    with storage.locked(root):
        path = Path(root) / 'attachments/locks' / (task + '.lock')
        row = storage.read(path)
        if not row or row['token'] != token: raise ValueError('Claim token required')
        now = time.time() if now is None else now
        if now - row['heartbeat'] > TTL: raise ValueError('Claim expired; reclaim before continuing')
        if release:
            if not isinstance(status,str) or not status.strip() or any(c in status for c in '\r\n|'):
                raise ValueError('Use one worker status cell')
            row.update(heartbeat=now,released=now)
            lifecycle._worker_transition(root,'release',row,status=status)
            history = path.parent / 'history'; history.mkdir(exist_ok=True)
            path.replace(history / (path.name + '.' + uuid.uuid4().hex + '.released'))
        else:
            row['heartbeat'] = now
            lifecycle._worker_transition(root,'heartbeat',row)
            storage.write(path, row)
        return row

def append_shared(root,relative,text):
    with storage.locked(root):
        path=storage.relative_file(root,relative);old=path.read_bytes() if path.exists() else b''
        data=text.encode('utf-8') if isinstance(text,str) else text
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            history=path.parent/'history';history.mkdir(exist_ok=True)
            (history/(path.name+'.'+str(time.time_ns())+'.before')).write_bytes(old)
        with path.open('ab') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())

def update_board(root,task,status):
    """Compatibility helper; lifecycle owns the shared board write."""
    with storage.locked(root):
        return lifecycle._worker_transition(root,'status',{'task':task},status=status)
