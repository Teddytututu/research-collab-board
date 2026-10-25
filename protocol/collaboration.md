# Collaboration protocol

[简体中文](collaboration.zh-CN.md) · [Project home](../README.md)

## Purpose

Use the board to connect each research question to an agreed experiment, recoverable execution, and an explicit acceptance decision. The unit of work is a task with a stable ID.

## Responsibilities

| Role | Owns | Produces |
| --- | --- | --- |
| Research lead | Research questions, hypotheses, comparisons, interpretation, scope changes, and acceptance | A clear decision and its supporting evidence |
| Implementer | Engineering design, code, experiment execution, recovery, and delivery | Reproducible artifacts and an accurate execution record |
| Blind checker | Assessment against frozen criteria with the intended result concealed where practical | Observations and scores recorded before revealing conditions |
| Deployer | Account permissions, runtime environment, resource limits, and paid-service allowances | Deployment settings and an explicit operating envelope |

One participant may hold several roles. Record the person or agent responsible for each role on the task and identify any overlap in the acceptance record. The research lead retains scientific judgment when implementation is delegated.

## Register every task

Create a board entry before execution, including for exploratory scripts, checks, and follow-up experiments. Give independently resumable work its own entry and link its parent task.

Each entry contains:

- A question and the smallest decision the task should support.
- A research lead, an implementer, and an acceptance reviewer.
- Inputs, permissions, dependencies, and a precise deliverable.
- Start conditions and a resource envelope.
- A prediction, comparison, measurement, and acceptance criterion.
- A recovery-state file and a pointer to the latest artifact.
- A blind-check plan and space for counterevidence and null results.

Use the [task template](../templates/task.md) as the starting point.

## Make work ready

The research lead and implementer agree on the start conditions before execution:

1. The research question and deliverable are concrete.
2. Input versions, access, dependencies, and the working directory are identified.
3. The prediction, comparison, metric, and decision rule are written down.
4. Compute, storage, transfer, paid-service limits, and stop conditions are explicit.
5. The recovery file, state update method, and blind-check procedure are selected.

When a condition requires a decision, move the task to a waiting stage and record the exact decision and its owner. Continue independent registered work within its own agreed scope.

## Freeze the prediction and criterion

State what should happen, against which baseline, on which inputs, and under which measurement. Include an observation that would weaken the proposed explanation.

For example, a fictional task may compare two renderers on synthetic circle diagrams and predict a lower position error at an agreed runtime budget. The criterion specifies the diagram set, metric, threshold, and evaluation procedure before the run.

Record changes to the prediction or criterion as a new revision with a reason. Keep earlier observations associated with the criterion that governed them. Exploratory findings can support a newly registered confirmatory task.

## Execute and preserve recovery

Start with the smallest run that resolves an important uncertainty. Scale within the deployer's limits after inspecting its output.

Maintain a task recovery file, such as `data/recovery/TASK-001.md`, with:

- Task ID, responsible roles, current stage, and last update.
- Inputs and versions, configuration, command, environment, and working directory.
- Current checkpoint, completed units, output locations, and the next exact step.
- Observed process identity, process state, and the time of observation.
- Resource use, remaining allowance, and applicable stop conditions.
- Errors, counterevidence, decisions, and recovery actions.

Keep the current work and process summary in `data/attachments/state.json`, using the structure supplied by the application and demo. Update it at task start, checkpoints, handoff, pause, completion, and process exit. Link detailed recovery files from the current state using the supported fields.

A process ID identifies a process; inspected output and checkpoints establish progress. Confirm the live process identity and latest artifacts before resuming a task. Record an ended process and its exit result, then choose the next action from the recovery file.

## Use blind checks

Freeze the criteria and item set before inspection. Give the checker neutral item IDs and conceal method labels, expected rankings, or preferred outcomes where practical.

Have the checker record observations before revealing the conditions. Preserve the item mapping and reveal procedure in the acceptance evidence. When the same participant implements and checks, record that arrangement and use concealed item order or condition labels where practical.

Keep the original observations when a later discussion changes the interpretation.

## Keep counterevidence visible

Record worse results, null effects, invalid runs, and failed approaches alongside positive results. For each, capture the setup, observation, likely explanations, and the next discriminating check.

Separate an observed result from an interpretation. Scope conclusions to the inputs and conditions actually examined. A well-documented counterexample can satisfy a task whose purpose is to test a hypothesis.

## Accept explicitly

The implementer hands over artifacts, recovery state, measured results, blind-check records, counterevidence, and the proposed conclusion. Use the [acceptance template](../templates/acceptance.md).

The research lead compares the evidence with the frozen criterion and chooses acceptance, revision, or a newly scoped follow-up. Record the decision, the supported claim, its scope, and the accepted artifact. Create board tasks for follow-up actions.

Use the installed board's status labels to represent registration, readiness, execution, review, acceptance, revision, and pause. Keep waiting conditions and their decision owners explicit.

## Separate working records and reader material

Working records contain commands, timestamps, diagnostics, source anchors, verification details, and recovery instructions. Reader-facing deliverables contain the research content appropriate to their audience. Keep these in separate files and connect them through the task entry.

Use the discussion room for short, task-linked updates. A useful message states the result or decision, the task ID, and the next action or artifact link. Put long technical records in the task's working files.

Use the [meeting template](../templates/meeting.md) for decisions involving several tasks and the [heartbeat template](../templates/heartbeat.md) for agreed progress checks.

## Respect the operating envelope

The deployer configures resource limits and paid-service allowances. Each task records applicable compute, concurrency, storage, transfer, service, currency, and spending limits, together with the owner of a limit change.

At a stop condition, checkpoint the task, update `data/attachments/state.json`, and record the specific resource or authorization decision. Resume resource-dependent work after that decision is recorded.

## Publish fictional examples

Keep repository examples fictional. Use original SVG placeholders for packaged visual resources. Store local research data, generated credentials, and deployment-specific runtime records in the local deployment workspace.

Publish selected code, templates, protocols, and fictional examples with their applicable license. Review screenshots and bundled examples for the same publication boundary.

## Brainstorm before freezing an experiment

For each candidate, state the mechanism, expected observation, competing explanation, cheapest distinguishing test, and stop condition. The lead chooses the research direction and freezes the comparison. The implementer carries out the agreed test and brings unexpected observations back for interpretation.

## Common operational pitfalls

Check the current process identity before resuming work. Freeze input lists and comparisons before counting results. Keep blind labels separate from model scores and reveal the mapping only after annotation. Count every loading, generation and scoring process against the same compute budget. Preserve counterevidence and old state bytes. Give readers the finished result and keep diagnostic detail in a separate working record.

## Multiple workers

Follow the [worker protocol](workers.md) for dispatch, exclusive scope claims, quota and CPU limits, heartbeats, shared writes, recoverable execution, ETA calibration and concise handoff. Follow [continuous execution](execution.md) for ordinary recovery and the decision boundary.
