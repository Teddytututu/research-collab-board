"""Bundled character art and optional public emotes stored in project data."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def avatars():
    path=ROOT/'board/art/fanart.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def emote_manifest():
    path=ROOT/'assets/public-emotes.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []


def reaction_catalog(data):
    rows = []
    for row in emote_manifest():
        path = Path(data)/'emotes'/row['file']
        if path.is_file() and not path.is_symlink() and path.stat().st_size:
            rows.append(dict(key=row['key'], label=row['label'],
                             url='/room-reactions/'+row['file'], fallback=row['fallback']))
    return rows
