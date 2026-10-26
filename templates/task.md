# Task: {{short title}}

## Assignment

| Field | Value |
| --- | --- |
| Task ID | TASK-{{number}} |
| Board entry | {{task link}} |
| Parent task | {{parent ID or standalone}} |
| Research lead | {{role identifier}} |
| Implementer | {{role identifier}} |
| Acceptance reviewer | {{role identifier}} |
| Blind checker | {{role identifier and role overlap}} |
| Current stage | {{installed board status}} |

## Question and deliverable

- Research question: {{one concrete question}}
- Decision this task supports: {{the smallest useful decision}}
- Deliverable: {{artifact, format, and project-relative location}}
- Scope: {{inputs, conditions, and permitted changes}}
- Dependencies: {{task IDs and required outputs}}

## Start conditions

- [ ] The research lead has agreed on the question and scope.
- [ ] Input versions, access, dependencies, and the working directory are ready.
- [ ] The prediction and acceptance criterion are recorded below.
- [ ] The blind-check procedure and responsible checker are assigned.
- [ ] The deployer's resource and paid-service allowances are recorded below.
- [ ] The recovery file and current-state update method are ready.

## Prediction and acceptance criterion

- Prediction: {{expected observation and direction}}
- Baseline or comparison: {{comparison condition}}
- Input set and version: {{fixed items and selection rule}}
- Measurement: {{metric, units, and calculation}}
- Acceptance rule: {{threshold and decision procedure}}
- Counterevidence: {{observation that would weaken the explanation}}
- Criterion revision: {{revision ID and reason for any later change}}

## Execution plan

1. {{smallest useful check}}
2. {{agreed experiment}}
3. {{blind assessment and handoff}}

## Resource envelope

- Compute and concurrency: {{CPU, GPU, memory, workers, and runtime limits}}
- Storage and transfer: {{local storage and cumulative outbound allowance}}
- Paid services: {{service, amount, currency, billing scope, and allowance owner}}
- Checkpoint and stop conditions: {{specific thresholds or events}}
- Limit-change decision owner: {{role identifier}}

## Recovery and current state

- Recovery file: `data/recovery/TASK-{{number}}.md`
- Current work and process summary: `data/attachments/state.json`
- Input and environment record: {{project-relative path}}
- Command and working directory: {{reproducible invocation}}
- Latest completed unit and checkpoint: {{unit and path}}
- Observed process identity and state: {{identity, state, and observation time}}
- Next exact step: {{action that another implementer can perform}}
- State update points: start, checkpoint, handoff, pause, completion, process exit.

## Blind check

- Frozen criteria and item set: {{paths or task links}}
- Neutral item IDs and concealed conditions: {{procedure}}
- Checker observations before reveal: {{record path}}
- Condition mapping and reveal: {{record path and responsible role}}

## Results and handoff

- Observed results: {{measurements and artifact links}}
- Counterevidence, null results, and failed approaches: {{setup and observations}}
- Interpretation and supported scope: {{claim tied to the examined conditions}}
- Working logs and evidence: {{companion paths}}
- Reader-facing deliverable: {{separate final artifact}}
- Acceptance record: {{completed acceptance template}}
- Follow-up task IDs: {{registered actions or closed}}

- Write scopes: {{project-relative scopes}}
- Estimated completion: {{date and time}}
- Confidence and basis: {{high / medium / low; one sentence}}
- Actual completion and estimate error: {{record at delivery}}

## Lifecycle registration

Use a reserved `T` number and a specification named `data/tasks/T001-short-name.md`. Register it with `scripts/task_flow.py new T001 --by Claude --title TITLE --when CONDITION`, adding `--node TITLE` for a result-tree task. State, progress, blocking, delivery and review follow `protocol/lifecycle.md`. Evidence contains existing artifact paths, numerical recomputation, and test commands with result tails; interface work includes actual screenshots.
