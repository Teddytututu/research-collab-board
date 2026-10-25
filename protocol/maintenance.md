# Board and exchange maintenance

All tools are in this repository and use the worker workspace lock. Runtime records live under data/.

```sh
python scripts/task_number.py --title "A concrete task"
python scripts/maintenance.py board
python scripts/maintenance.py exchange
```

Number reservation scans task files, the active board, archived tasks and existing reservations, then exclusively reserves the next T number. The dispatcher registers scope before a worker claims it.

Board compaction transfers accepted, cancelled and archived rows to data/tasks/archive.md while keeping running and review tasks active. Original row bytes and the complete preceding board are preserved. Repeating the operation keeps the existing archive.

Exchange maintenance groups dated third-level headings, respecting code fences. The complete source is retained under data/exchange/history-<hash>.md; daily files use YYYY-MM-DD.md and exchange.md is a hard link to the current day. board.workers.append_shared preserves that link while retaining earlier bytes in history. Keep source and daily files on one filesystem supporting hard links.

Read [roles](roles.md) and the [worker protocol](workers.md) for authorization and shared writes. Further task-page ETA presentation can be integrated after that interface version is ready; the current package keeps estimates and their basis in state.
