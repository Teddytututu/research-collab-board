"""File-backed task transitions, deadline checks and visible assistant patrols."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from . import storage

LEAD_ACTIONS = {'new', 'accept', 'reject', 'stop'}
ACTIONS = LEAD_ACTIONS | {'start', 'progress', 'block', 'deliver'}
ROLES = ('Claude', 'GPT')
TASK = re.compile(r'T\d+')
COUNTS = re.compile(r'^(\d+)\s*/\s*(\d+)(?:\s|$)')


def data_file(root, relative):
    path = storage.relative_file(root, relative)
    current = path
    while current != root:
        if getattr(current, 'is_junction', lambda: False)():
            raise ValueError('Project-local regular path required')
        current = current.parent
    return path


def moment(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.astimezone()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if isinstance(value, str):
        try:
            return moment(datetime.fromisoformat(value.strip().replace('Z', '+00:00')))
        except ValueError:
            pass
    return None


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '').replace('|', '／')).strip()


def state_of(status):
    text = str(status or '').strip()
    for state, pattern in [
        ('stopped', r'^(stopped|cancelled|已停|取消)'),
        ('accepted', r'^(accepted|通过|已完成|完成)'),
        ('delivered', r'^(delivered|已交|待验收)'),
        ('rejected', r'^(rejected|退回)'),
        ('blocked', r'^(blocked|卡住|受阻|失败)'),
        ('daily', r'^(daily|每日)'),
        ('queued', r'^(queued|排队|待领|条件满足就开工|暂停|等待|等)'),
    ]:
        if re.search(pattern, text, re.I):
            return state
    return 'running' if COUNTS.match(text) else 'unknown'


def parse_board(text):
    rows = []
    for index, line in enumerate(text.splitlines()):
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) >= 4 and TASK.fullmatch(cells[0]):
            rows.append(dict(task=cells[0], title=cells[1], status=cells[2], owner=cells[3],
                             updated_at=cells[4] if len(cells) > 4 else None, index=index, cells=cells))
    return rows


def nodes(overview):
    def walk(node):
        yield node
        for child in node.get('children') or []:
            yield from walk(child)
    for node in overview.get('tree') or []:
        yield from walk(node)


def task_spec(root, task):
    folder = data_file(root, 'tasks')
    found = sorted(folder.glob(task + '-*.md'))
    if len(found) != 1:
        raise ValueError('Provide exactly one tasks/' + task + '-short-name.md specification')
    return data_file(root, found[0].relative_to(root))


# Forecasts use the same fixed Taipei clock as the board UI.
TAIPEI = timezone(timedelta(hours=8))
DECLARED_ETA = re.compile(r'约\s*(明天|\d\d-\d\d)?\s*(\d{1,2}):(\d\d)')


def declared_eta(status, updated):
    match = DECLARED_ETA.search(status)
    if not match or updated is None:
        return None
    base = updated.astimezone(TAIPEI)
    day = base.date()
    try:
        if match[1] == '明天':
            day += timedelta(days=1)
        elif match[1]:
            day = day.replace(month=int(match[1][:2]), day=int(match[1][3:]))
        result = datetime(day.year, day.month, day.day, int(match[2]), int(match[3]), tzinfo=TAIPEI)
    except ValueError:
        return None
    return result + timedelta(days=1) if not match[1] and result < base else result


def estimate_progress(root, task, status, at):
    """Estimate from the current counter's last twelve hours of recorded progress."""
    current = COUNTS.match(status)
    if not current:
        return None
    done, total = map(int, current.groups())
    if done >= total:
        return None
    samples = []
    for record in storage.lines(data_file(root, 'attachments/task-flow.jsonl')):
        if record.get('task') != task or record.get('action') not in {'start', 'progress'}:
            continue
        stamp = moment(record.get('at'))
        count = COUNTS.match(str(record.get('status', '')))
        if not stamp or not count or int(count[2]) != total or not 0 <= (at-stamp).total_seconds() <= 12*3600:
            continue
        completed = int(count[1])
        if not 0 <= completed <= total:
            continue
        if samples and completed < samples[-1][1]:
            samples = []  # Counter reset starts a new phase.
        samples.append((stamp, completed))
    if not samples or samples[-1][1] > done or samples[0][1] >= done:
        return None
    start, previous = samples[0]
    elapsed = (at-start).total_seconds()
    remaining = (total-done)*elapsed/(done-previous)
    return at+timedelta(seconds=remaining) if elapsed > 0 and 0 < remaining <= 7*86400 else None


def with_progress_eta(root, task, status, at):
    if '约' in status:
        return status
    estimate = estimate_progress(root, task, status, at)
    if estimate is None:
        return status
    local, current = estimate.astimezone(TAIPEI), at.astimezone(TAIPEI)
    days = (local.date()-current.date()).days
    day = '' if days == 0 else '明天 ' if days == 1 else local.strftime('%m-%d ')
    return re.sub(r'估不了[:：]\s*', '', status) + ' · 约 ' + day + local.strftime('%H:%M')


def transition(root, action, task, *, by, now=None, **fields):
    root = Path(root).resolve()
    if by not in ROLES or action not in ACTIONS or not TASK.fullmatch(task):
        raise ValueError('Valid action, assistant role and T-number required')
    if action in LEAD_ACTIONS and by != 'Claude':
        raise ValueError(action + ' requires the research lead (Claude)')
    required = {'new': ('title', 'when'), 'start': ('status',), 'progress': ('status',),
                'block': ('wait',), 'deliver': ('evidence',), 'accept': ('summary',),
                'reject': ('reason',), 'stop': ('reason',)}[action]
    for name in required:
        if not clean(fields.get(name)):
            raise ValueError(action + ' requires --' + name)
    if action in {'start', 'progress'}:
        match = COUNTS.match(clean(fields['status']))
        if not match or not 0 <= int(match[1]) <= int(match[2]) or int(match[2]) == 0:
            raise ValueError('Running status requires 0 <= X <= N and N > 0: X/N')
    if action == 'start' and '约' not in fields['status'] and '估不了' not in fields['status']:
        raise ValueError('Start requires an ETA: X/N · 约 HH:MM, or X/N · 估不了：specific reason')
    if action == 'block' and not re.match(r'^(waiting for\s+\S|等\s*\S)', clean(fields['wait']), re.I):
        raise ValueError('Use --wait "waiting for WHO to DO WHAT"')
    if action == 'deliver' and not data_file(root, fields['evidence']).is_file():
        raise ValueError('Evidence requires an existing project-relative file')
    at = moment(now) or datetime.now().astimezone()
    stamp = at.isoformat(timespec='seconds')
    # Resolve every output before the first write, including lock and history paths.
    paths = {key: data_file(root, value) for key, value in {
        'board': 'board.md', 'archive': 'tasks/archive.md', 'overview': 'overview.json',
        'state': 'attachments/state.json', 'log': 'attachments/task-flow.jsonl',
        'lock': '.write.lock', 'history': 'history', 'task_history': 'tasks/history',
        'attachment_history': 'attachments/history',
    }.items()}
    with storage.locked(root):
        text = paths['board'].read_text('utf-8-sig')
        rows = parse_board(text)
        matches = [row for row in rows if row['task'] == task]
        archive = paths['archive'].read_text('utf-8-sig') if paths['archive'].exists() else '# Task archive\n\n| ID | Task | Status | Owner | Updated |\n| --- | --- | --- | --- | --- |\n'
        archived = {row['task'] for row in parse_board(archive)}
        if len(matches) > 1 or task in archived or (action == 'new') == bool(matches):
            raise ValueError('Task must be unique and active; new requires an unused ID')
        spec = task_spec(root, task)
        spec_text = spec.read_text('utf-8-sig')
        row = matches[0] if matches else None
        current = state_of(row['status']) if row else None
        allowed = {'new': {None}, 'start': {'queued', 'blocked', 'rejected', 'unknown'}, 'progress': {'running'},
                   'block': {'queued', 'running', 'blocked', 'rejected'},
                   'deliver': {'running', 'blocked', 'rejected'}, 'accept': {'delivered'},
                   'reject': {'delivered'}, 'stop': {'queued', 'running', 'blocked', 'rejected', 'delivered', 'daily', 'unknown'}}
        if current not in allowed[action]:
            raise ValueError('Transition ' + str(current) + ' -> ' + action + ' requires a valid lifecycle state')
        overview = storage.read(paths['overview'], {})
        tree = list(nodes(overview))
        attached = [n for n in tree if n.get('title') == fields.get('node')]
        if action == 'new' and fields.get('node') and len(attached) != 1:
            raise ValueError('--node requires one existing result-tree title')
        state = storage.read(paths['state'], {'tasks': {}, 'runs': {}})
        status = {'new': lambda: 'queued: ' + clean(fields['when']),
                  'start': lambda: clean(fields['status']), 'progress': lambda: clean(fields['status']),
                  'block': lambda: 'blocked: ' + clean(fields['wait']), 'deliver': lambda: 'delivered · awaiting review',
                  'accept': lambda: 'accepted: ' + clean(fields['summary']),
                  'reject': lambda: 'rejected: ' + clean(fields['reason']), 'stop': lambda: 'stopped: ' + clean(fields['reason'])}[action]()
        if action in {'start', 'progress'}:
            status = with_progress_eta(root, task, status, at)
        cells = list(row['cells']) if row else [task, '[' + clean(fields['title']) + '](tasks/' + spec.name + ')', '', 'GPT']
        cells[2] = status
        if len(cells) < 5:
            cells.append(stamp)
        else:
            cells[4] = stamp
        rendered = '| ' + ' | '.join(cells) + ' |'
        lines = text.splitlines()
        if row:
            if action in {'accept', 'stop'}:
                del lines[row['index']]
                archive = archive.rstrip('\n') + '\n' + rendered + '\n'
                archived.add(task)
            else:
                lines[row['index']] = rendered
        else:
            if not any(re.match(r'^\|\s*:?-+', line) for line in lines):
                lines += ['', '| ID | Task | Status | Owner | Updated |', '| --- | --- | --- | --- | --- |']
            lines.append(rendered)
        if action == 'new':
            for node in attached:
                node.setdefault('tasks', []).append(task)
        changed = []
        for node in tree:
            if task in (node.get('tasks') or []) and action in {'start', 'accept', 'stop'}:
                if fields.get('node_summary'):
                    node['summary'] = clean(fields['node_summary'])
                node['status'] = 'done' if all(t in archived for t in node['tasks']) else 'doing'
                changed.append(node.get('title'))
        if action in {'accept', 'stop'}:
            overview['runs'] = [r for r in overview.get('runs', []) if task not in (r.get('id'), r.get('task_id'))]
            for section in ('tasks', 'runs'):
                state.setdefault(section, {}).pop(task, None)
                for key, value in list(state[section].items()):
                    if isinstance(value, dict) and value.get('task_id') == task:
                        del state[section][key]
        else:
            state.setdefault('tasks', {}).setdefault(task, {}).update(status=status, owner=cells[3], updated_at=stamp, lifecycle_managed=True)
        record = dict(at=stamp, task=task, action=action, by=by, status=status,
                      evidence=fields.get('evidence'), tree_nodes=changed)
        if '## Transition history' not in spec_text:
            spec_text = spec_text.rstrip() + '\n\n## Transition history\n'
        spec_text = spec_text.rstrip() + '\n- ' + stamp + ' · ' + by + ' · ' + action + ' · ' + status + ((' · ' + fields['evidence']) if action == 'deliver' else '') + '\n'
        storage.write_bytes(paths['board'], ('\n'.join(lines) + '\n').encode())
        if action in {'accept', 'stop'}:
            storage.write_bytes(paths['archive'], archive.encode())
        storage.write(paths['overview'], overview)
        storage.write(paths['state'], state)
        storage.write_bytes(spec, spec_text.encode())
        storage.append(paths['log'], record)
        return record


def check(root, *, now=None, owner=None):
    root = Path(root).resolve()
    at = moment(now) or datetime.now().astimezone()
    def read_text(relative):
        path = data_file(root, relative)
        return path.read_text('utf-8-sig') if path.exists() else ''
    rows = parse_board(read_text('board.md'))
    archived_rows = parse_board(read_text('tasks/archive.md'))
    archived = {r['task'] for r in archived_rows}
    overview = storage.read(data_file(root, 'overview.json'), {})
    state = storage.read(data_file(root, 'attachments/state.json'), {})
    issues = []
    def add(who, task, code, what, fix):
        issues.append(dict(owner=who, task=task, code=code, what=what, fix=fix))
    seen = set()
    for row in rows:
        task, status = row['task'], state_of(row['status'])
        if task in seen or task in archived:
            add('Claude', task, 'duplicate_task', 'Task ID occurs more than once', 'Review board and archive history')
        seen.add(task)
        if status in {'accepted', 'stopped'}:
            add('Claude', task, 'closed_on_board', 'Closed task remains active', 'Archive with task_flow.py')
        elif status == 'unknown':
            add('GPT', task, 'status_format', 'Task status requires the lifecycle format', 'Use task_flow.py')
        try:
            task_spec(root, task)
        except ValueError:
            add('GPT', task, 'task_spec', 'Task requires one specification', 'Write tasks/' + task + '-short-name.md')
        updated = moment(row['updated_at']) or moment(state.get('tasks', {}).get(task, {}).get('updated_at'))
        if updated is None:
            add('GPT', task, 'missing_update', 'Task requires an update time', 'Record the current transition')
            continue
        if status == 'running':
            count = COUNTS.match(row['status'])
            if int(count[1]) >= int(count[2]):
                add('GPT', task, 'counter_complete', 'Running phase counter is complete', 'Deliver evidence or start the next phase counter')
            elif '约' not in row['status'] and '估不了' not in row['status']:
                add('GPT', task, 'eta_missing', 'Running phase requires an ETA', 'Progress with 约 HH:MM or 估不了：specific reason')
            forecast = declared_eta(row['status'], updated)
            if '约' in row['status'] and forecast is None:
                add('GPT', task, 'eta_invalid', 'Declared ETA requires a valid clock and date', 'Correct the progress ETA')
            elif forecast and at > forecast + timedelta(minutes=30):
                add('GPT', task, 'eta_overdue', 'Declared ETA passed thirty minutes ago', 'Update progress and ETA or record the dependency')
        age = (at - updated).total_seconds() / 3600
        limit = {'delivered': 2, 'blocked': 2, 'rejected': 2, 'running': 3}.get(status)
        until = re.search(r'(?:until|到)\s*(\d{2})-(\d{2})', row['status'], re.I)
        defer = False
        if until:
            try:
                defer = at < at.replace(month=int(until[1]), day=int(until[2]), hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                add('GPT', task, 'invalid_wait_date', 'Wait date requires a valid MM-DD', 'Correct the block condition')
        if limit and age > limit and not (status == 'blocked' and defer):
            who = 'Claude' if status in {'delivered', 'blocked'} else 'GPT'
            code = {'delivered': 'review_overdue', 'blocked': 'blocked_overdue', 'running': 'running_stale', 'rejected': 'rework_overdue'}[status]
            add(who, task, code, f'{status}: {age:.1f} hours since update',
                'Review or decide the next action' if who == 'Claude' else 'Update progress or redeliver with evidence')
    if not any(state_of(r['status']) == 'queued' for r in rows):
        add('Claude', '-', 'empty_queue', 'Execution queue is empty', 'Queue resource work and a task that uses no compute slot')
    for node in nodes(overview):
        tasks = node.get('tasks') or []
        if tasks and ((all(t in archived for t in tasks) and node.get('status') != 'done') or
                      (any(t in seen for t in tasks) and node.get('status') == 'done')):
            add('Claude', ','.join(tasks), 'tree_mismatch', 'Result tree disagrees with task board: ' + str(node.get('title')), 'Review node status and summary')
        for task in tasks:
            if task not in seen and task not in archived:
                add('Claude', task, 'tree_missing_task', 'Result tree references a missing task', 'Register task or restore its archive record')
    findings = read_text('findings.md')
    research_tasks = {t for n in nodes(overview) for t in n.get('tasks') or []}
    for row in archived_rows:
        closed = moment(row['updated_at'])
        if row['task'] in research_tasks and closed and timedelta(0) <= at - closed < timedelta(days=2) and row['task'] not in findings:
            add('Claude', row['task'], 'findings_missing', 'Closed research task requires a findings entry', 'Record conclusion, key counts and limits in findings.md')
    for who in ROLES:
        patrol = overview.get('patrols', {}).get(who, {})
        last = moment(patrol.get('at'))
        due = moment(patrol.get('next_at'))
        if due is None and last:
            due = last + timedelta(minutes=120 if who == 'Claude' else 45)
        if due is None or at > due + timedelta(minutes=15):
            add(who, '-', 'patrol_overdue', who + ' patrol is due', 'Inspect assigned events and run patrol_log.py')
        if who == 'Claude' and last and at - last > timedelta(hours=3.5):
            add('GPT', '-', 'lead_patrol_overdue', 'Research-lead patrol is overdue', 'Record the decision and recommendation in the exchange; continue authorized work')
    return [i for i in issues if owner is None or i['owner'] == owner]


def fix_tree(root, *, by):
    """Lead-requested mechanical repair: all archived tasks imply a done node."""
    if by != 'Claude':
        raise ValueError('Tree repair requires the research lead (Claude)')
    root = Path(root).resolve()
    for name in ('.write.lock', 'history', 'overview.json', 'tasks/archive.md'):
        data_file(root, name)
    with storage.locked(root):
        path = root / 'tasks/archive.md'
        archived = {r['task'] for r in parse_board(path.read_text('utf-8-sig'))} if path.exists() else set()
        board = data_file(root, 'board.md')
        live = {r['task'] for r in parse_board(board.read_text('utf-8-sig'))} if board.exists() else set()
        overview = storage.read(root / 'overview.json', {})
        changed = []
        for node in nodes(overview):
            tasks = node.get('tasks') or []
            if tasks and all(t in archived and t not in live for t in tasks) and node.get('status') != 'done':
                node['status'] = 'done'
                changed.append(node.get('title'))
        if changed:
            storage.write(root / 'overview.json', overview)
        return changed


def log_patrol(root, who, note, *, every=120, now=None):
    root = Path(root).resolve()
    if who not in ROLES or type(every) is not int or every <= 0 or not clean(note):
        raise ValueError('Assistant, note and positive interval in minutes required')
    at = moment(now) or datetime.now().astimezone()
    for path in ('.write.lock', 'history', 'attachments/history', 'attachments/patrol-log.jsonl', 'overview.json'):
        data_file(root, path)
    with storage.locked(root):
        issues = check(root, now=at)
        mine = [i for i in issues if i['owner'] == who and i['code'] != 'patrol_overdue']
        record = dict(at=at.isoformat(timespec='seconds'), who=who, note=clean(note)[:80],
                      next_at=(at + timedelta(minutes=every)).isoformat(timespec='seconds'),
                      every_min=every, open_issues=len(mine))
        overview = storage.read(root / 'overview.json', {})
        overview.setdefault('patrols', {})[who] = record
        overview['flow_issues'] = [i for i in issues if i['code'] != 'patrol_overdue' or i['owner'] != who]
        storage.write(root / 'overview.json', overview)
        storage.append(root / 'attachments/patrol-log.jsonl', record)
        return record
