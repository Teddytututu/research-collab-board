# Project night watch and finite queues

The night watch is an ordinary Python script. It observes local JSON progress, updates project X/N and ETA, and records actionable events. Model invocation and event handling belong to the existing assistant session.

## Install and bootstrap integration

The stable installation CLI is:

```sh
python scripts/install_night_watch.py --project-root "/path/to/project" --install
```

Preview the complete installation plan with `--dry-run`. The installer uses the project interpreter in `.venv` when present; `--python` selects an explicit interpreter. `--data-dir data` selects the project-relative runtime directory.

Windows also has a PowerShell entry:

```powershell
pwsh -NoProfile -File scripts/install-night-watch.ps1 -ProjectRoot 'C:\projects\my-study' -Install
pwsh -NoProfile -File scripts/install-night-watch.ps1 -ProjectRoot 'C:\projects\my-study' -Install -DryRun
```

Windows registration uses `schtasks.exe /Create /TN ResearchNightWatch-<path-hash> /XML <project-local-xml> /F`. The XML specifies a ten-minute interval, hidden execution, the current interactive user, least privilege, and one active instance. PowerShell's encoded argument preserves spaces, Unicode, apostrophes and shell characters in project paths. XML also supports command lengths beyond the scheduler's `/TR` argument limit. Each resolved project path receives a separate task name. Registration replaces only that project's named entry.

The JSON result reports `installed`, `preview`, or `manual_registration`. Registration failure includes the actual error and a runnable `manual_command`; the installer returns success so bootstrap can finish independent setup. Configuration and path errors raise their precise error. Windows writes the task XML inside the selected project during installation; preview produces its plan on stdout.

Bootstrap can invoke the stable CLI once after initialization and show the returned JSON. The watch installation and the board's optional login startup have separate lifecycles.

The bootstrap helper `register_night_watch(python, data_root, dry_run=True)` forwards its data root as a project-relative `--data-dir`. The installer returns ASCII-escaped JSON, which stays compatible with bootstrap's UTF-8 decoding and legacy Windows console encodings. The PowerShell wrapper forwards the same value through `-DataDir`. Installation preview performs zero scheduler calls and zero runtime writes. Integration fixtures exercise the real bootstrap helper, real installer subprocess, PowerShell wrapper and hidden patrol action with spaces, Unicode and apostrophes in both project and data paths. Scheduler registration itself uses a mock.

On macOS and Linux the same installer prints a `prepare_command` and a ten-minute `manual_command`. Run the preparation command, then place the emitted cron line in `crontab -e`, for example:

```cron
*/10 * * * * /path/to/project/.venv/bin/python -B /path/to/project/scripts/night_watch.py --project-root /path/to/project --data-dir data >> /path/to/project/data/attachments/night-watch/patrol.log 2>&1
```

Cron uses the installation account and its filesystem access. Windows runs while the selected user is logged in. Both preserve the deployment's existing resource and security settings.

## Progress sources and events

Run one patrol manually:

```sh
python scripts/night_watch.py --project-root "/path/to/project"
```

The default source is `data/attachments/state.json`, with run/task maps keyed by task ID. Each observation uses `done` and `total`, with `completed` and `total_cases` accepted as aliases. A row may provide `progress_file`, `phase`, `state`, `process_alive`, `process_generation`, `waiting_dependency`, and `estimated_seconds_remaining`.

Optional configuration lives in `data/attachments/night-watch.json`:

```json
{
  "progress_files": {"T001": "work/batch/progress.json"},
  "stall_seconds": 3600,
  "disks": [{"path": ".", "floor_bytes": 21474836480}]
}
```

Paths are relative to the selected project root. The path boundary validates sources, destinations, symlinks and Windows junctions. Disk observations use only explicitly configured project paths. Hardware availability and process identity come from the deployment's existing observer: `process_alive: false` means an observed process exit; `resources: {"available_slots": 1, "queued": 2}` means an eligible slot and runnable queued work. This keeps protected devices and allocation rules with their existing controller.

The watcher updates `done`, `total`, `completed`, `total_cases`, `progress_text` and its own `eta` in the relevant state rows, retaining unrelated fields. Run rows also carry observed `source_at` and `active` for the existing ETA reader. `progress_text` uses `X/N · HH:MM` within fourteen characters and X/N alone for longer counts. ETA uses an explicit remaining duration or measured progress: a thirty-minute recent window takes precedence over historical samples. Forecasts stay anchored to the observation time. The watcher supplies its fallback forecast through `eta_tracking.manual` when that task's entry is available or already watcher-owned. Paused rows clear the watcher's ETA; operator-authored ETA entries retain their ownership. The board reads these state rows through its existing snapshot path.

Actionable event types are:

| Type | Condition |
| --- | --- |
| `task_complete` | Positive total reached |
| `progress_stalled` | Active X stays constant for the configured interval |
| `process_exit` | Observer reports a stopped process on unfinished work |
| `task_paused` | Queue reports paused, failed, waiting or anomaly repair |
| `available_slot_and_queue` | Eligible capacity and runnable queued work coexist |
| `capacity_below_floor` | Configured free-space protection line reached |
| `observation_error` | Configured progress or disk observation has an actionable error |

The assistant heartbeat first reads `data/attachments/night-watch/events.json`. An empty event list or an absent event file ends the heartbeat quietly. For an event, read its task and the latest relevant discussion, carry out the authorized response, then acknowledge its ID:

```sh
python scripts/night_watch.py --project-root "/path/to/project" --ack EVENT_ID
```

The watch writes stdout only for newly detected events. Each active condition has a stable ID. Acknowledgement removes the pending event and suppresses repeated wakeups while that condition persists. Recovery clears condition events automatically; recurrence creates another wakeup. Completion events stay pending until acknowledged. Checkpoint and event writes are atomic and occur only when bytes change. State updates use the project's shared storage lock and retain its original-byte history.

## Queue configuration

```json
{
  "handler_file": "work/handler.py",
  "handler": "process",
  "output": "work/batch",
  "items": [{"id": "sample-001", "value": 1}, {"id": "sample-002", "value": 2}]
}
```

An ordinary handler receives one row and returns a JSON-compatible result:

```python
def process(row):
    return {"value": row["value"] * 2}
```

```sh
python scripts/run_queue.py work/queue.json --project-root "/path/to/project" --dry-run
python scripts/run_queue.py work/queue.json --project-root "/path/to/project"
```

The handler is trusted project code and runs with the operator's existing permissions. The queue itself creates only project-local files. Dry-run reads configuration and reports paths and item count; handler loading belongs to the execution step.

Queue output uses the project-relative `output` field. Point `progress_files` in the selected data directory at that output's `progress.json`; the queue's output path and the watcher's `--data-dir` then share the same configured runtime tree.

Every successful item writes `results/<id>.json` containing `complete: true`, its item ID, frozen input digest, and result. A complete, matching record is skipped on restart. Partial or malformed records are retried. An existing complete result with changed input pauses with a frozen-input error. Portable unique IDs and contained output paths are validated before execution.

The handler finishes all required routes before returning its final result. Existing multi-output handlers can use `iterate_queue(rows, process, is_done=..., record_result=..., progress_path=..., anomalies_path=...)`; `is_done` validates the complete group of final outputs. Execute adapter calls under the deployment's existing single-owner lock, as the file-backed `run_queue` wrapper does.

Each ordinary item exception appends to `anomalies.jsonl` and continues to the next row. Five consecutive exceptions pause immediately. Success resets the consecutive count. Memory, capacity, quota, permissions, read-only storage, frozen-input assertions and source-drift errors pause immediately and propagate the original exception. `ENOSPC` also propagates if the disk prevents writing the pause record. Atomic replacement retains the previous complete file on write failure.

`progress.json` records `done`, `total`, current-run `errors`, `consecutive_errors`, `last_item_time`, `updated_at`, `pid`, and execution state. A finite pass ends in `complete` or `awaiting_anomaly_repair`. Repair the input or resource condition and rerun the same command: completed matching items remain skipped and remaining items resume. Queue progress, events and checkpoints use lightweight atomic replacement; anomaly history is append-only. Full audits and hashes of final artifacts belong to the batch completion step.

## Focused verification

```sh
python -B -m unittest discover -s tests -p 'test_v023_night_watch*.py' -v
```

Fixtures live under `work/`. Installation tests mock the scheduler and exercise preview, failure recovery, XML construction, project naming and quoting. Queue fixtures cover completion skipping, partial-result retry, frozen input, ENOSPC, anomaly isolation and five-error pause. Watch fixtures cover quiet polls, event deduplication, acknowledgement, recovery, X/N, ETA and containment.

## Lifecycle wake conditions

With a local board present, the watch also emits:

- `idle_cards_unfinished_work`: unfinished running or queued tasks with spare slots under the observed resource cap. `state.allocation` or `state.resources.allocation` supplies `effective_cap`, `actual_cards`, `loading_cards` and `reserved_cards`; used IDs are unioned. `state.resources.available_slots` is the fallback observation.
- `question_unanswered_30min`: a GPT decision request in the dated exchange has waited thirty minutes. A lead entry with the same task ID resolves it; unrelated replies preserve the pending question. Headings and examples are in `protocol/lifecycle.md`.
- `flow_issue`: a GPT-owned lifecycle issue with a stable code, task and suggested action.

These conditions use the existing deduplication, acknowledgement and recovery queue. Quiet polls preserve silence. The watch observes; the existing assistant session checks authorization and acts. Routine decisions go to the research lead while independent work continues. User-operated actions, external sending, payment, deletion and resource limits retain the user's approval rules.
