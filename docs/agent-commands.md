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

It also returns `local_disk`: the available local volumes with `path`, `free_gib` and `total_gib`. The executor's first `status` each local calendar day posts one greeting in the discussion; repeated calls reuse that day's record. The lead acknowledges it with a reply or reaction.

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
| `ask TITLE BODY --option A --option B [--lean TEXT]` | Ask the other assistant in today's exchange; two nonempty options required | daily exchange |
| `note TITLE BODY` | Append an update or answer in today's exchange | daily exchange |
| `mood NAME [NOTE]` | Register this assistant's mood using an existing expression | overview mood |
| `commands` | List the commands | — |

Categories for `file add --cat`: 研究, 学习, 事务, 界面与设计, 项目, 其他.

## Rules the commands enforce / 命令替你把关的规矩

- **Status text is for the owner.** Write `X/N · what is happening · 约 HH:MM`, at most 60 characters, in plain words. Only a trailing `· 约 HH:MM` segment counts as the forecast; a clock inside a sentence is ignored. Without a forecast, `progress` fills one in from the last twelve hours of the same counter. `flow_check` reports long statuses and internal process words.
- **Nobody working on it means queued.** Use `task queue ID --when "condition"` instead of leaving a stalled row as running.
- **Messages state results.** `say` refuses internal process words, identifiers, paths and hedging. Name experiments the way the owner does, give the result number and when the next result lands.
- **Roles.** `new`, `accept`, `reject` and `stop` belong to the research lead (Claude). The executor (GPT) starts, progresses, blocks, queues and delivers.

## Stability checks / 稳定性检查

`check` and `status` include these issues, assigned to the responsible assistant:

- Owner discussion messages require an explicit `say --reply ID` or active reaction within 2.5 hours for Claude and 45 minutes for GPT. A leading `@Claude` or `@GPT` assigns just that assistant; mentions later in the body retain both recipients. Withdrawn messages and saved library copies are skipped; removing a reaction reopens the corresponding obligation.
- Each assistant's private conversation uses the same role deadline. A later assistant reply acknowledges the preceding owner messages. Status reads only the acting assistant's private conversation, and flow issues contain metadata rather than private message bodies.
- Executor exchange questions require a lead answer within 2.5 hours. `ask` and `note` write the date, timestamp and `sender → recipient` heading into `exchange/YYYY-MM-DD.md`; they add `问：` and `答：` respectively, keeping task-number titles distinct from legacy task labels. A later lead `note` with the same title answers that question; each title retains its own deadline. Legacy task-labelled headings retain task-specific matching, and the existing 30-minute night-watch question condition also recognizes new headings.
- Local free space below 20 GiB creates a GPT issue. Review disposable files within the task's authorized scope and refer owner-data decisions to the lead.
- Today's executor greeting uses the lead reply deadline. Each role's mood registration becomes stale after 12 hours; an initial registration becomes due 12 hours after project creation. `mood` accepts existing bundled or project-generated expression names for that role and refreshes the timestamp even when the name stays the same. The command error lists valid names. Records are `claude_mood` and `gpt_mood` in the overview, each with `mood`, `note`, `at`; presentation is handled separately.

Character expressions appear after the existing reaction grid, separated by one thin line. `mood expression:insight` and `mood expression:wave` select an assistant's own new artwork; `expr:ROLE-NAME` is an exact catalog key and stays role-scoped. Current moods appear in discussion, private-chat and title portraits. The owner clicks their own portrait to choose a persistent mood, while other portraits open the full uncropped image. Original account portraits remain the fallback. Avatar framing uses alpha-bound metadata and leaves the image pixels intact.

Configure positive numeric thresholds in the existing `data/project.json` under `stability`:

```json
{
  "stability": {
    "lead_reply_hours": 2.5,
    "executor_reply_minutes": 45,
    "collaboration_reply_hours": 2.5,
    "disk_min_free_gib": 20,
    "mood_max_age_hours": 12
  }
}
```

Before committing, stage the intended changes and run `python scripts/check_eol.py`. It compares staged text blobs with HEAD and lists files whose LF/CRLF/CR style changed, including detected renames and mixed styles. New files have no prior style; deleted files and binary blobs are skipped. `verify.py` and `release.py` run this guard before tests or packaging. Source archives without Git metadata report an explicit skip.

## Examples / 例子

```bash
python scripts/agent.py --as Claude task new T012 --title "Same-budget comparison" --when "after T011" --node "Claim 3"
python scripts/agent.py --as GPT task start T012 --status "0/60 · generating · 约 23:00"
python scripts/agent.py --as GPT task progress T012 --status "24/60 · generating"
python scripts/agent.py --as GPT task deliver T012 --evidence attachments/T012/result.md
python scripts/agent.py --as GPT say "Same-budget run finished: 42/60 against 33/60. Table at 21:00."
python scripts/agent.py --as GPT file add --title "Same-budget table" --path attachments/T012/table.html --cat 研究
python scripts/agent.py --as Claude todo add --what "Reply to the co-author" --when "after the exam"
python scripts/agent.py --as GPT ask "Comparison budget" "Which sample pool should we use?" --option "Reuse the accepted pool" --option "Generate a new pool" --lean "Reuse the accepted pool"
python scripts/agent.py --as Claude note "Comparison budget" "Use the accepted pool."
python scripts/agent.py --as GPT mood calm "Reviewing the comparison"
```
