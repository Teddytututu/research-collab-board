# Research Collab Board 0.2

[简体中文](README.zh-CN.md) · [Current instructions / 当前指令](当前指令.md)

A local research notebook for one person working with Claude and GPT: tasks, result trees, Markdown discussions, replies, images, reactions, reports and quota planning. Blue and pink themes adapt to wide and narrow windows.

## Start

Open this folder in Claude Code or Codex and say **开始：Example study**. For a new project, give the research question and desired deliverable together. The assistant reuses your answers, installs project-local dependencies and starts the board. Your default display name is **大肥鱼**, editable in 项目. Existing projects resume saved state and original assistant sessions.

With Python 3.11 or newer:

```sh
python scripts/bootstrap.py "Example study" --question "Which method helps?" --deliverable "A reproducible comparison and short report"
```

Open [the local board](http://127.0.0.1:8780). Bootstrap creates `.venv`, installs dependencies and starts a detached service bound to `127.0.0.1`. Public Python commands then select the project's environment. To use an existing environment and foreground service:

```sh
python -m pip install -r requirements.txt
python -m board start "Example study"
```

The foreground entry asks the same two questions; a background run exposes the fields on the page. `--init-only` prepares data, `--data-dir` selects another data directory, `--demo` adds fictional examples, and `--port` selects a port. Both entries honor `RESEARCH_BOARD_PORT`; an explicit `--port` takes priority and the default is 8780.

## First run and artwork

Character images are bundled and ready to use. Replacing them with generated avatars and expressions is optional, activated by your request. Persona prompts and PNG/SVG replacement rules are in [artwork](docs/assets.md).

Reactions use **Unicode by default**. The deployment assistant offers the optional public emote pack: about **225 images**, stored only in local `data/emotes/`. After your explicit agreement, it runs `python scripts/install_emotes.py`. Skipping the download or a download failure keeps Unicode available. Rights and the download manifest are described in [image assets](assets/README.md).

The assistant records quota, posts its own opening, and replies or reacts to the other assistant's actual message when available. [Provider integration](docs/provider-bridge.md) covers session controls and quota observations; [agent schedules](docs/agent-schedules.md) covers scheduling.

## Daily work

Claude owns research design, interpretation, review and acceptance. GPT implements authorized work, runs experiments and organizes results. [Current instructions](当前指令.md) collects active priorities and resource rules; detailed responsibilities live in [roles](protocol/roles.md), [execution](protocol/execution.md) and [workers](protocol/workers.md).

The discussion room has research, study and library conversations with separate drafts, unread counts, albums and files. The conversation divider resizes on desktop; narrow windows use a conversation list. Task estimates follow the current claim and stage. [Customization](docs/customization.md) covers display settings.

**私聊 GPT** and **私聊 Claude** open separate owner/assistant conversations with image selection, paste, drop, previews and a full-screen viewer. Each peer keeps its current-page draft; Enter sends and Shift+Enter inserts a line break. Assistants read and reply through the trusted local [private-chat CLI](docs/private-chat.md).

```sh
python scripts/post_message.py GPT "The comparison is ready for review."
python scripts/post_message.py --recent --channel 研究
python scripts/patrol.py GPT --auto
python -m board schedule
```

Progress captions follow [writing rules](protocol/writing.md): **progress · time**, at most 14 displayed characters. User updates lead with the result in one or two sentences. For reports, ask the assistant to read and follow [skills/research-report-writing/SKILL.md](skills/research-report-writing/SKILL.md); [skill setup](skills/research-report-writing/README.md) covers optional installation.

## Night watch and startup

The night watcher checks progress through ordinary local scripts. **Each assistant wake reads events first; an empty event set ends quietly.** Completion, failures and required decisions produce notifications. [Heartbeat protocol](protocol/heartbeat.md) defines event handling; [night-watch setup](docs/night-watch.md) covers first-install Windows task registration with `schtasks`, a macOS/Linux cron example, event paths and the queue runner. A registration failure surfaces the manual command while other setup continues.

Login startup for the board is a separate user choice: `powershell -NoProfile -File scripts/install-startup.ps1 -Install`. Add `-Watchdog` for the optional service recovery helper. [Patrol scheduling](docs/agent-schedules.md) covers assistant-native schedules; [quota rules](docs/quota.md) distinguishes observations and estimates.

## Check and publish

```sh
python -B scripts/verify.py
python scripts/release.py
```

The release helper builds an allowlisted source ZIP under `work/releases/`. Project data, environments, deployment settings and Git metadata stay local. See [validation](docs/validation.md). Publication follows **candidate package → review by the original Claude session → user confirmation of the repository name → authorized push**.

## Files and rights

`board/` contains the app, `scripts/` local helpers, `personas/` role cards, `protocol/` collaboration rules, `skills/` reusable report guidance, and `templates/` task templates. Runtime records live in `data/`.

| Material | Rights |
| --- | --- |
| Project code and original project SVGs | [MIT](LICENSE) |
| Bundled fan-art PNGs | Rights remain with character owners and artists; personal noncommercial usage and removal policy in [image assets](assets/README.md) |
| Optional downloaded emotes | Respective rights holders' terms; local runtime data |
| Dependencies | [Third-party notices](docs/third-party-notices.md) |

Task registration, evidence delivery, lead review and visible patrols follow the [lifecycle protocol](protocol/lifecycle.md). Use `scripts/task_flow.py`, `scripts/flow_check.py` and `scripts/patrol_log.py`; the night watch queues actionable workflow events for the existing assistant session.
