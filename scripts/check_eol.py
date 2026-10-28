"""Reject staged text files whose line-ending style differs from HEAD."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout


def style(raw):
    if b'\0' in raw:
        return None
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n') - crlf
    cr = raw.count(b'\r') - crlf
    return '+'.join(name for name, count in [('CRLF', crlf), ('LF', lf), ('CR', cr)] if count)


def changed_eols(repo):
    records = git(repo, 'diff', '--cached', '--raw', '-z', '--no-abbrev', '--find-renames',
                  '--diff-filter=ACMRT', '--no-ext-diff').split(b'\0')
    changes, index = [], 0
    while index < len(records) and records[index]:
        fields = records[index].split()
        path = records[index+1]
        index += 2
        if fields[4].startswith((b'R', b'C')):
            path = records[index]
            index += 1
        old_mode, new_mode, before, after, _ = fields
        if old_mode not in (b':100644', b':100755') or new_mode not in (b'100644', b'100755'):
            continue
        old = style(git(repo, 'cat-file', 'blob', before.decode('ascii')))
        new = style(git(repo, 'cat-file', 'blob', after.decode('ascii')))
        if old and new and old != new:
            changes.append(dict(path=path.decode('utf-8', errors='surrogateescape'), before=old, after=new))
    return changes


def check_eol(repo=ROOT):
    if not (Path(repo) / '.git').exists():
        print(json.dumps(dict(ok=True, changes=[], skipped='Source archive without Git metadata')))
        return 0
    try:
        changes = changed_eols(repo)
    except (OSError, ValueError) as error:
        print(json.dumps(dict(ok=False, changes=[], error=str(error)), ensure_ascii=True))
        return 1
    print(json.dumps(dict(ok=not changes, changes=changes), ensure_ascii=True))
    return 1 if changes else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    return check_eol(parser.parse_args(argv).repo)


if __name__ == '__main__':
    sys.exit(main())
