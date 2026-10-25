# One dispatcher, multiple workers

The dispatcher recovers current state and assigns one task per worker. Each worker retains that task until delivery or a recorded handoff. Use the smaller of three ordinary workers, the quota-supported count and the configured CPU allowance. Reserve two physical CPU cores when the machine provides that capacity. Accelerator work also obeys the deployment's device count, memory, runtime and protected-device rules.

The quota count follows the operating mechanism: `B = r / max(T, 0.5)`, available patrol share `0.3 × B × min(24, max(T, 0.5))`, divided by the EMA invocation cost, rounded down; the dispatcher bounds ordinary work to 0–3. Ordinary work with remaining quota below 0.1 receives zero workers. `board.workers.quota_capacity` estimates quota capacity; the dispatcher applies the ordinary three-worker ceiling. The dispatcher records its observed input values and passes the chosen allowance to the claim command.

A deployment may record an explicitly user-authorized finite window in `data/attachments/state.json` under `worker_pool_policy.temporary_override`. Its fields are `authorized_by: "user"`, a rewritten authorization summary, `starts_unix`, `expires_unix`, and `max_workers` (up to six). `cpu_slots` limits the effective allowance. `board.workers.effective_worker_limit` applies that policy to new claims; expiry restores the normal maximum while current leases finish their accepted scope. The source package contains the mechanism and fictional tests; each deployment supplies its own authorization and dates. Physical accelerator allowances remain a separate deployment rule.

```sh
python scripts/workers.py claim TASK-001 --worker W1 --scope board --allowed-workers 2
python scripts/workers.py heartbeat TASK-001 --token RETURNED_TOKEN
python scripts/workers.py release TASK-001 --token RETURNED_TOKEN
```

Claims use an exclusive task file under `data/attachments/locks/` while holding a process-wide registry lock. Task, worker and write-scope conflicts are rejected. A directory scope reserves all descendants; use a directory for wildcard groups. A `.` scope reserves the whole project. Declare exact files for field edits whose coordination the dispatcher already controls. Scope declarations and the registry form the coordination contract; workers verify ownership before every write.

Heartbeat every ten minutes. A lease expires thirty minutes after its last heartbeat. Reclaiming preserves the expired file in history. The old worker reacquires before further writes; the replacement token prevents the old owner from renewing the new lease. Completion releases the task into history. The regression suite demonstrates independent-process contention, overlap rejection, heartbeat, expired reclaim and old-byte preservation.

Shared state updates hold `board.storage.locked(data_dir)` and update only the assigned fields with `storage.write`. Shared discussion uses `project.post`; Markdown board and exchange changes use the same workspace lock and byte-preserving field edits or append operations. Keep recovery commands, process identities and checkpoints in state. Put worker IDs in technical handoff headings, such as `GPT · W1`; human conversation carries useful decisions and results.

Within thirty minutes of accepting work, record an expected finish, confidence and basis in the task and state. Revise the estimate at each handoff. Record estimate versus actual completion for later calibration. Experiments use recent 30–60 minute throughput, with the historical mean as fallback; a paused experiment records the remaining duration after resumption.

Research workers keep assigned experiments moving through the existing server controller, checkpoints and physical-device locks. Verify processes by account, creation identity and full command. Reuse live processes; inspect and repair failed exits. After the first device change, compare replay with the same seed. The research lead owns the sample set, seed rules, model and scoring criterion. Generation, scoring and loading count against the same physical-device cap; explicit temporary windows use their approved allowance and ordinary windows use the deployment default.

Use conditional estimates for dependent work, revise delays with a reason, and keep final task results within ten lines. Shared helpers are `board.storage.update_json(data_dir, relative_path, transform)`, `board.workers.update_board(data_dir, task, status)` and `board.workers.append_shared(data_dir, relative_path, text)`. They preserve previous bytes while holding the project lock. Claim accepts `--eta` and release accepts `--status`. Research review and final acceptance remain with the board's existing reviewer.


The five execution rules and eleven operational conditions in [continuous execution](execution.md) apply to experiment progress, resource counting, communication and completion.
