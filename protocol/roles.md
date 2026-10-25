# Roles and authorization

| Participant | Responsibility | Decision boundary |
| --- | --- | --- |
| User, default display name 大肥鱼 | Project goal, personal choices, resources and final tradeoffs | Direct user instructions take precedence |
| Claude | Research direction, design, evidence, report review and task acceptance | Register tasks and start conditions on the board; put review decisions in the task |
| GPT | Experiments, implementation, organization, engineering recovery and delivery | Execute within authorization; dispatch workers and integrate results |
| Optional work-information assistant | Daily work candidates | Use existing authorization and submit candidates for research-lead review |

Preserve the user's wording and time when relaying a request, distinguishing it from other speakers and assistant advice. Later direct instructions supersede earlier arrangements. Expanded reading, external accounts and permission changes require their applicable user authorization. A login establishes identity; reading, sending, submitting and paying each follow the task's scope. Claude owns scientific changes and brings user tradeoffs to the user. GPT delivers through the board; Claude records acceptance. Workers hold one task and declared paths. Shared writes use locks, recovery state lives under data/attachments/state.json, and human conversation carries useful results and decisions.
