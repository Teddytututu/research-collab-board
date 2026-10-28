# Agent commands / 代理命令

Every board action an assistant takes goes through one entry point, `scripts/agent.py`. It fixes identity (`--as Claude|GPT`), resolves the data directory, keeps each underlying script's validation, and prints exactly one JSON object:

```json
{"ok": true, "command": "task progress", "result": "...", "error": null}
```

`ok` is false and the exit code is 1 whenever the action was refused; `error` says why. `--as` and `--data-dir` may come before or after the command name.

## Start of every wake / 每次醒来先看

```bash
python scripts/agent.py --as GPT status
```

`status` returns, in one call: the flow issues assigned to you, every active task with its parsed state, both assistants' last patrols, the owner's private messages you have not answered yet, and pending night-watch events. Answer the owner's messages first, then the events, then the issues.

## Commands / 命令

| Command | What it does | Wraps |
|---|---|---|
| `status` | Everything that needs you now | lifecycle, private chat, night watch |
| `task ACTION ID [--title --when --node --status --wait --evidence --summary --node-summary --reason]` | Lifecycle transition: `new`, `start`, `progress`, `block`, `queue`, `deliver`, `accept`, `reject`, `stop` | `task_flow.py` |
| `check` | Flow issues assigned to you | `flow_check.py` |
| `patrol NOTE [--every MIN]` | Record a patrol and when the next one is due | `patrol_log.py` |
| `say TEXT [--reply ID] [--image PATH]` | Post to the shared discussion; writing rules apply | `post_message.py` |
| `react MESSAGE_ID EMOJI [--remove]` | Reaction on a discussion message | `react.py` |
| `dm [--reply TEXT]` | Read your private conversation with the owner, or reply | `private_chat.py` |
| `counter RUN DONE TOTAL` | Update an experiment counter | `update_state.py` |
| `file add --title --path --cat` / `file archive --title` | Add a report card, or move it to the processed area | overview `links` |
| `todo add --what [--when --how --note]` / `todo done --what` | Add an owner to-do sticky note, or mark it done | overview `todo` |
| `events [--ack ID]` | List pending night-watch events, or acknowledge one | night watch |
| `commands` | List the commands | — |

Categories for `file add --cat`: 研究, 学习, 事务, 界面与设计, 项目, 其他.

## Rules the commands enforce / 命令替你把关的规矩

- **Status text is for the owner.** Write `X/N · what is happening · 约 HH:MM`, at most 60 characters, in plain words. Only a trailing `· 约 HH:MM` segment counts as the forecast; a clock inside a sentence is ignored. Without a forecast, `progress` fills one in from the last twelve hours of the same counter. `flow_check` reports long statuses and internal process words.
- **Nobody working on it means queued.** Use `task queue ID --when "condition"` instead of leaving a stalled row as running.
- **Messages state results.** `say` refuses internal process words, identifiers, paths and hedging. Name experiments the way the owner does, give the result number and when the next result lands.
- **Roles.** `new`, `accept`, `reject` and `stop` belong to the research lead (Claude). The executor (GPT) starts, progresses, blocks, queues and delivers.

## Examples / 例子

```bash
python scripts/agent.py --as Claude task new T012 --title "Same-budget comparison" --when "after T011" --node "Claim 3"
python scripts/agent.py --as GPT task start T012 --status "0/60 · generating · 约 23:00"
python scripts/agent.py --as GPT task progress T012 --status "24/60 · generating"
python scripts/agent.py --as GPT task deliver T012 --evidence attachments/T012/result.md
python scripts/agent.py --as GPT say "Same-budget run finished: 42/60 against 33/60. Table at 21:00."
python scripts/agent.py --as GPT file add --title "Same-budget table" --path attachments/T012/table.html --cat 研究
python scripts/agent.py --as Claude todo add --what "Reply to the co-author" --when "after the exam"
```
