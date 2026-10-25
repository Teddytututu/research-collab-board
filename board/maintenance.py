"""Reserve unique task numbers, compact accepted rows and retain daily exchange bytes."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,re,time,uuid
from . import storage

def reserve(root,owner='GPT',title=''):
    root=Path(root)
    with storage.locked(root):
        folder=root/'attachments/locks/task-numbers';folder.mkdir(parents=True,exist_ok=True);numbers=[]
        for p in (root/'tasks').glob('T*.md'):
            match=re.match(r'T(\d+)',p.name)
            if match:numbers.append(int(match[1]))
        for p in [root/'board.md',root/'tasks/archive.md']:
            if p.exists():numbers.extend(int(n) for n in re.findall(rb'\bT(\d+)\b',p.read_bytes()))
        numbers.extend(int(p.stem[1:]) for p in folder.glob('T*.json'))
        task='T'+str(max(numbers,default=0)+1).zfill(3)
        with (folder/(task+'.json')).open('x',encoding='utf-8') as f:
            json.dump(dict(task=task,owner=owner,title=title,reserved_at=datetime.now().astimezone().isoformat()),f,ensure_ascii=False)
        return task

def compact_board(root):
    root=Path(root)
    with storage.locked(root):
        path=root/'board.md';before=path.read_bytes();archive=root/'tasks/archive.md'
        old=archive.read_bytes() if archive.exists() else b'';rows=[];moved=[];added=[]
        for line in before.splitlines(keepends=True):
            cells=line.decode('utf-8-sig').split('|')
            closed=len(cells)>=5 and re.fullmatch(r'T\d+|TASK-\d+',cells[1].strip()) and cells[3].strip().startswith(('通过','已通过','取消','已取消','归档','accepted','cancelled','archived'))
            if closed:
                moved.append(cells[1].strip())
                if line.strip() not in old:added.append(line);old+=line
            else:rows.append(line)
        if added:
            prior=archive.read_bytes() if archive.exists() else b''
            storage.write_bytes(archive,prior+(b'\n' if prior and not prior.endswith(b'\n') else b'')+b''.join(added))
        storage.write_bytes(path,b''.join(rows))
        return dict(moved=moved,before_lines=len(before.splitlines()),after_lines=len(rows))

def blocks(raw):
    starts=[];offset=0;fenced=False
    for line in raw.splitlines(keepends=True):
        if line.lstrip().startswith(b'```'):fenced=not fenced
        match=re.match(rb'^### (\d{4}-\d{2}-\d{2})[ T]',line)
        if match and not fenced:starts.append((offset,match[1].decode()))
        offset+=len(line)
    if not starts:return raw,[]
    return raw[:starts[0][0]],[(day,raw[start:starts[i+1][0] if i+1<len(starts) else len(raw)]) for i,(start,day) in enumerate(starts)]

def split_exchange(root,today=None):
    root=Path(root).resolve();today=today or datetime.now().strftime('%Y-%m-%d')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',today):raise ValueError('ISO calendar date required')
    with storage.locked(root):
        path=root/'exchange.md';folder=root/'exchange';folder.mkdir(exist_ok=True);target=folder/(today+'.md')
        if path.exists() and target.exists() and os.path.samefile(path,target):return dict(already_daily=True,active=target.relative_to(root).as_posix())
        raw=path.read_bytes() if path.exists() else b'';intro,entries=blocks(raw);groups={}
        for day,body in entries:groups.setdefault(day,[]).append(body)
        snapshot=folder/('history-'+hashlib.sha256(raw).hexdigest()+'.md')
        if snapshot.exists():assert snapshot.read_bytes()==raw
        else:snapshot.write_bytes(raw)
        for day,parts in groups.items():storage.write_bytes(folder/(day+'.md'),b''.join(parts))
        if intro:storage.write_bytes(folder/'preamble.md',intro)
        if not target.exists():storage.write_bytes(target,intro if not entries else ('# '+today+'\n\n').encode())
        history=path.parent/'history';history.mkdir(exist_ok=True)
        (history/(path.name+'.'+str(time.time_ns())+'.before')).write_bytes(raw)
        temp=path.with_name('.exchange-'+uuid.uuid4().hex+'.link');os.link(target,temp);os.replace(temp,path)
        assert os.path.samefile(path,target)
        return dict(already_daily=False,active=target.relative_to(root).as_posix(),source_archive=snapshot.relative_to(root).as_posix(),source_sha256=hashlib.sha256(raw).hexdigest())
