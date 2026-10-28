---
name: board-agent
description: Operate the research collaboration board as an assistant (Claude as research lead, GPT as executor). Use at the start of every wake or patrol, and whenever you change a task's state, report progress, post to the discussion, answer the owner's private messages, add a report card or an owner to-do, or acknowledge night-watch events.
---

# Board agent

All board actions go through one command; never edit `data/board.md`, `overview.json` or the message ledgers by hand.

```bash
python scripts/agent.py --as <Claude|GPT> <command> ...
```

Every call prints one JSON object with `ok`, `command`, `result` and `error`. If `ok` is false, read `error`, fix the input and try once more; do not work around the command by writing files directly.

## Every wake, in this order

1. `status` — one call returns your flow issues, active tasks, both patrols, the owner's unanswered private messages, pending events and local disk capacity. The executor's first status each local day posts one greeting; the lead replies or reacts.
2. Answer the owner first: `dm` to read, `dm --reply "..."` to answer. A message from the owner is never left for a later wake.
3. Handle events (`events`, then `events --ack ID` once handled), then your flow issues (`check`).
4. Do the work. Record each real state change with `task ...`.
5. End with `patrol "one sentence" --every MINUTES`.

## Questions, notes and moods

- Use `ask TITLE BODY --option A --option B [--lean TEXT]` for a decision and `note TITLE BODY` for an update or answer. The command writes the daily exchange heading, time and direction. Answer each pending executor question with a lead `note` using the same title.
- Use `mood NAME [NOTE]` to register your own mood. Choose an expression already available for your role; the command lists valid names on error. Refresh it within 12 hours, including when the expression stays the same.
- `check` reports owner discussion/private replies due after 2.5 hours for the lead and 45 minutes for the executor. A leading role mention assigns just that assistant; an explicit reply or active reaction acknowledges a discussion message. Lead exchange replies and daily greetings use 2.5 hours. Low disk space below 20 GiB belongs to the executor. Project-specific positive thresholds live under `stability` in `data/project.json`; see the command reference for the keys.
- Before committing run `python scripts/check_eol.py` after staging. `verify.py` and `release.py` also compare staged line endings with HEAD.

## Writing statuses and messages

- Status: `X/N · what is happening · 约 HH:MM`, 60 characters at most, plain words. The forecast is only the trailing `· 约 HH:MM`; leave it out and `progress` estimates it from the counter's recent speed. A counter that is not moving because nobody is working on it is `task queue ID --when "condition"`, not running.
- Discussion (`say`): result number first, then when the next result lands; a third sentence only when the owner must do something. Use the owner's names for experiments. Internal process words, identifiers, paths, hashes and hedging are refused.

## Work size

- Light work (reading, scoring, running an approved experiment, tallying): do it directly, split 20+ independent items across parallel workers, keep no protective copies of large files.
- Heavy work (code other people run: the board, the night watch, lifecycle tools): candidate, tests, lead review.
- Engineering is time-boxed to four hours from `start`: deliver with a list of what is left, or block with the reason.

## Never

- Ask the owner for administrator rights or change operating-system settings.
- Delete data permanently, touch other users' files or processes, or exceed the agreed resource limits.
- Push to a remote or publish without the owner's explicit approval.

Command reference: [docs/agent-commands.md](../../docs/agent-commands.md).
