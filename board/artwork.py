"""Deploy actual native PNG outputs without rewriting or redrawing their pixels."""
from pathlib import Path
import hashlib
from . import storage
from .onboarding import NAMES, pillow_image

def deploy(root,role,ids):
    root=Path(root)
    if role not in ['GPT','Claude'] or len(ids)!=7 or len(set(ids))!=7:raise ValueError('Choose one role and its seven distinct native job IDs')
    Image=pillow_image()
    ledger=storage.read(root/'attachments/provider-images.json',{})
    validated=[]
    for name,job in zip(NAMES,ids):
        record=ledger.get(job,{})
        if record.get('status')!='completed' or not record.get('saved_path'):raise ValueError('A completed native image with a saved path is required')
        source=Path(record['saved_path'])
        with Image.open(source) as image:
            alpha=image.getchannel('A').getextrema() if 'A' in image.getbands() else (255,255)
            if image.format!='PNG' or min(image.size)<256 or alpha[0]>=255 or alpha[1]<=0:raise ValueError('Native output must contain a visible subject and transparent PNG alpha')
        raw=source.read_bytes();validated.append((name,job,record,raw))
    rows=[]
    with storage.locked(root):
        for name,job,record,raw in validated:
            target=root/'attachments/generated'/role/(name+'.png');storage.write_bytes(target,raw)
            row=dict(role=role,expression=name,native_job_id=job,creator='image_gen.imagegen',
                     prompt=record.get('revised_prompt'),source=record['saved_path'],file=str(target.relative_to(root)),
                     sha256=hashlib.sha256(raw).hexdigest(),format='PNG',usage_basis='Original native generation on the installation service quota')
            storage.append(root/'attachments/generated/artwork-record.jsonl',row);rows.append(row)
    return rows
