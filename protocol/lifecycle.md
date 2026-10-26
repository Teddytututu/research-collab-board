# Task lifecycle and visible patrols

[简体中文](lifecycle.zh-CN.md)

The research lead uses the existing Claude identity; the executor uses GPT. Persona styling preserves these responsibilities. Task status changes go through `scripts/task_flow.py`. Daily recurring captions are the sole manual exception.

```
new (lead) → queued → running ⇄ blocked → delivered → accepted (lead, archived)
                         ↑                 ↘ rejected (lead) ↗
                any active state → stopped (lead, archived)
```

| Action | Role | Required fields | Result |
| --- | --- | --- | --- |
| new | Lead | title, when; optional node | Register an existing task specification and start condition |
| start | Executor | status starting X/N | Start from queued, blocked or rejected; node becomes doing |
| progress | Executor | status starting X/N | Update running task; 0 ≤ X ≤ N, N > 0 |
| block | Either | wait: waiting for WHO to DO WHAT | Record dependency and continue independent work |
| deliver | Executor | evidence | Existing project-relative file; running, blocked or rejected task becomes review-ready |
| reject | Lead | reason | Return delivered task with concrete acceptance criteria |
| accept | Lead | summary; optional node-summary | Archive delivered task and refresh result tree |
| stop | Lead | reason; optional node-summary | Archive active task and refresh result tree |

The lead can perform execution transitions too. Lead-only actions reject GPT. Scripts run in a trusted local workspace: `--by` records the acting role and checks workflow authority; the operating system supplies account authentication and file access.

## Commands and task specification

Create `data/tasks/T001-example.md` first, with goal, rationale, start condition, applicable result-tree node, required work, acceptance criteria and constraints. `--data-dir` defaults to `data/`; evidence is relative to that directory. A node title must uniquely identify an existing node.

```sh
python scripts/task_flow.py new T001 --by Claude --title "Compare methods" --when "Inputs ready" --node "Comparison"
python scripts/task_flow.py start T001 --by GPT --status "0/6"
python scripts/task_flow.py progress T001 --by GPT --status "3/6 · ~18:00"
python scripts/task_flow.py block T001 --by GPT --wait "waiting for researcher to review inputs"
python scripts/task_flow.py deliver T001 --by GPT --evidence attachments/T001/evidence.md
python scripts/task_flow.py accept T001 --by Claude --summary "Six cases reviewed" --node-summary "Comparison ready"
python scripts/flow_check.py --owner GPT --json
python scripts/patrol_log.py GPT "Reviewed events and updated comparison" --every 30
```

Transitions append `attachments/task-flow.jsonl` and the task history. Changed board rows retain the four existing fields and add an ISO update time. Shared storage retains original bytes. Accept/stop move rows into `tasks/archive.md` and remove active task/run projections. A node becomes done when all attached tasks are archived. The lead records scientific conclusions in `findings.md` within two days of closure and attaches result cards to the node's `results`.

## Deadlines

| Condition | Owner | Action |
| --- | --- | --- |
| Delivered for over 2 hours | Lead | Accept or reject |
| Blocked for over 2 hours | Lead | Decide or request a specific user action |
| Running update older than 3 hours | Executor | Update progress or record dependency |
| Rejected for over 2 hours | Executor | Revise and redeliver |
| Empty execution queue | Lead | Queue resource work and work using no compute slot |
| Board/result tree mismatch | Lead | Reconcile task state and node conclusion |

A blocked condition may include `until MM-DD`; a valid future date defers its deadline. `flow_check.py` reads the board, archive, tree, findings and patrols, returning stable issue codes with owner, task and action.

## Every wake

GPT handles `attachments/night-watch/events.json`, runs its flow check, starts eligible work within resource limits and records its patrol. Claude checks its own flow issues, exchange, user discussion and resource observations, then reviews, decides and queues work. Both record actual work through `patrol_log.py ROLE NOTE --every MINUTES`.

The top of “正在做” shows both roles' last patrol, next patrol, note and issue count. A patrol becomes overdue fifteen minutes after its next time. Actual wake scheduling belongs to the existing provider session.

## Decisions while work continues

During an accepted task, route routine decisions to the lead through the exchange, with two options and a recommendation. Continue independent authorized work. After thirty minutes, apply a recorded recommendation to reversible work within existing authorization and resource limits. Login, license consent, credentials, payment, external sending/publication, original-data deletion and personal choices follow the user's applicable approval policy. Put specific user-operated actions in the discussion.

Use a dated heading with an explicit offset and task ID; lead replies use the same task ID:

```md
### 2030-01-01T10:00:00+00:00 · GPT → Claude · T001
Please decide: A or B. Recommend A because it reuses the inputs.

### 2030-01-01T10:10:00+00:00 · Claude → GPT · T001
Use A.
```

Daily files live in `data/exchange/YYYY-MM-DD.md`; `exchange.md` remains supported. The watcher observes and queues events. The assistant evaluates authorization and performs actions.

The lead can request the mechanical all-archived tree repair with `python scripts/flow_check.py --fix-tree --by Claude`.
