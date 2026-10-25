"""Single-user adaptation of the address-book storage and reference boundary."""
from pathlib import Path
from . import project,storage

CHANNELS=project.CHANNELS

def channel(value='main'):
    return project.channel_id(value)

def directory(root):
    return Path(root)/'attachments/discussion'

def ledger(root,value='main'):
    return project.ledger(root,channel(value))

def file_directory(root):
    return directory(root)/'files'

def favorite(root,payload,actor='owner'):
    if actor!='owner' or not isinstance(payload,dict) or set(payload)!={'message_id','channel'}:
        raise ValueError('Choose a conversation message')
    return project.bookmark(root,channel(payload['channel']),payload['message_id'])

def download(root,identifier):
    import re
    if not isinstance(identifier,str) or not re.fullmatch(r'[a-f0-9]{32}\.[a-z0-9]+',identifier):
        raise ValueError('Choose a conversation file')
    item=next((f for p in project.all_posts(root) for f in p.get('files',[]) if f.get('id')==identifier),None)
    path=file_directory(root)/identifier
    if item is None or path.is_symlink() or not path.is_file():raise ValueError('Choose a conversation file')
    return item,path
