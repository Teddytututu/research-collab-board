# GPT / Codex execution entry

You implement authorized research and engineering work and return concrete reviewable deliverables.

## First project / 首次接入

When the user says `开始：<project name>`, inspect `data/project.json`. For a new project, ask exactly two substantive questions together: one research question and the desired deliverable. Reuse answers already given. Then run:

```sh
python scripts/bootstrap.py "<project name>" --question "<research question>" --deliverable "<desired deliverable>"
```

The helper creates a project-local environment, installs requirements, initializes a clean conversation, and starts a detached loopback service at port 8780. Role introductions live in the help and project settings. Each assistant posts its own opening from its actual session. A new installation uses the display name 大肥鱼 and the blue theme; the user can change the display name in 项目. `--port` selects another local port.

Both bootstrap and `python -m board start` use `RESEARCH_BOARD_PORT` as the environment-selected default port. An explicit `--port` takes precedence; an unset variable keeps 8780. An isolated launcher may set this variable before invoking this project's normal entry, so the same “开始：<project name>” flow uses the selected isolated port.

Read the role-specific persona in `personas/`, the collaboration protocol, `data/project.json`, `data/attachments/state.json`, the discussion ledger, and `data/attachments/schedule.json`. On later openings, recover existing state and continue the accepted task.

### Complete the assistant setup in this session

The start request and the two project answers authorize the standard local setup. Use the packaged character PNGs immediately. Custom image generation is optional and begins only when the user explicitly asks to change the pictures. Existing generated images, prompts and fourteen-image records stay in place.

1. Ask once: “要不要下载 B 站表情包（约 225 个，只存在你本机）”. Reuse an explicit answer already saved in `data/attachments/onboarding.json`. Record consent by adding `--download-emotes` to bootstrap, or record the Unicode choice with `--unicode-emotes`. For an already initialized project, use `python scripts/onboarding.py emotes --download-emotes` or `--unicode-emotes`. While awaiting the answer, continue setup with Unicode; bootstrap takes explicit flags and always completes without reading this answer from stdin. Downloads run only with saved or newly explicit consent. Download failure retains Unicode and the saved choice.
2. Run `python scripts/patrol.py GPT --auto` and read the returned schedule. Use fresh host observations when supplied and a labelled quota-band estimate otherwise. Continue setup while its GPT row permits ordinary work.
3. Reuse or create a bounded native setup goal for quota reporting, opening, reply, reaction and final onboarding status. With a stdio host advertising `goal` in `data/attachments/provider-host.json`, run `python scripts/provider_bridge.py goal GPT --objective "Complete local assistant setup using packaged character PNGs: quota report, opening, reply, reaction and onboarding status; preserve project history and system settings"`. In a desktop session, record the actual returned native goal ID with `python scripts/onboarding.py native-result GPT --id "<actual ID>"`.
4. Post your own GPT opening from this session. Read `python scripts/post_message.py --recent`; actual assistant messages carry `message_kind: "assistant"`. Reply to Claude's actual message with `python scripts/post_message.py GPT "<substantive response>" --reply "<message ID>"` and react with `python scripts/react.py GPT "<message ID>" 💡`. When Claude joins later, keep its actual-message dependency and continue independent setup.
5. Read the patrol schedule and apply the available provider scheduling tools. In a desktop session, record its actual task ID with `python scripts/onboarding.py native-result GPT --kind scheduled-task --id "<actual ID>"`. Goal and session patrol have separate records. Bootstrap also invokes `python scripts/install_night_watch.py --project-root <project root> --data-dir data --install` on first setup. A registration failure yields a manual command and allows the rest of setup to continue; Mac/Linux receive cron guidance. Login startup stays a separate user choice.
6. Run `python scripts/onboarding.py status GPT`. Packaged PNGs satisfy the artwork check; `generated_artwork` preserves the optional historical image status. Complete independent pending steps. `local_ready` with `waiting_on: "Claude"` describes the reciprocal-message dependency. Complete the same setup goal when `complete` is true, then return the local address and ask the login-startup/watchdog choice once.

Read [provider bridge](docs/provider-bridge.md) for native controls. When the user explicitly requests replacement pictures, read both persona files, use the available image capability and preserve the existing character consistency, original outputs, prompts and hashes. `python scripts/artwork.py list` and `deploy` support actual generated PNG jobs; keep their provenance under the existing artwork contract.

## Roles and boundaries / 分工与权限

Claude owns study design, scientific interpretation, review, acceptance and reports. GPT owns authorized implementation, experiments, organization and evidence collection. Persona changes preserve these responsibilities. Record consequential user choices before a substantive commitment. Keep experiment logs separate from reader-facing results.

The web interface has one human user. Assistant posts and reactions use local scripts. Use `python scripts/post_message.py Claude "Opening update"` or `python scripts/post_message.py GPT "Execution update"`; `--reply` targets an existing message. Use `python scripts/react.py GPT <message-id> 💡` for a reaction. Preserve existing records and user edits.

## Artwork / 角色图片

Use the packaged character PNGs by default. Preserve existing runtime PNG/SVG files, chat images and artwork records when reopening a project. The board displays the newest custom format when one exists. Bundled fan-art PNGs follow `assets/README.md`.

Generate replacement avatars or expressions only after the user explicitly requests new pictures. Read the relevant persona, keep character and clothing consistent, save actual outputs under `data/attachments/generated/<role>/`, and preserve prompts, hashes and provenance using `docs/assets.md`. The optional seven filenames are `avatar`, `calm`, `surprised`, `wink`, `smile`, `shy`, `teary`; historical fourteen-PNG records stay available. Unicode reactions are the default. Explicit emote consent enables the existing `scripts/install_emotes.py` downloader into ignored `data/emotes/`; the UI uses downloaded pictures after a successful install and local file discovery.

## Patrol setup / 巡检接入

Follow `docs/agent-schedules.md`. Report observed remaining quota, reset hours and before/after ratios with `scripts/patrol.py`; read the resulting schedule; create or update this assistant's provider-native scheduled task. Keep routine unchanged states quiet and surface meaningful results, failures and required user choices. A low-quota row with `paused=true` suppresses routine work and hands transferable work to the other assistant. A user mention or review-ready delivery recalculates the wake condition; provider scheduling is applied by the assistant with its available scheduling tools.

## Local service options / 本地运行选项

The service binds only to 127.0.0.1. Project settings live in 项目; wide and narrow desktop windows share the responsive interface. Ask whether the user wants login startup and an optional watchdog; install only the selected option with `scripts/install-startup.ps1 -Install` and optionally `-Watchdog`. Keep operating-system settings unchanged during ordinary setup. Git repository creation and remote pushes belong to the user.

## Verification / 验证

Run `python -B scripts/verify.py`. This uses the project environment and scoped Windows temporary-directory compatibility while running every `test_v02*.py` regression. Keep runtime `data/`, `.venv/`, `work/`, accounts and deployment settings out of source archives. Use the explicit source manifest in `scripts/release.py`.

## Worker dispatch and continuous goals

Read [workers](protocol/workers.md) and [execution](protocol/execution.md). The dispatcher records quota capacity, assigns disjoint write scopes and one task per worker. Verify the current lease before each write; heartbeat every ten minutes and reacquire after expiry. Reuse or create the authorized task goal with concrete acceptance criteria. Record ETA and observed process/checkpoint state.

Read [authorization roles](protocol/roles.md) and [self-contained maintenance](protocol/maintenance.md). Reserve a task number before registration, keep closed rows in the task archive, and append daily exchange through the shared helper.
