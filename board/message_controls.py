"""Append-only withdrawal markers and a content-free public message projection."""
import copy
from datetime import datetime
from pathlib import Path
from . import storage


def marker_path(root):
    return Path(root) / 'attachments/discussion/message-tombstones.jsonl'


def project_rows(rows, markers):
    """Saved copies follow source withdrawal; ordinary replies retain their own text."""
    marks = {row['message_id']: row for row in markers}
    while True:
        size = len(marks)
        for row in rows:
            reference = row.get('reference') or row.get('source') or {}
            source = reference.get('message_id', reference.get('id')) if isinstance(reference, dict) else None
            copied = row.get('channel') in {'files', 'library'} or isinstance(row.get('source'), dict)
            if copied and row['id'] not in marks and source in marks:
                marks[row['id']] = marks[source]
        if len(marks) == size:
            break
    result = []
    for original in rows:
        row = copy.deepcopy(original)
        marker = marks.get(row['id'])
        row.update(deleted=bool(marker), deleted_by=marker['deleted_by'] if marker else None,
                   deleted_at=marker['deleted_at'] if marker else None,
                   delete_action=marker.get('delete_action', 'withdraw') if marker else 'withdraw')
        if marker:
            row.update(body='', images=[], files=[], reactions=[])
            allowed = {'id', 'author', 'parent_id', 'created_at', 'channel', 'deleted', 'deleted_by',
                       'deleted_at', 'delete_action', 'body', 'images', 'files', 'reactions'}
            row = {key: value for key, value in row.items() if key in allowed}
        reference = original.get('reference') or {}
        quoted = reference.get('message_id', reference.get('id')) if isinstance(reference, dict) else None
        if row.get('parent_id') in marks or quoted in marks:
            row.update(parent_deleted=True, reference_text='原消息已撤回')
            row.pop('reference', None)
        result.append(row)
    return result


def reaction_state(rows):
    """Unknown historical aggregate counts remain anonymous."""
    active = set()
    for row in rows:
        mid, emoji = row.get('message_id'), row.get('emoji')
        if not isinstance(mid, str) or not isinstance(emoji, str):
            continue
        actor = row.get('actor')
        if not isinstance(actor, str) or not actor:
            prefix = f'history:{mid}:{emoji}:'
            active = {key for key in active if not (key[0] == mid and key[2] == emoji and key[1].startswith(prefix))}
            count = row.get('count', 1) if row.get('active', True) else 0
            count = count if type(count) is int and 0 <= count <= 100000 else 0
            active.update((mid, prefix + str(i), emoji) for i in range(count))
        else:
            key = (mid, actor, emoji)
            if row.get('active', True): active.add(key)
            else: active.discard(key)
    return active


def delete_message(root, message_id, actor, *, assistant=False, channel=None):
    from . import project
    if assistant:
        if actor not in {'Claude', 'GPT'}:
            raise PermissionError('Assistant withdrawal requires its own CLI identity')
    elif actor != 'owner':
        raise PermissionError('Browser deletion uses the project owner')
    if not isinstance(message_id, str) or not message_id or len(message_id) > 80:
        raise ValueError('Choose a conversation message')
    if channel is not None: channel = project.channel_id(channel)
    with storage.locked(root):
        target = next((p for p in project.raw_posts(root) if p['id'] == message_id and
                       (channel is None or p.get('channel', 'main') == channel)), None)
        if target is None: raise ValueError('Choose a conversation message')
        if assistant and target['author'] != actor:
            raise PermissionError('Assistants withdraw only their own messages')
        previous = next((m for m in storage.lines(marker_path(root)) if m['message_id'] == message_id), None)
        if previous:
            return {k: previous[k] for k in ('message_id', 'deleted', 'deleted_by', 'deleted_at')}
        marker = dict(message_id=message_id, deleted=True, deleted_by=actor,
                      deleted_at=datetime.now().astimezone().isoformat(),
                      delete_action='withdraw' if target['author'] == actor else 'delete')
        storage.append(marker_path(root), marker)
        return {k: marker[k] for k in ('message_id', 'deleted', 'deleted_by', 'deleted_at')}
