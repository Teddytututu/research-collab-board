# Six quota scenarios

| Scenario | Claude r/T | GPT r/T | Claude min | GPT min | Claude/GPT share | Handoff |
| --- | --- | --- | ---: | ---: | --- | --- |
| Both plentiful | 0.7/24 | 0.7/24 | 68.57 | 68.57 | 0.50/0.50 | Claude |
| One tight | 0.15/24 | 0.7/24 | 240 | 68.57 | 0.20/0.80 | GPT |
| One exhausted | 0.03/24 | 0.7/24 | paused | 68.57 | 0.20/0.80 | GPT |
| Just reset | 0.99/5 | 0.7/24 | 20 | 68.57 | 0.80/0.20 | Claude |
| User mention | 0.03/24 | 0.7/24 | 20 | 68.57 | 0.20/0.80 | GPT |
| Long idle | 0.15/24 | 0.15/24 | 240 | 240 | 0.50/0.50 | Claude |

The first five rows have one active task per assistant; the last row is idle. Mention and low-quota rules take precedence over routine intervals.
