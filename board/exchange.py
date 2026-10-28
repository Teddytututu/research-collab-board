"""Daily assistant exchange entries with one machine-written heading format."""
from datetime import datetime
from pathlib import Path
import os
import re

from . import storage
from .lifecycle import ROLES, append_text, data_file, moment

HEAD = re.compile(r'^### (\d{4}-\d\d-\d\d[T ][^·\n]+?)\s*·\s*(GPT|Claude)\s*→\s*(GPT|Claude)(?:\s*·\s*(T\d+))?(?:\s*·\s*(.*))?\s*$')
ASK = re.compile(r'please (?:decide|confirm|approve)|decision requested|请定|请明确|请确认|请批', re.I)


def write(root, who, title, body, *, ask=False, options=None, lean=None, now=None):
    root = Path(root).resolve()
    if who not in ROLES:
        raise ValueError('Choose Claude or GPT')
    if not isinstance(title, str) or not title.strip() or any(c in title for c in '\r\n'):
        raise ValueError('Use a nonempty, single-line exchange title')
    if not isinstance(body, str) or not body.strip():
        raise ValueError('Provide an exchange body')
    options = list(options or [])
    if ask and (len(options) < 2 or any(not isinstance(o, str) or not o.strip() for o in options)):
        raise ValueError('ask requires at least two nonempty --option values')
    at = moment(now) or datetime.now().astimezone()
    other = 'GPT' if who == 'Claude' else 'Claude'
    heading = f'### {at.isoformat(timespec="microseconds")} · {who} → {other} · ' + ('问：' if ask else '答：') + title.strip()
    lines = ['', heading, body.strip()]
    lines += [f'{chr(65+i) if i < 26 else i+1}. {option.strip()}' for i, option in enumerate(options)]
    if lean and lean.strip():
        lines.append('我的倾向：' + lean.strip())
    path = data_file(root, f'exchange/{at:%Y-%m-%d}.md')
    for name in ('.write.lock', 'exchange/history'):
        data_file(root, name)
    with storage.locked(root):
        raw = path.read_bytes() if path.exists() else b''
        initial = b'' if raw else f'# {at:%Y-%m-%d} exchange\n'.encode()
        update = append_text(raw or initial, '\n'.join(lines) + '\n')
        path.parent.mkdir(parents=True, exist_ok=True)
        # Append under the shared lock so exchange.md's existing hard link stays live.
        with path.open('ab') as stream:
            stream.write(update[len(raw):]); stream.flush(); os.fsync(stream.fileno())
    return dict(file=path.relative_to(root).as_posix(), heading=heading)


def entries(root):
    """Read daily files and legacy exchange.md; deduplicate hard-linked entries."""
    root = Path(root).resolve()
    paths = sorted(data_file(root, 'exchange').glob('????-??-??.md'))
    main = data_file(root, 'exchange.md')
    if main.exists():
        paths.append(main)
    result, seen = [], set()
    for path in paths:
        text = data_file(root, path.relative_to(root)).read_text('utf-8-sig')
        current, body, fence = None, [], None
        def save():
            if current is None:
                return
            stamp = moment(current[1])
            if stamp is None:
                return
            value = dict(at=stamp, author=current[2], peer=current[3],
                         task=current[4] or 'exchange', title=current[5] or '', body='\n'.join(body))
            key = (stamp.timestamp(), value['author'], value['peer'], value['task'], value['title'], value['body'])
            if key not in seen:
                seen.add(key)
                result.append(value)
        for line in text.splitlines():
            marker = re.match(r'^\s*(`{3,}|~{3,})', line)
            if marker:
                if fence is None:
                    fence = marker[1]
                elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                    fence = None
                body.append(line)
                continue
            head = HEAD.fullmatch(line) if fence is None else None
            if head:
                save()
                current, body = head, []
            elif current:
                body.append(line)
        save()
    return sorted(result, key=lambda row: row['at'])


def open_questions(root, *, now=None):
    pending = {}
    for row in entries(root):
        if now is not None and row['at'] > moment(now):
            continue
        title = re.sub(r'^(?:问|答)：', '', row['title'], count=1).strip()
        key = row['task'] + ':' + title if title else row['task']
        if row['author'] == 'GPT' and row['peer'] == 'Claude' and (
                row['title'].startswith('问：') or ASK.search(row['body'])):
            pending.setdefault(key, row)
        elif row['author'] == 'Claude' and row['peer'] == 'GPT' and not row['title'].startswith('问：'):
            pending.pop(key, None)
    return pending
