# 任务生命周期与巡检

[English](lifecycle.md)

研究负责人使用既有 Claude 身份，执行助手使用 GPT 身份；角色语气与工作权限分别维护。状态统一通过 `scripts/task_flow.py` 流转，每日周期任务的状态格按当天实际情况更新。

```
新建（负责人）→ 排队 → 在跑 ⇄ 卡住 → 已交 → 通过（负责人，归档）
                           ↑           ↘ 退回（负责人）↗
                   任意活跃状态 → 已停（负责人，归档）
```

| 命令 | 身份 | 必填内容 | 结果 |
| --- | --- | --- | --- |
| new | 负责人 | title、when；可选 node | 登记已有任务文件与开工条件 |
| start | 执行助手 | status，以 X/N 开头 | 从排队、卡住、退回开工，节点进入 doing |
| progress | 执行助手 | status，以 X/N 开头 | 更新在跑任务，0 ≤ X ≤ N，N > 0 |
| block | 两方 | wait，写清等谁做什么 | 登记依赖后继续其他已授权工作 |
| deliver | 执行助手 | evidence | 在跑、卡住、退回任务提交已有证据文件 |
| reject | 负责人 | reason | 退回已交任务，写清修改目标与验收标准 |
| accept | 负责人 | summary；可选 node-summary | 通过并归档，更新结果树 |
| stop | 负责人 | reason；可选 node-summary | 停止活跃任务并归档，更新结果树 |

负责人也可执行实现阶段的流转。负责人专属命令对 GPT 身份返回权限错误。脚本运行在可信本地工作区；`--by` 记录角色并检查流程权限，操作系统负责账号认证与文件访问。

## 使用

先写 `data/tasks/T001-example.md`，包含目标、起因、开工条件、适用的结果树节点、工作项、验收标准和约束。`--data-dir` 默认为 `data/`；证据路径相对该目录，节点标题对应唯一已有节点。

```sh
python scripts/task_flow.py new T001 --by Claude --title "比较方法" --when "输入齐全" --node "比较结果"
python scripts/task_flow.py start T001 --by GPT --status "0/6"
python scripts/task_flow.py progress T001 --by GPT --status "3/6 · 约18:00"
python scripts/task_flow.py block T001 --by GPT --wait "等研究负责人审阅输入"
python scripts/task_flow.py deliver T001 --by GPT --evidence attachments/T001/evidence.md
python scripts/task_flow.py accept T001 --by Claude --summary "六组比较已审阅" --node-summary "比较完成"
python scripts/flow_check.py --owner GPT --json
python scripts/patrol_log.py GPT "已处理事件并更新比较" --every 30
```

流转记录追加到 `attachments/task-flow.jsonl` 与任务文件。看板保留四个既有字段，更新行增加 ISO 时间；共享存储保留原字节。accept、stop 将任务移入 `tasks/archive.md`，清理活跃投影，节点任务全部归档后标为 done。负责人在研究任务结束后两天内写入 `findings.md`，结果卡片挂到节点的 `results`。

## 时限

| 条件 | 处理者 | 动作 |
| --- | --- | --- |
| 已交超过 2 小时 | 负责人 | 验收或退回 |
| 卡住超过 2 小时 | 负责人 | 拍板下一步或提出用户具体操作 |
| 在跑超过 3 小时未更新 | 执行助手 | 更新进度或登记依赖 |
| 退回超过 2 小时 | 执行助手 | 修改后重交 |
| 执行队列为空 | 负责人 | 安排资源任务和一条零算力任务 |
| 结果树与看板冲突 | 负责人 | 对齐状态与结论 |

依赖可写 `until MM-DD` 或 `到 MM-DD`，有效未来日期延后催办时限。检查输出包含稳定问题代码、负责人、任务与具体动作。

## 每次唤醒

GPT 读取 `attachments/night-watch/events.json`，处理事件、检查自己名下问题，在资源额度内开工，最后登记巡检。Claude 检查自己的流程问题、交流、用户讨论和资源观测，完成验收、拍板、排活后登记。命令为 `patrol_log.py 身份 一句话 --every 间隔分钟`。

“正在做”顶部显示两方的上次、下次、摘要和问题数。超过下次时间十五分钟时显示红色与“巡检超时”。实际唤醒由既有平台会话的调度工具负责。

## 持续执行与决定

已接任务的日常决定写入交流板，给负责人两个选项和建议，同时继续其他已授权工作。三十分钟后，可在既有授权和资源额度内执行可撤回的建议。登录、许可、凭据、付款、外部发送、公开发布、原始数据删除和个人决定继续按用户确认策略处理，具体用户操作需求写进讨论室。

交流标题采用带时区的 ISO 时间和任务编号，例如 `### 2030-01-01T10:00:00+00:00 · GPT → Claude · T001`；正文写选项和建议，负责人用相同任务编号回复。每日文件放在 `data/exchange/YYYY-MM-DD.md`，同时支持 `exchange.md`。守夜人负责观测和写事件，实际会话负责判断授权与执行。

负责人可用 `python scripts/flow_check.py --fix-tree --by Claude` 将关联任务全部归档的节点标为 done。
