# Agent patrol scheduling / 助手巡检

The board calculates advice; the assistant uses its own scheduling tools to apply that advice. Opening this source package creates no provider automation and installs no system startup entry.

## Record a patrol

For automatic setup, use `python scripts/patrol.py GPT --auto` or the Claude equivalent. Fresh credential-free host observations take precedence; otherwise the configured quota band and reset-horizon estimate are explicitly recorded. See [provider bridge](provider-bridge.md). Setup uses the [bundled character artwork](assets.md) and completes the native goal or scheduled-task step, the assistant's opening, and a reply and reaction to the counterpart's actual message when available. Generating replacement avatars and expressions is optional and starts when the user requests different images. The first HTTP response is the service milestone.

自动接入使用 `python scripts/patrol.py GPT --auto` 或 Claude 对应命令，优先采用最新的免凭据主机观测，其余情况明确记录配置档位与重置时间估计，详见[原生接入](provider-bridge.md)。接入使用[包内角色图](assets.md)，完成原生目标或定时任务、助手自己的开工消息，以及另一助手真实消息出现后的回复与反应。生成替换头像与表情属于可选功能，用户提出换图需求后启用。首次 HTTP 响应作为服务启动节点。

```sh
python scripts/patrol.py Claude --tier plenty --reset-hours 12 --before 0.70 --after 0.69
python scripts/patrol.py GPT --remaining 0.40 --reset-hours 8 --before 0.41 --after 0.40
python -m board schedule
```

`--remaining` is for an observed exact ratio. Otherwise choose a quota band: `plenty=0.70`, `normal=0.40`, `tight=0.15`, `low=0.03`. Report the actual estimated reset horizon. The output files are `data/attachments/agents.json` and `data/attachments/schedule.json`. A browser quota selector records a band, rather than a provider measurement.

## Claude Code

In a Claude Code session, create the initial session task with:

```text
/loop 1h Read docs/patrol.md, do one authorized patrol, report quota, read data/attachments/schedule.json and apply Claude's next wake through the available scheduling tools. Keep unchanged healthy states quiet.
```

After each patrol, use the session's scheduling tools to replace the previous task at the suggested next time. Choose a one-time scheduled wake when the exact minute matters; fixed recurring intervals can be rounded by the provider. A sleeping low-quota assistant cancels routine patrols and resumes when the user returns or an installed event integration forwards a mention or review event. The board updates the wake advice on a mention; forwarding that event to an assistant uses the installation's explicitly configured integration.

For scheduling independent of an open session, use the provider's local Desktop scheduled task with this project directory and the same prompt. Keep the local computer available for tasks that read this project's data.

## Codex desktop

In the project's existing Codex chat, say:

```text
Create a recurring follow-up in this chat, initially every hour. Read docs/patrol.md, continue only authorized project work, report quota with scripts/patrol.py GPT, read data/attachments/schedule.json and adapt the next wake. Keep unchanged healthy states quiet. Notify on a meaningful result, failure or required user action.
```

The assistant discovers and uses the available `automation_update` tool with `mode=create`, `kind=heartbeat`, a project-specific name and the prompt above. Keep the returned automation ID in the local deployment record. On later runs use `mode=update` with that ID and the next suggested interval; use the tool's current schema for scheduling fields. When the row is paused, use the provider's pause or delete operation for routine patrols, then recreate it when the user or a configured event integration resumes work. Command-line sessions can prepare the prompt and scripts; scheduled task management uses the supported desktop interface.

## Per-patrol prompt

Read the project state and current task. Check the assistant's remaining quota before and after this patrol. Use actual values when available and a labelled band otherwise. Record the report, read the new schedule and adapt the provider task. With quota below 0.1, do only mentioned work or delivery acceptance, and assign transferable tasks to the eligible assistant with the larger capacity score. Keep meaningful decisions and recovery state in the project data.

Provider references: [OpenAI scheduled tasks](https://learn.chatgpt.com/docs/automations), [Claude Code scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks).
