"""Portable assistant stability checks, using only project-local runtime data."""
from datetime import datetime
from pathlib import Path
import math
import os
import re
import shutil
import uuid

from . import storage
from .lifecycle import ROLES, data_file, moment

DEFAULTS = dict(lead_reply_hours=2.5, executor_reply_minutes=45,
                collaboration_reply_hours=2.5, disk_min_free_gib=20, mood_max_age_hours=12)


def settings(root):
    config = storage.read(data_file(root, 'project.json'), {}).get('stability', {})
    if not isinstance(config, dict):
        raise ValueError('project.json stability must be an object')
    result = dict(DEFAULTS)
    for key in DEFAULTS:
        value = config.get(key, DEFAULTS[key])
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('stability.' + key + ' requires a positive finite number')
        result[key] = value
    return result


def disk_roots():
    if os.name == 'nt':
        if hasattr(os, 'listdrives'):
            return os.listdrives()
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return [chr(65+i) + ':/' for i in range(26) if mask & (1 << i)]
    paths = ['/']
    mounts = Path('/proc/self/mounts')
    if mounts.is_file():
        for line in mounts.read_text().splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0].startswith('/dev/'):
                paths.append(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), fields[1]))
    volumes = Path('/Volumes')
    if volumes.is_dir():
        paths.extend(str(p) for p in volumes.iterdir() if p.is_dir())
    # A filesystem mounted at several paths represents the same capacity.
    result, devices = [], set()
    for path in paths:
        try:
            device = os.stat(path).st_dev
        except OSError:
            continue
        if device not in devices:
            devices.add(device)
            result.append(path)
    return result


def disk_summary():
    rows = []
    for path in disk_roots():
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            continue
        rows.append(dict(path=str(path), free_gib=usage.free / 2**30, total_gib=usage.total / 2**30))
    return rows


def daily_greeting(root, who, *, now=None):
    """The executor's first status of the local day posts one retry-safe greeting."""
    if who != 'GPT':
        return None
    root = Path(root).resolve()
    at = (moment(now) or datetime.now().astimezone()).astimezone()
    key = f'executor-greeting-{at:%Y-%m-%d}'
    path = data_file(root, 'attachments/discussion/web-main.jsonl')
    data_file(root, '.write.lock')
    with storage.locked(root):
        previous = next((r for r in storage.lines(path) if r.get('client_id') == key and r.get('author') == who), None)
        if previous:
            return previous
        row = dict(id=uuid.uuid4().hex, author=who, body='Claude，早安。今天继续推进约定的工作。',
                   parent_id=None, client_id=key, images=[], files=[], channel='main',
                   created_at=at.isoformat(timespec='seconds'))
        storage.append(path, row)
        return row


def mood_names(root, who):
    if who not in ROLES:
        raise ValueError('Choose Claude or GPT')
    names = set()
    art = Path(__file__).resolve().parent / 'art'
    prefix = who.lower() + '-'
    for path in art.glob(prefix + '*'):
        if path.suffix in {'.png', '.svg'} and path.is_file():
            names.add(path.stem[len(prefix):])
    folder = data_file(root, 'attachments/generated/' + who)
    for path in folder.glob('*'):
        if path.suffix in {'.png', '.svg'} and path.stem != 'avatar' and re.fullmatch(r'[a-z][a-z0-9-]*', path.stem):
            if data_file(root, path.relative_to(root)).is_file() and path.stat().st_size:
                names.add(path.stem)
    return sorted(names)


def set_mood(root, who, mood, note='', *, now=None):
    root = Path(root).resolve()
    names = mood_names(root, who)
    if mood not in names:
        from . import expressions
        try:
            expressions.resolve(who, mood)
        except ValueError:
            raise ValueError('Choose an existing ' + who + ' expression: ' + ', '.join(names) + ', expression:NAME') from None
    if not isinstance(note, str) or len(note) > 200 or any(c in note for c in '\r\n'):
        raise ValueError('Use a single-line mood note within 200 characters')
    at = moment(now) or datetime.now().astimezone()
    value = dict(mood=mood, note=note.strip(), at=at.isoformat(timespec='seconds'))
    for name in ('.write.lock', 'overview.json', 'history'):
        data_file(root, name)
    def update(overview):
        overview[who.lower() + '_mood'] = value
    storage.update_json(root, 'overview.json', update)
    return value


def issues(root, at, overview, *, owner=None):
    from . import project, exchange
    from .message_controls import reaction_state
    result = []
    def add(who, code, what, fix):
        if owner is None or owner == who:
            result.append(dict(owner=who, task='-', code=code, what=what, fix=fix))
    try:
        config = settings(root)
    except ValueError as error:
        add('GPT', 'stability_config', str(error), 'Set positive stability thresholds in project.json')
        config = DEFAULTS
    limits = {'Claude': config['lead_reply_hours'] * 3600, 'GPT': config['executor_reply_minutes'] * 60}
    # Resolve every read within the existing project boundary before loading it.
    for relative in ('attachments/discussion/web-main.jsonl', 'attachments/discussion/web-study.jsonl',
                     'attachments/discussion/web-library.jsonl', 'attachments/discussion/message-tombstones.jsonl'):
        data_file(root, relative)
    room = [r for r in project.all_posts(root) if not r.get('deleted') and r.get('channel', 'main') != 'library']
    reacted = {(actor, mid) for mid, actor, _ in reaction_state(storage.lines(data_file(root, 'attachments/discussion/reactions.jsonl')))}
    replied = {(r.get('author'), r.get('parent_id')) for r in room
               if r.get('parent_id') and moment(r.get('created_at')) and moment(r['created_at']) <= at}
    for row in room:
        stamp = moment(row.get('created_at'))
        if stamp is None or stamp > at:
            continue
        age, mid = (at - stamp).total_seconds(), row['id']
        if row.get('author') == 'owner':
            mention = re.match(r'^\s*@(Claude|GPT)(?=$|[^A-Za-z0-9_])', row.get('body') or '')
            targets = (mention[1],) if mention else ROLES
            for who in targets:
                if age > limits[who] and (who, mid) not in reacted and (who, mid) not in replied:
                    add(who, 'owner_reply_overdue', f'Owner discussion message {mid} awaits {who}', 'Reply with say --reply or react')
        if (row.get('author') == 'GPT' and str(row.get('client_id', '')).startswith('executor-greeting-')
                and stamp.astimezone().date() == at.astimezone().date() and age > limits['Claude']
                and ('Claude', mid) not in reacted and ('Claude', mid) not in replied):
            add('Claude', 'greeting_reply_overdue', f'Executor daily greeting {mid} awaits a reply', 'Reply with say --reply or react')
    created = moment(storage.read(data_file(root, 'project.json'), {}).get('created_at'))
    for who in ROLES:
        # An assistant's status reads only its own private conversation.
        if owner is not None and owner != who:
            continue
        path = data_file(root, 'attachments/private/owner-' + who + '.jsonl')
        from .private_notes import records
        rows = [r for r in records(path) if moment(r.get('created_at')) and moment(r['created_at']) <= at]
        last_reply = max((i for i, r in enumerate(rows) if r.get('author') == who), default=-1)
        waiting = [r for r in rows[last_reply+1:] if r.get('author') == 'owner']
        if waiting:
            oldest = min(moment(r['created_at']) for r in waiting)
            if (at - oldest).total_seconds() > limits[who]:
                add(who, 'private_reply_overdue', 'Owner private message awaits ' + who, 'Read dm and answer with dm --reply')
        mood = overview.get(who.lower() + '_mood', {})
        registered = moment(mood.get('at')) or created
        if registered and (at - registered).total_seconds() > config['mood_max_age_hours'] * 3600:
            add(who, 'mood_stale', f"{who} mood registration is over {config['mood_max_age_hours']:g} hours old", 'Use mood to refresh an existing expression')
    for row in exchange.open_questions(root, now=at).values():
        if (at - row['at']).total_seconds() > config['collaboration_reply_hours'] * 3600:
            add('Claude', 'exchange_reply_overdue', 'Executor question awaits a lead answer: ' + row['title'], 'Answer with note in the daily exchange')
    for disk in disk_summary():
        if disk['free_gib'] < config['disk_min_free_gib']:
            add('GPT', 'disk_low', f"Local disk {disk['path']} has {disk['free_gib']:.1f} GiB free",
                'Review disposable task files within the authorized scope; ask the lead about owner data')
    return result
