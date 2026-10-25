"""One ordinary local patrol: progress, ETA and deduplicated actionable events."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import json
import math
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board import storage
from board.environment import use_project_environment
from scripts.run_queue import atomic_json, project_path

TERMINAL = {'complete', 'completed', 'done', 'accepted_complete', 'cancelled', 'delivered'}
INACTIVE = TERMINAL | {'paused', 'waiting', 'awaiting_anomaly_repair', 'queued'}


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def paths(root, data_dir):
    data = project_path(root, data_dir)
    relative = data.relative_to(root)
    project_path(root, relative / '.write.lock')
    project_path(root, relative / 'attachments/history')
    return {name: project_path(root, relative / suffix) for name, suffix in {
        'data': '.', 'state': 'attachments/state.json', 'config': 'attachments/night-watch.json',
        'events': 'attachments/night-watch/events.json', 'cache': 'attachments/night-watch/checkpoint.json',
    }.items()}


def acknowledge(project_root, identifiers, *, data_dir='data'):
    p = paths(Path(project_root).resolve(), data_dir)
    with storage.locked(p['data']):
        queue = storage.read(p['events'], {'events': []})
        queue['events'] = [e for e in queue['events'] if e['id'] not in set(identifiers)]
        atomic_json(p['events'], queue)


def patrol(project_root=ROOT, *, data_dir='data', now=None):
    root = Path(project_root).resolve()
    at = time.time() if now is None else now
    p = paths(root, data_dir)
    config = storage.read(p['config'], {})
    progress_files = config.get('progress_files', {})
    # Validate configured paths first, including each filesystem observation.
    for relative in progress_files.values():
        project_path(root, relative)
    for disk in config.get('disks', []):
        project_path(root, disk.get('path', '.'))
    stall = config.get('stall_seconds', 3600)
    if not number(stall) or stall <= 0:
        raise ValueError('Positive stall_seconds required')
    with storage.locked(p['data']):
        state = storage.read(p['state'], {})
        before = copy.deepcopy(state)
        cache = storage.read(p['cache'], {'tracking': {}, 'active': []})
        old_tracking = cache.get('tracking', {})
        tracking = {}
        conditions = {}

        def event(kind, task, generation='', **detail):
            signature = json.dumps([kind, task, generation], ensure_ascii=False, sort_keys=True)
            identifier = hashlib.sha256(signature.encode('utf-8')).hexdigest()[:24]
            conditions[identifier] = dict(id=identifier, type=kind, task=task, at=at, **detail)

        rows = {}
        for section in ('runs', 'tasks'):
            for key, row in state.get(section, {}).items():
                if isinstance(row, dict):
                    rows.setdefault(key, {}).update(row)
        for key in progress_files:
            rows.setdefault(key, {})
        for task, original in rows.items():
            row = dict(original)
            relative = progress_files.get(task, row.get('progress_file'))
            if relative:
                path = project_path(root, relative)
                try:
                    observed = storage.read(path)
                    if not isinstance(observed, dict):
                        raise ValueError('Progress object required: ' + str(relative))
                    row.update(observed)
                    if 'active' not in observed:
                        row.pop('active', None)
                except (OSError, ValueError, UnicodeError) as error:
                    event('observation_error', task, str(relative), file=str(relative), reason=str(error))
                    if task in old_tracking:
                        tracking[task] = old_tracking[task]
                    continue
            done = row.get('done', row.get('completed', 0))
            total = row.get('total', row.get('total_cases', 0))
            if not all(number(n) and n >= 0 and int(n) == n for n in (done, total)) or done > total:
                event('observation_error', task, 'counts', reason='Counts require 0 <= done <= total')
                continue
            done, total = int(done), int(total)
            if total == 0:
                continue
            status = str(row.get('state', row.get('status', 'running'))).lower()
            paused = status.startswith(('paused', 'failed', 'waiting')) or status in INACTIVE or row.get('active') is False
            old = old_tracking.get(task, {})
            changed = old.get('done') != done or old.get('total') != total or old.get('phase') != row.get('phase')
            resumed = old.get('paused', False) and not paused
            advanced = at if changed or resumed else old.get('advanced_at', at)
            samples = [] if old.get('total') != total or old.get('phase') != row.get('phase') or resumed else list(old.get('samples', []))
            if changed or not samples:
                samples.append({'at': at, 'done': done})
            samples = samples[-120:]
            remaining = row.get('estimated_seconds_remaining')
            if remaining is None:
                recent = [sample for sample in samples if sample['at'] >= at - 3600]
                window = recent if len(recent) >= 2 and recent[-1]['at'] - recent[0]['at'] >= 1800 else samples
                if len(window) >= 2:
                    elapsed = window[-1]['at'] - window[0]['at']
                    gain = window[-1]['done'] - window[0]['done']
                    if elapsed > 0 and gain > 0:
                        remaining = (total - done) * elapsed / gain
            if remaining is not None and (not number(remaining) or remaining < 0):
                event('observation_error', task, 'eta', reason='ETA requires nonnegative finite seconds')
                remaining = None
            estimate = None
            if done < total and not paused and row.get('process_alive') is not False and remaining is not None:
                # Anchor the forecast to a real observation, keeping quiet polls stable.
                anchor = row.get('updated_at', row.get('last_item_time'))
                if not number(anchor):
                    anchor = advanced
                estimate = {'at': anchor + remaining, 'remaining_seconds': remaining,
                            'confidence': 'medium', 'basis': 'project progress throughput'}
            tracking[task] = dict(done=done, total=total, phase=row.get('phase'), advanced_at=advanced,
                                  paused=paused, samples=samples)
            if done == total:
                event('task_complete', task, [row.get('phase'), total], done=done, total=total)
            elif status not in TERMINAL:
                if row.get('process_alive') is False:
                    event('process_exit', task, row.get('process_generation', ''), done=done, total=total)
                if paused:
                    event('task_paused', task, [done, status, row.get('reason')], done=done, total=total, reason=row.get('reason', status))
                elif at - advanced >= stall and not row.get('waiting_dependency'):
                    event('progress_stalled', task, [done, total, row.get('phase')], done=done, total=total)
            text = f'{done}/{total}'
            timed = text + ' · ' + datetime.fromtimestamp(estimate['at']).strftime('%H:%M') if estimate else text
            text = timed if len(timed) <= 14 else text
            source_at = row.get('updated_at', row.get('last_item_time'))
            if not number(source_at):
                source_at = advanced
            for section in ('runs', 'tasks'):
                if task in state.get(section, {}):
                    target = state[section][task]
                    target.update(done=done, total=total, progress_text=text)
                    if section == 'runs':
                        target.update(active=not paused and done < total and row.get('process_alive') is not False,
                                      source_at=source_at)
                    if relative:
                        target.update(state=status)
                    if section == 'tasks':
                        target.update(completed=done, total_cases=total)
                    # Only the watcher's own previous estimate is replaced or cleared.
                    if estimate is not None:
                        target['eta'] = dict(estimate, source='night_watch')
                    elif isinstance(target.get('eta'), dict) and target['eta'].get('source') == 'night_watch':
                        target['eta'] = {}
            if relative and task not in state.get('runs', {}) and task not in state.get('tasks', {}):
                state.setdefault('runs', {})[task] = dict(done=done, total=total, state=status, progress_text=text,
                                                         active=not paused and done < total and row.get('process_alive') is not False, source_at=source_at,
                                                         eta=dict(estimate, source='night_watch') if estimate else {})
            # The existing board ETA reader accepts per-run fallback forecasts here.
            manual = state.get('eta_tracking', {}).get('manual', {})
            entry = manual.get(task)
            if estimate is not None and (entry is None or entry.get('source') == 'night_watch'):
                state.setdefault('eta_tracking', {}).setdefault('manual', {})[task] = dict(
                    estimate, at=datetime.fromtimestamp(estimate['at'], timezone.utc).isoformat(),
                    source='night_watch', mode='estimate')
            elif estimate is None and isinstance(entry, dict) and entry.get('source') == 'night_watch':
                del manual[task]
        resources = state.get('resources', {})
        available, queued = resources.get('available_slots', 0), resources.get('queued', 0)
        if number(available) and number(queued) and available > 0 and queued > 0:
            event('available_slot_and_queue', 'queue', available_slots=available, queued=queued)
        for disk in config.get('disks', []):
            relative = disk.get('path', '.')
            floor = disk.get('floor_bytes', 20 * 1024 ** 3)
            if not number(floor) or floor < 0:
                raise ValueError('Nonnegative disk floor_bytes required')
            try:
                free = shutil.disk_usage(project_path(root, relative)).free
                if free < floor:
                    event('capacity_below_floor', str(relative), floor, free=free, floor=floor)
            except OSError as error:
                event('observation_error', str(relative), 'disk', reason=str(error))
        previous = set(cache.get('active', []))
        fresh = [event for key, event in conditions.items() if key not in previous]
        queue = storage.read(p['events'], {'events': []})
        # Completion stays pending until acknowledged. Condition events clear on recovery.
        pending = {e['id']: e for e in queue['events'] if e['type'] == 'task_complete' or e['id'] in conditions}
        for entry in fresh:
            pending.setdefault(entry['id'], entry)
        if pending or p['events'].exists():
            atomic_json(p['events'], {'events': list(pending.values())})
        if state != before:
            storage.write(p['state'], state)
        atomic_json(p['cache'], dict(tracking=tracking, active=sorted(conditions)))
        return fresh


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--data-dir', default='data', help='Project-relative data directory')
    parser.add_argument('--ack', action='append', default=[], metavar='EVENT_ID')
    args = parser.parse_args(argv)
    if args.ack:
        acknowledge(args.project_root, args.ack, data_dir=args.data_dir)
        return 0
    events = patrol(args.project_root, data_dir=args.data_dir)
    if events:
        print(json.dumps({'events': events}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    use_project_environment(__file__)
    raise SystemExit(main())
