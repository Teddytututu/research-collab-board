"""One entry point for assistants: every board action as a command with JSON output.

    python scripts/agent.py --as GPT status
    python scripts/agent.py --as GPT task progress T002 --status "12/60 · 约 23:00"
    python scripts/agent.py commands

Each command prints one JSON object: {"ok": true|false, "command": ..., "result": ..., "error": ...}.
The wrapped scripts keep their own validation; this file only normalises identity, data directory and output.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board import exchange, lifecycle, stability, storage  # noqa: E402

AGENTS = ['Claude', 'GPT']
CATEGORIES = ['研究', '学习', '事务', '界面与设计', '项目', '其他']
TASK_ACTIONS = ['new', 'start', 'progress', 'block', 'queue', 'deliver', 'accept', 'reject', 'stop']
TASK_FIELDS = ['title', 'when', 'node', 'status', 'wait', 'evidence', 'summary', 'node_summary', 'reason']

COMMANDS = {
    'status': 'Everything that needs me now: my flow issues, tasks, patrols, unread owner messages, pending events',
    'task': 'Move a task through its lifecycle: ' + ' / '.join(TASK_ACTIONS),
    'check': 'Flow issues assigned to me',
    'patrol': 'Record that I patrolled, with a one-line note and the next interval',
    'say': 'Post a short message to the shared discussion (writing rules apply)',
    'react': 'Add or remove a reaction on a discussion message',
    'dm': 'Read my private conversation with the owner, or reply with --reply',
    'counter': 'Update an experiment counter shown on the board',
    'file': 'Add a report/file card (add) or move one to the processed area (archive)',
    'todo': 'Add an owner to-do sticky note (add) or mark one done (done)',
    'events': 'List pending night-watch events, or acknowledge one with --ack',
    'ask': 'Ask the other assistant in the daily exchange: at least two --option values, optional --lean',
    'note': 'Append a note or answer to the daily exchange with a standard heading',
    'mood': 'Register my mood using an expression already available for my role',
    'commands': 'List these commands',
}


def emit(ok, command, result=None, error=None):
    print(json.dumps(dict(ok=ok, command=command, result=result, error=error), ensure_ascii=False, indent=1))
    return 0 if ok else 1


def run_script(name, argv):
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    done = subprocess.run([sys.executable, str(ROOT / 'scripts' / name), *argv], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding='utf-8', errors='replace')
    out, err = done.stdout.strip(), done.stderr.strip()
    try:
        out = json.loads(out) if out[:1] in '[{' else out
    except ValueError:
        pass
    return done.returncode == 0, out, err or (None if done.returncode == 0 else 'exit code %d' % done.returncode)


def overview_update(data, transform):
    return storage.update_json(data, 'overview.json', transform)


def cmd_status(a):
    data = a.data_dir
    stability.daily_greeting(data, a.who)
    board_file = lifecycle.data_file(data, 'board.md')
    rows = lifecycle.parse_board(board_file.read_text('utf-8-sig')) if board_file.is_file() else []
    tasks = [dict(task=r['task'], title=r['title'], status=r['status'], state=lifecycle.state_of(r['status'])) for r in rows]
    overview = storage.read(lifecycle.data_file(data, 'overview.json'), {})
    events = storage.read(lifecycle.data_file(data, 'attachments/night-watch/events.json'), {'events': []}).get('events', [])
    unread = None
    try:
        from board import private_notes
        items = private_notes.history(data, a.who, a.who)['items']
        last_mine = max((i for i, row in enumerate(items) if row['author'] == a.who), default=-1)
        unread = [dict(id=row['id'], at=row['created_at'], body=row['body'][:200]) for row in items[last_mine + 1:] if row['author'] != a.who]
    except Exception:  # private chat is optional in a project
        unread = None
    return {'as': a.who, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'my_issues': lifecycle.check(data, owner=a.who), 'tasks': tasks,
            'patrols': overview.get('patrols'), 'unread_owner_messages': unread,
            'pending_events': [dict(id=e.get('id'), type=e.get('type'), task=e.get('task')) for e in events],
            'local_disk': stability.disk_summary()}


def cmd_file(a):
    if a.op == 'add':
        if not (a.title and a.path):
            raise ValueError('file add needs --title and --path')
        if a.cat not in CATEGORIES:
            raise ValueError('--cat must be one of: ' + ', '.join(CATEGORIES))
        def add(value):
            links = value.setdefault('links', [])
            if any(link.get('title') == a.title for link in links):
                raise ValueError('A card with this title already exists')
            links.insert(0, dict(title=a.title, path=a.path, cat=a.cat, archived=False))
        overview_update(a.data_dir, add)
        return dict(added=a.title, cat=a.cat)
    def archive(value):
        found = [link for link in value.get('links', []) if link.get('title') == a.title]
        if len(found) != 1:
            raise ValueError('Exactly one card must have this title (found %d)' % len(found))
        found[0]['archived'] = True
    overview_update(a.data_dir, archive)
    return dict(archived=a.title)


def cmd_todo(a):
    if a.op == 'add':
        if not a.what:
            raise ValueError('todo add needs --what')
        def add(value):
            value.setdefault('todo', []).append({k: v for k, v in dict(what=a.what, when=a.when, how=a.how, note=a.note).items() if v})
        overview_update(a.data_dir, add)
        return dict(added=a.what)
    def done(value):
        items = value.get('todo', [])
        found = [item for item in items if item.get('what') == a.what]
        if len(found) != 1:
            raise ValueError('Exactly one to-do must have this text (found %d)' % len(found))
        items.remove(found[0])
        value.setdefault('todo_done', []).append(dict(found[0], done_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), by=a.who))
    overview_update(a.data_dir, done)
    return dict(done=a.what)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--as', dest='who', choices=AGENTS, help='Which assistant is acting (required except for commands)')
    p.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    # --as and --data-dir are accepted before or after the command name.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--as', dest='who', choices=AGENTS, default=argparse.SUPPRESS)
    common.add_argument('--data-dir', type=Path, default=argparse.SUPPRESS)
    sub = p.add_subparsers(dest='command', required=True)
    add = lambda name: sub.add_parser(name, parents=[common])
    add('status'); add('check'); add('commands')
    t = add('task'); t.add_argument('action', choices=TASK_ACTIONS); t.add_argument('task')
    for field in TASK_FIELDS:
        t.add_argument('--' + field.replace('_', '-'))
    pt = add('patrol'); pt.add_argument('note'); pt.add_argument('--every', type=int, default=120)
    s = add('say'); s.add_argument('text'); s.add_argument('--reply'); s.add_argument('--image', action='append', default=[])
    r = add('react'); r.add_argument('message_id'); r.add_argument('emoji'); r.add_argument('--remove', action='store_true')
    d = add('dm'); d.add_argument('--reply', metavar='TEXT')
    c = add('counter'); c.add_argument('run'); c.add_argument('done', type=int); c.add_argument('total', type=int)
    f = add('file'); f.add_argument('op', choices=['add', 'archive']); f.add_argument('--title', required=True)
    f.add_argument('--path'); f.add_argument('--cat', default='研究')
    td = add('todo'); td.add_argument('op', choices=['add', 'done']); td.add_argument('--what', required=True)
    td.add_argument('--when'); td.add_argument('--how'); td.add_argument('--note')
    e = add('events'); e.add_argument('--ack', action='append', default=[])
    for command in ('ask', 'note'):
        q = add(command); q.add_argument('title'); q.add_argument('body')
        if command == 'ask':
            q.add_argument('--option', action='append', default=[]); q.add_argument('--lean')
    m = add('mood'); m.add_argument('mood'); m.add_argument('note', nargs='?', default='')
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    name = a.command + (' ' + getattr(a, 'action', '') if a.command == 'task' else '') + (' ' + a.op if a.command in ('file', 'todo') else '')
    if a.command == 'commands':
        return emit(True, name, COMMANDS)
    if not a.who:
        return emit(False, name, error='--as Claude|GPT is required')
    a.data_dir = Path(a.data_dir).resolve()  # board helpers walk up to the data root, so it must be absolute
    data = str(a.data_dir)
    try:
        if a.command == 'status':
            return emit(True, name, cmd_status(a))
        if a.command == 'check':
            return emit(True, name, lifecycle.check(a.data_dir, owner=a.who))
        if a.command in ('ask', 'note'):
            return emit(True, name, exchange.write(a.data_dir, a.who, a.title, a.body,
                        ask=a.command == 'ask', options=getattr(a, 'option', None), lean=getattr(a, 'lean', None)))
        if a.command == 'mood':
            return emit(True, name, stability.set_mood(a.data_dir, a.who, a.mood, a.note))
        if a.command == 'file':
            return emit(True, name, cmd_file(a))
        if a.command == 'todo':
            return emit(True, name, cmd_todo(a))
        if a.command == 'events' and not a.ack:
            events = storage.read(lifecycle.data_file(a.data_dir, 'attachments/night-watch/events.json'), {'events': []})
            return emit(True, name, events.get('events', []))
    except ValueError as error:
        return emit(False, name, error=str(error))
    if a.command == 'task':
        argv2 = [a.action, a.task, '--by', a.who, '--data-dir', data]
        for field in TASK_FIELDS:
            value = getattr(a, field)
            if value:
                argv2 += ['--' + field.replace('_', '-'), value]
        ok, out, err = run_script('task_flow.py', argv2)
    elif a.command == 'patrol':
        ok, out, err = run_script('patrol_log.py', [a.who, a.note, '--every', str(a.every), '--data-dir', data])
    elif a.command == 'say':
        argv2 = [a.who, a.text, '--root', data] + (['--reply', a.reply] if a.reply else [])
        for image in a.image:
            argv2 += ['--image', image]
        ok, out, err = run_script('post_message.py', argv2)
    elif a.command == 'react':
        ok, out, err = run_script('react.py', [a.who, a.message_id, a.emoji, '--root', data] + (['--remove'] if a.remove else []))
    elif a.command == 'dm':
        argv2 = ['--data-dir', data, '--actor', a.who, '--peer', a.who] + (['--body', a.reply] if a.reply else [])
        ok, out, err = run_script('private_chat.py', argv2)
    elif a.command == 'counter':
        ok, out, err = run_script('update_state.py', ['--run', a.run, '--done', str(a.done), '--total', str(a.total), '--root', data])
    else:  # events --ack: acknowledge only, without running a patrol
        import importlib.util
        spec = importlib.util.spec_from_file_location('night_watch', ROOT / 'scripts' / 'night_watch.py')
        watch = importlib.util.module_from_spec(spec); spec.loader.exec_module(watch)
        try:
            watch.acknowledge(ROOT, a.ack, data_dir=os.path.relpath(a.data_dir, ROOT))
            ok, out, err = True, dict(acknowledged=a.ack), None
        except (ValueError, OSError) as error:
            ok, out, err = False, None, str(error)
    return emit(ok, name, out, err)


if __name__ == '__main__':
    sys.exit(main())
