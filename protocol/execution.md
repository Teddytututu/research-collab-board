# Continuous execution and complete results

1. Run one experiment process per physical accelerator and consume the frozen fixed queue until empty. During the run, check output presence and reasonable size; perform SHA and the full file audit once after the batch. Resource coordination counts devices under the current deployment rule; workers execute already assigned work directly.
2. Progress is X/N, where X counts groups with final outputs for every required route. Use `X/N · expected HH:MM` in the task board. Keep baseline stages, checks, archives and permission records in attachments. When executable work and eligible idle devices exist and X stays constant for an hour, prioritize the existing minimal experiment loop.
3. Post to the exchange for a result, a required decision, or a blockage lasting over thirty minutes. Limit each task to one message per hour and three sentences per message. Store process identities, commands, detailed progress and recovery records in state and attachments.
4. The dispatcher assigns two or three workers to independent write scopes, one task per worker. Each worker reuses an authorized provider-native goal with the complete countable task as its completion condition, such as 48/48 or 300/300 plus 30/30.
5. Execute prompts, seeds, parameters and branches already fixed by the plan. The research lead decides new scientific choices while independent authorized work continues.

| Condition | Action |
|---|---|
| The minimal loop fails twice consecutively | Explain the actual failure and proposed change to the research lead, then apply the agreed correction. |
| Reporting progress | Count only groups whose required final route outputs are complete; retain other counters in attachments. |
| A blockage lasts thirty minutes | Post its concrete cause and update the task-board status. |
| The first group completes | Check its frozen prompts, seeds, resolution and parameters once; continue the same configuration, writing new outputs to a new directory and retaining old outputs. |
| Loading a model | Check available memory first; allow at most two simultaneous loads on the host and release the loading lock when loading returns. |
| Using extra overnight slots | Extra slices beyond the usual five must be expected to finish naturally by 07:30; restore the applicable allowance by 08:00. |
| Fifteen-minute account check | Inspect other accounts on eligible devices. Count generation, scoring, loading and held physical reservations together; finish current finite slices before yielding excess slots under the deployment's three/five-device rule. |
| Changing or cleaning files | Resolve the real path and junction target first. Obtain the applicable user confirmation for deletion and retain protected data and other users' processes. |
| Continuing a goal | Keep the complete X/N as the finish condition; prioritize actual experiment execution after an hour without an increase when work and eligible idle devices exist. |
| Delivering numerical results | Recalculate the result table from final output files and record their paths in the companion audit. |
| Result-volume free space falls below 20GB | Pause new slices and report the capacity condition; retain checkpoints and all existing data. |

Recover ordinary failures through the current process and existing checkpoint. Resume on an eligible device of the same model after resources recover. Spending, account permissions, system changes, resource increases and new scientific comparisons go to their decision owner. Each deployment keeps its protected devices, sharing exceptions, and other users' files and processes intact.

## Light work, heavy work and time boxes

- **Light work, done directly:** reading papers, scoring images, running approved experiments, tallying numbers. No candidate bundles, no independent review hand-offs, no protective copies of large files; split 20+ independent items across parallel workers.
- **Heavy work, reviewed:** code other people run (the board, the night watch, lifecycle tools) keeps the candidate, tests and lead review.
- **Engineering is time-boxed to four hours** from `start`: deliver with a list of what is left, or block with the reason. Until experiment tables are out, take no new interface or engineering work.
- **Nobody working on it means queued:** a row whose counter is not moving with no process or worker behind it goes back with `task queue`.

## Red lines

- Never ask the owner for administrator rights or change operating-system settings.
- Answer the owner's private and discussion messages first on every wake.
- Statuses and discussion messages state results and times, not internal process words.

All board actions go through `python scripts/agent.py`; see [agent commands](../docs/agent-commands.md).
