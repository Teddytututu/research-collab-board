"""Download the public emote list to ignored runtime data, with bounded failures."""
from pathlib import Path
from urllib.parse import urlsplit
import argparse, io, json, re, stat, sys, urllib.request, uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board.assets import emote_manifest
MAX_BYTES = 2*1024**2


def regular_path(path):
    """Keep links, junctions and other Windows reparse points out of write paths."""
    for current in (path, *path.parents):
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
            raise ValueError('A regular project-local emote path is required')


def data_path(root, path):
    regular_path(path)
    if not path.resolve().is_relative_to(root):
        raise ValueError('Emote paths must stay inside the selected data root')
    return path


def public_url(value):
    url = urlsplit(value)
    return (url.scheme == 'https' and url.hostname in {'i0.hdslb.com','i1.hdslb.com','i2.hdslb.com'}
            and url.port in (None,443) and not url.username and not url.password
            and not url.query and not url.fragment
            and re.fullmatch(r'/bfs/emote/[a-f0-9]{40}\.png', url.path))


def install(data, *, opener=urllib.request.urlopen, limit=None):
    from PIL import Image
    root = Path(data).absolute()
    regular_path(root)
    root = root.resolve()
    target = data_path(root, root/'emotes')
    target.mkdir(parents=True,exist_ok=True)
    data_path(root, target)
    report = dict(downloaded=0, reused=0, failed=0)
    for row in emote_manifest()[:limit]:
        if not re.fullmatch(r'[0-9]+\.png',row['file']) or not public_url(row['url']):
            raise ValueError('A public emote source and numeric file name are required')
        path = data_path(root, target/row['file'])
        temp = data_path(root, path.with_suffix('.partial'))
        if path.is_file() and path.stat().st_size:
            report['reused'] += 1
            continue
        if temp.exists():
            temp = data_path(root, path.with_name(path.name+'.'+uuid.uuid4().hex+'.partial'))
        created_temp = False
        try:
            with opener(row['url'],timeout=8) as response:
                if not public_url(response.geturl()):
                    raise ValueError('A public emote response is required')
                raw = response.read(MAX_BYTES+1)
            if not raw or len(raw)>MAX_BYTES:
                raise ValueError('Emote size limit')
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != 'PNG' or image.width>4096 or image.height>4096:
                    raise ValueError('A bounded PNG emote is required')
                image.verify()
            data_path(root, path)
            data_path(root, temp)
            with temp.open('xb') as stream:
                created_temp = True
                stream.write(raw)
            data_path(root, temp)
            data_path(root, path)
            temp.replace(path)
            created_temp = False
            report['downloaded'] += 1
        except (OSError,ValueError):
            report['failed'] += 1
            if report['failed']>=3:
                break
        finally:
            if created_temp:
                try:
                    data_path(root, temp).unlink(missing_ok=True)
                except (OSError, ValueError):
                    pass
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,default=ROOT/'data')
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    print(json.dumps(install(args.data,limit=args.limit)))
