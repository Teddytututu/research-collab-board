"""Actionable lifecycle wake conditions; observations only, with stable event keys."""
import re

from .lifecycle import check, data_file, moment, parse_board, state_of, COUNTS

HEAD = re.compile(r'^### (\d{4}-\d\d-\d\d[T ][^·\n]+?)\s*·\s*(GPT|Claude)\s*→\s*(GPT|Claude)(?:\s*·\s*(T\d+))?\s*$', re.M)
ASK = re.compile(r'please (?:decide|confirm|approve)|decision requested|请定|请明确|请确认|请批', re.I)


def open_questions(root):
    folder = data_file(root, 'exchange')
    paths = sorted(folder.glob('????-??-??.md'))
    main = data_file(root, 'exchange.md')
    if main.exists():
        paths.append(main)
    entries = {}
    for path in paths:
        text = data_file(root, path.relative_to(root)).read_text('utf-8-sig')
        heads = list(HEAD.finditer(text))
        for index, head in enumerate(heads):
            at = moment(head[1])
            if at:
                body = text[head.end():heads[index + 1].start() if index + 1 < len(heads) else len(text)]
                entries[(at.timestamp(), head[2], head[4] or 'exchange')] = body
    pending = {}
    for (at, author, task), body in sorted(entries.items()):
        if author == 'GPT' and ASK.search(body):
            # Follow-ups retain the original question deadline.
            pending.setdefault(task, at)
        elif author == 'Claude':
            pending.pop(task, None)
    return pending


def conditions(root, state, at):
    board = data_file(root, 'board.md')
    if not board.exists():
        return []
    rows = parse_board(board.read_text('utf-8-sig'))
    unfinished = []
    for row in rows:
        kind = state_of(row['status'])
        count = COUNTS.match(row['status'])
        if kind == 'queued' or kind == 'running' and count and int(count[1]) < int(count[2]):
            unfinished.append(row['task'])
    out = []
    resources = state.get('resources', {})
    allocation = state.get('allocation', resources.get('allocation', {}))
    cap = allocation.get('effective_cap', 0)
    if type(cap) is int and cap > 0:
        used = set(allocation.get('actual_cards', [])) | set(allocation.get('loading_cards', [])) | set(allocation.get('reserved_cards', []))
        free = cap - len(used)
    else:
        free = resources.get('available_slots', 0)
    if type(free) is int and free > 0 and unfinished:
        tasks = sorted(set(unfinished))
        out.append(dict(type='idle_cards_unfinished_work', task='resources', generation=[tasks, free],
                        tasks=tasks, available_slots=free,
                        action='Start eligible queued work within the existing resource cap'))
    for task, asked in open_questions(root).items():
        if at - asked >= 1800:
            out.append(dict(type='question_unanswered_30min', task=task, generation=asked, asked=asked,
                            action='Apply the recorded recommendation for reversible authorized work within the resource cap; approvals for sending, payments and deletion remain with the user'))
    for issue in check(root, now=at, owner='GPT'):
        out.append(dict(type='flow_issue', task=issue['task'], generation=issue['code'],
                        what=issue['what'], action=issue['fix']))
    return out
