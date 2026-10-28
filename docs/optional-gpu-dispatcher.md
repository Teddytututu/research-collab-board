# Optional: GPU slot dispatcher / 可选能力：卡位自动调度

Not part of the board. An assistant may set this up on a shared GPU server when the owner asks for it. It solves one problem: an approved experiment waits while a card sits idle, or our job finishes and someone else takes the card before the next one starts.

## Shape

A small process on the GPU server, started with `nohup`, wakes every 60 seconds:

1. Read `nvidia-smi`: memory, processes and owning user per card. A free card has under 1 GiB in use and no processes.
2. Apply the agreed limit. Example rule: at most 3 of our cards while anyone else is using the server, otherwise 5 by day and 7 between 00:00 and 08:00, with night jobs expected to finish before 08:00. Exclude cards reserved for other people.
3. Look in `queue/`, one JSON spec per approved job: `task`, `priority`, `cmd`, `cwd`, `mem_gb`, `disk_gb`, `est_hours`, `approved` (who approved and when). Take the highest priority, oldest first.
4. If a card is free, the limit allows it and the disk has `disk_gb` spare, start it with `CUDA_VISIBLE_DEVICES=<card> nohup <cmd>`, move the spec to `running/` with process id, card and start time.
5. When the process exits, move the spec to `done/` or `failed/` with the exit code. Retry a failed job at most once.
6. Write `status.json`: who holds each card, what of ours is running, what is still queued.

The night watch on the owner's computer reads `status.json` over one SSH call and turns it into events: job done, job failed, free cards with an empty queue (the research lead should queue the next approved job), low disk.

## Rules

- **Start only, never stop.** The dispatcher never ends any process, including ours, and never touches other users' files.
- Only specs the research lead approved enter `queue/`.
- The executor's job shrinks to two things: put approved specs in `queue/`, handle `failed/`.
- Pull back results, scores, configs and logs; leave large intermediate states on the server unless they are needed, since they can be recomputed from the same seeds.

Keep the server name, user name, card numbers and limits in the deployment's own configuration, outside this repository.
