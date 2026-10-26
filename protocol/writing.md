# Writing for the board and conversations

[简体中文](writing.zh-CN.md)

These rules apply to progress captions, task status, user discussions and the assistant exchange. Use the user's configured display name; a new project defaults to 大肥鱼.

## Progress captions

Show one task and its current stage in **progress · time**, or a single status word. Keep the entire caption within **14 displayed characters**, including spaces and punctuation. Shorten words before publishing; retain the count when an estimate would overflow.

| Situation | Caption |
| --- | --- |
| Running, same-day estimate | `12/60 · ~06:14` |
| Running, next morning | `12/60·明早06:14` |
| Paused | `196/320 · 暂停` |
| Stopped | `196/320 · 已停` |
| Collecting after generation finished | `收图797/1000` |
| Waiting on an action | `等你登录` / `等审核` / `等空卡` |
| Estimate unavailable | `12/60` / `—` |
| Document or interface delivery | `约23:00交` |
| Delivered for review | `已交` |

Chinese examples are compact captions for the board's Chinese interface. Use equally short localized equivalents elsewhere. Show the active stage after a stage finishes. Use a next-day marker only for a date after today. Put causes, filenames and detailed counters in the task opened through “+”. Keep each caption's numbers scoped to that task.

## Messages to the user

Use **one or two sentences**: result or concrete user action first, then one useful number. Prefer everyday words and affirmative statements. Keep identifiers, hashes, process details and implementation records in attachments, unless they answer the user's question.

Example: “All 60 comparisons are ready. The report shows the three methods on the same samples.”

## Assistant exchange

Use at most **three sentences**: what finished, the key number, and the next step or decision for Claude. Ask consequential research questions directly in the exchange, with two concrete options and a recommendation. Give one entry path for supporting material.

## Reader-facing results

Organize findings for the reader's question. Keep logs, checks and provenance in companion records. Use the [research report skill](../skills/research-report-writing/SKILL.md) for reports and result pages.

Before posting, check that the line states the current position, a useful completion time when available, and the concrete user action when one applies.

## Concrete language across the project

Apply these rules to discussions, exchange entries, task files and status cells:

| Replace | Write instead |
| --- | --- |
| Circular disclaimers and abstract proof claims | State the actual scope: “The estimate uses 18 groups.” |
| Self-criticism followed by a rhetorical turn | Name the error and correction: “The two routes were mixed; the table now separates them.” |
| Agreement before changing the subject | State the finding or decision directly |
| A catalogue of checks | Give one useful count and put detailed commands in evidence |
| Empty abstractions such as closed loop, evidence chain, end-to-end, empowerment | Name the comparison, count or concrete action |

Preserve material limitations and user choice in plain language. `scripts/post_message.py` enforces 120 characters and two lines, and rejects internal paths, task IDs, hashes, process details, filenames and listed filler before processing attachments. The English and Chinese patterns live in `board/writing.py`. Read-only history and author withdrawal retain their existing behavior. Technical evidence belongs in task attachments; use the existing file option for supporting material. The exchange supports three useful sentences and its task evidence link.
