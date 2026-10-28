"""Separate owner/assistant conversations for the trusted local project workflow.

The loopback browser is always owner. Assistants use the explicit local CLI;
an HTTP header or request body never selects an assistant identity.
"""
import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from . import storage

PEERS = ('GPT', 'Claude')
PAGE_SIZE = 100


def authorize(actor, peer):
    if peer not in PEERS:
        raise ValueError('Choose GPT or Claude')
    if actor not in ('owner', peer):
        raise PermissionError('Choose your own private conversation')


def directory(root):
    from .app import contained
    return contained(Path(root), 'attachments/private')


def ledger(root, peer):
    authorize('owner', peer)
    from .app import contained
    return contained(directory(root), 'owner-' + peer + '.jsonl')


def records(path):
    """Only complete append-framed records are visible, including during a read."""
    raw = path.read_bytes() if path.exists() else b''
    end = raw.rfind(b'\n') + 1
    return [json.loads(line) for line in raw[:end].splitlines() if line.strip()]


def public(row):
    return {key: row[key] for key in ('id', 'author', 'peer', 'body', 'created_at', 'images')}


def history(root, actor, peer, before=None):
    authorize(actor, peer)
    rows = records(ledger(root, peer))
    if before is not None:
        at = next((i for i, row in enumerate(rows) if row['id'] == before), None)
        if at is None:
            raise ValueError('Choose a history cursor from this conversation')
        rows = rows[:at]
    items = [public(row) for row in rows[-PAGE_SIZE:]]
    return dict(items=items, has_more=len(rows) > PAGE_SIZE,
                revision=hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest())


def publish(root, actor, peer, payload):
    authorize(actor, peer)
    if not isinstance(payload, dict) or set(payload) - {'body', 'client_id', 'images'}:
        raise ValueError('Choose the private conversation message format')
    body, client, images = payload.get('body'), payload.get('client_id'), payload.get('images', [])
    if not isinstance(images, list) or len(images) > 6:
        raise ValueError('Up to six images')
    if not isinstance(body, str) or len(body) > 6000 or (not body.strip() and not images):
        raise ValueError('Provide text or an image within 6000 characters')
    if not isinstance(client, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', client):
        raise ValueError('Choose a valid message identifier')
    digest = hashlib.sha256(json.dumps(dict(body=body.strip(), images=images), sort_keys=True).encode()).hexdigest()
    from .app import contained, decode_image
    with storage.locked(root):
        path = ledger(root, peer)
        if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b'\n'):
            raise ValueError('Restore the incomplete conversation record before appending')
        prior = next((row for row in records(path)
                      if row['author'] == actor and row['client_id'] == client), None)
        if prior:
            if prior['request_digest'] != digest:
                raise ValueError('Retry content must match')
            return public(prior)
        # Decode the whole request before writing any image or record.
        decoded = [decode_image(value) for value in images]
        names = []
        for image in decoded:
            name = uuid.uuid4().hex + '.png'
            target = contained(directory(root), 'images/' + peer + '/' + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                image.save(stream, 'PNG')
            names.append(name)
        row = dict(id=uuid.uuid4().hex, author=actor, peer=peer, body=body.strip(),
                   created_at=datetime.now().astimezone().isoformat(), images=names,
                   client_id=client, request_digest=digest)
        storage.append(path, row)
        return public(row)


def image(root, actor, peer, name):
    authorize(actor, peer)
    if not isinstance(name, str) or not re.fullmatch(r'[a-f0-9]{32}\.png', name):
        raise FileNotFoundError('Choose a conversation image')
    if not any(name in row['images'] for row in records(ledger(root, peer))):
        raise FileNotFoundError('Choose an image from this conversation')
    from .app import contained
    path = contained(directory(root), 'images/' + peer + '/' + name)
    if not path.is_file():
        raise FileNotFoundError('Choose an existing conversation image')
    return path


def dispatch(handler, root, route, query):
    if route not in ('/api/private', '/api/private/image'):
        return False
    # Match the existing single-user browser contract on reads as well as writes.
    if handler.headers.get('X-Board-Identity') not in (None, 'owner'):
        handler.respond(403, dict(error='Browser identity is the project owner'))
        return True
    allowed = {'peer', 'name'} if route.endswith('/image') else {'peer', 'before'}
    if set(query) - allowed or any(len(value) != 1 for value in query.values()):
        raise ValueError('Choose valid conversation parameters')
    peer = query.get('peer', [None])[0]
    authorize('owner', peer)
    if route.endswith('/image'):
        if handler.command not in ('GET', 'HEAD'):
            handler.respond(405, dict(error='Use the image viewer'))
        else:
            try:
                path = image(root, 'owner', peer, query.get('name', [None])[0])
            except FileNotFoundError:
                handler.respond(404, dict(error='Choose an image from this conversation'))
            else:
                handler.respond(200, path.read_bytes(), 'image/png')
    elif handler.command == 'POST':
        if 'before' in query:
            raise ValueError('Use the current conversation to send')
        handler.respond(201, dict(post=publish(root, 'owner', peer, handler.body(68 * 1024**2))))
    else:
        handler.respond(200, history(root, 'owner', peer, query.get('before', [None])[0]))
    return True
