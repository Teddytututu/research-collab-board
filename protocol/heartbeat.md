# Event-first heartbeat

[简体中文](heartbeat.zh-CN.md) · [Night-watch setup](../docs/night-watch.md)

The night watcher is an ordinary script that observes progress and writes actionable events. It updates routine counts directly. Assistant reasoning starts from an event that needs handling.

1. **Read `data/attachments/night-watch/events.json` first**, using its `events` list. With a custom data directory, use the same relative path under that directory. An absent file or an empty event set means a quiet end to this wake. A malformed or unreadable file is a watcher failure: surface its concrete cause once and preserve it for diagnosis.
2. For an actionable event, read only its related task, the relevant current instructions and the latest **20 exchange entries**. Resume the accepted configuration and existing session. Read additional evidence only as the event requires.
3. Complete independent authorized recovery or implementation. Claude decides changes to research design; the user decides consequential resource, account and publication choices. Continue independent work while a decision is pending.
4. Record the concrete result and acknowledge the handled event with `python scripts/night_watch.py --project-root . --ack EVENT_ID`; use the installation's `--data-dir` when customized. Preserve unrelated or newer events. A notification alone leaves the event pending while its action remains open. Deduplicate repeated notifications for the same condition. See the [night-watch interface](../docs/night-watch.md) for the event lifecycle.

## Notification conditions

| Event | Action |
| --- | --- |
| A task completes | Collect its final result and notify with the useful outcome. |
| A process exits early or progress stalls | Inspect task evidence, recover within authorization, and report the concrete failure or recovery result. |
| Eligible resources become available with queued work | Resume accepted work within the deployment's resource allowance; update progress locally. |
| Capacity crosses the configured protection line | Apply capacity protection, retain existing outputs, and notify with the required choice. |
| Research or user decision required | State concrete options and a recommendation to the decision owner. |
| Healthy run, unchanged condition, or ordinary progress | Update local progress through the watcher and finish quietly. |

## First installation and scheduling

Follow [night-watch setup](../docs/night-watch.md) for Windows task registration with `schtasks`, the macOS/Linux cron example, dry runs and manual fallback commands. Apply registration under current installation authorization. A registration failure produces the manual command while independent setup continues. Keep night-watch registration, board login startup and provider-native assistant wakes as separate controls. Forward events to the existing assistant session through the deployment's configured integration.

Keep check output and diagnostic details in project-local runtime records. Use [writing rules](writing.md) for user-facing results and decisions.
