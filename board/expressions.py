"""Curated character expressions, separate from the original portrait assets."""
from pathlib import Path
from functools import lru_cache
import json
import re

DIRECTORY = Path(__file__).with_name('expressions')
ROLES = {'owner': 'owner', 'Claude': 'claude', 'GPT': 'gpt'}


@lru_cache(maxsize=1)
def catalog():
    path = DIRECTORY / 'catalog.json'
    return json.loads(path.read_text(encoding='utf-8'))['items'] if path.exists() else []


def resolve(who, value):
    role = ROLES.get(who)
    if role is None or not isinstance(value, str):
        raise ValueError('Choose your own character expression')
    rows = [row for row in catalog() if row['role'] == role]
    exact = next((r for r in rows if r['key'] == value), None)
    if exact:
        return exact
    explicit = value.startswith(('expression:', '表情:'))
    name = re.sub(r'^(?:expression|表情):', '', value)
    if value.startswith('expr:'):
        raise ValueError('Choose an expression belonging to ' + who)
    if not explicit:
        # Preserve old simple names while new expressions have an explicit prefix.
        for row in sorted(rows, key=lambda r: not r['file'].endswith('.webp')):
            if name in row.get('aliases', []):
                return row
    for row in rows:
        if (not explicit or row['collection'] == 'original-60') and name in (row['name'], row['label']):
            return row
    raise ValueError('Choose an existing ' + who + ' expression')


def snapshot(root):
    from . import storage
    value = storage.read(Path(root) / 'overview.json', {})
    return dict(items=catalog(), actors=ROLES,
                moods={role: value.get(who.lower() + '_mood', {}) for who, role in ROLES.items()})


def choose_owner(root, payload):
    from . import storage
    if not isinstance(payload, dict) or set(payload) != {'mood'}:
        raise ValueError('Choose your own mood using the expression picker')
    resolve('owner', payload['mood'])
    from datetime import datetime
    record = dict(mood=payload['mood'], note='', at=datetime.now().astimezone().isoformat(timespec='seconds'))
    storage.update_json(root, 'overview.json', lambda overview: overview.update(owner_mood=record))
    return record
