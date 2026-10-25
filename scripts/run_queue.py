"""Finite, resumable local queues with complete-result and capacity protection."""
from pathlib import Path
from contextlib import suppress
import argparse
import errno
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board import storage
from board.environment import use_project_environment


def project_path(root, relative):
    """Accept project-relative paths and reject traversal, links and junctions."""
    root = Path(root).resolve()
    path = storage.relative_file(root, relative)
    current = path
    while current != root:
        if getattr(current, 'is_junction', lambda: False)():
            raise ValueError('Project-relative regular directory required')
        current = current.parent
    return path


def atomic_json(path, value):
    """Replace after fsync; retain original bytes on a failed write."""
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')
    path = Path(path)
    if path.is_file() and path.read_bytes() == raw:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        storage.replace_with_retry(temp, path)
    finally:
        with suppress(OSError):
            temp.unlink(missing_ok=True)


def fatal(error):
    resource_codes = {errno.ENOSPC, getattr(errno, 'EDQUOT', 122), errno.ENOMEM,
                      errno.EACCES, errno.EPERM, errno.EROFS, errno.EMFILE, errno.ENFILE}
    if isinstance(error, (AssertionError, MemoryError, PermissionError)):
        return True
    if isinstance(error, OSError) and error.errno in resource_codes:
        return True
    text = (type(error).__name__ + ' ' + str(error)).lower()
    return any(word in text for word in ('outofmemory', 'out of memory', 'capacity',
               'quota', 'source drift', 'frozen', 'immutable', 'sha mismatch', 'disk full'))


class QueuePaused(RuntimeError):
    """The consecutive ordinary-error limit was reached."""


def iterate_queue(rows, process, *, is_done, progress_path, anomalies_path,
                  record_result=None, maximum_consecutive_errors=5):
    """Adapter API: is_done must validate every final output for a whole item."""
    rows = list(rows)
    if maximum_consecutive_errors < 1 or maximum_consecutive_errors > 5:
        raise ValueError('Consecutive error limit must be between one and five')
    done = errors = consecutive = 0
    last_item_time = None

    def progress(state, **extra):
        atomic_json(progress_path, dict(state=state, done=done, total=len(rows), errors=errors,
                    consecutive_errors=consecutive, last_item_time=last_item_time,
                    updated_at=time.time(), pid=os.getpid(), **extra))

    try:
        complete = [bool(is_done(row)) for row in rows]
        done = sum(complete)
        progress('running')
        for row, finished in zip(rows, complete):
            if finished:
                consecutive = 0
                continue
            try:
                result = process(row)
                if record_result is not None:
                    record_result(row, result)
                if not is_done(row):
                    raise AssertionError('Handler completion requires every final output')
            except Exception as error:
                errors += 1
                consecutive += 1
                if fatal(error):
                    raise
                entry = dict(id=row['id'], error=repr(error), time=time.time(), consecutive=consecutive)
                storage.append(anomalies_path, entry)
                if consecutive >= maximum_consecutive_errors:
                    raise QueuePaused(f'{maximum_consecutive_errors} consecutive item failures; repair inputs and resume') from error
                progress('running', last_error=entry)
                continue
            done += 1
            consecutive = 0
            last_item_time = time.time()
            progress('running', last_id=row['id'])
            yield row, result
        progress('complete' if done == len(rows) else 'awaiting_anomaly_repair')
    except BaseException as error:
        # A full disk can also prevent recording the pause. Preserve the original cause.
        try:
            progress('paused', reason=repr(error))
        except OSError:
            pass
        raise


def fingerprint(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def result_directory_case_sensitive(directory):
    """Probe the nearest existing destination ancestor, including per-directory rules.

    The temporary filename is removed before work starts. Existing directories
    retain their own rules; new output directories inherit their ancestor's rules.
    """
    directory = Path(directory)
    while not directory.is_dir():
        if directory == directory.parent:
            raise ValueError('Existing result directory ancestor required')
        directory = directory.parent
    probe = directory / ('.queue-identity-' + uuid.uuid4().hex)
    descriptor = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(descriptor)
        try:
            return not os.path.samefile(probe, probe.with_name(probe.name.upper()))
        except FileNotFoundError:
            return True
    finally:
        probe.unlink()


def validate_result_paths(targets):
    """Reject aliases in a frozen queue before any result, lock or handler work."""
    by_folded_path = {}
    by_file_identity = {}

    def collision(first, second, path):
        raise ValueError(f'Frozen input result-path collision: IDs {first!r} and {second!r} '
                         f'address the same result file {str(path)!r}; choose distinct output IDs')

    for identifier, path in targets.items():
        # IDs are portable ASCII. Probe only potentially ambiguous case pairs,
        # preserving ordinary queues without extra filesystem writes.
        folded = str(path).casefold()
        prior = by_folded_path.get(folded)
        if prior is not None and not result_directory_case_sensitive(path.parent):
            collision(prior, identifier, path)
        by_folded_path[folded] = identifier
        try:
            info = path.stat()
        except FileNotFoundError:
            continue
        if not info.st_ino:
            continue
        identity = (info.st_dev, info.st_ino)
        prior = by_file_identity.get(identity)
        if prior is not None:
            collision(prior, identifier, path)
        by_file_identity[identity] = identifier


def prepare_queue(config, *, project_root=ROOT):
    root = Path(project_root).resolve()
    output = project_path(root, config['output'])
    items = config['items']
    identifiers = [row['id'] for row in items]
    if any(not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}', key)
           or key.endswith('.') or key.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
           *('COM' + str(i) for i in range(1, 10)), *('LPT' + str(i) for i in range(1, 10))} for key in identifiers):
        raise ValueError('Use portable plain item IDs')
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Frozen input collision: unique item IDs required')
    # Validate all write destinations before acquiring a lock or loading a handler.
    relative_output = output.relative_to(root)
    progress = project_path(root, relative_output / 'progress.json')
    anomalies = project_path(root, relative_output / 'anomalies.jsonl')
    lock = project_path(root, relative_output / '.queue-lock')
    project_path(root, relative_output / '.queue-lock/.write.lock')
    targets = {row['id']: project_path(root, relative_output / 'results' / (row['id'] + '.json')) for row in items}
    validate_result_paths(targets)
    return items, progress, anomalies, lock, targets


def run_queue(config, process, *, project_root=ROOT):
    items, progress, anomalies, lock, targets = prepare_queue(config, project_root=project_root)

    def is_done(row):
        try:
            value = storage.read(targets[row['id']])
        except (json.JSONDecodeError, UnicodeError):
            return False
        if not isinstance(value, dict) or value.get('complete') is not True or 'result' not in value:
            return False
        if value.get('id') != row['id'] or value.get('input_sha256') != fingerprint(row):
            raise AssertionError('Frozen input source drift for item ' + row['id'])
        return True

    def record(row, result):
        atomic_json(targets[row['id']], dict(id=row['id'], input_sha256=fingerprint(row), complete=True, result=result))

    with storage.locked(lock):
        # Stream execution without retaining a large batch of model outputs in RAM.
        for _ in iterate_queue(items, process, is_done=is_done, record_result=record,
                               progress_path=progress, anomalies_path=anomalies,
                               maximum_consecutive_errors=config.get('maximum_consecutive_errors', 5)):
            pass
    return storage.read(progress)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', help='Project-relative JSON configuration')
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    config = storage.read(project_path(root, args.config))
    handler = project_path(root, config['handler_file'])
    project_path(root, config['output'])
    if args.dry_run:
        print(json.dumps(dict(items=len(config['items']), handler=str(handler), output=config['output']), ensure_ascii=False))
        return 0
    prepare_queue(config, project_root=root)
    spec = importlib.util.spec_from_file_location('project_queue_handler', handler)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print(json.dumps(run_queue(config, getattr(module, config.get('handler', 'process')), project_root=root), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    use_project_environment(__file__)
    raise SystemExit(main())
