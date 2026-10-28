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

1. `status` — one call returns your flow issues, active tasks, both patrols, the owner's unanswered private messages and pending events.
2. Answer the owner first: `dm` to read, `dm --reply "..."` to answer. A message from the owner is never left for a later wake.
3. Handle events (`events`, then `events --ack ID` once handled), then your flow issues (`check`).
4. Do the work. Record each real state change with `task ...`.
5. End with `patrol "one sentence" --every MINUTES`.

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
