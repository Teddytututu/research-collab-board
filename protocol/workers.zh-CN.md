# 多工人协作

主线程负责分派、整合与交付；工人每次领取一个任务，完成并释放后再领取下一项。研究工人持续处理已派实验，网页、学习和打包按各自文件范围推进。

## 领取与心跳

使用 `python scripts/workers.py claim TASK-ID --worker W1 --scope folder/ --allowed-workers 2 --eta "预计完成时间、把握与依据"` 领取。领取工具独占创建任务锁，同时检查工人、任务、并行额度与文件范围。

工人读取返回的 token，每十分钟执行 `python scripts/workers.py heartbeat TASK-ID --token TOKEN`。三十分钟心跳过期后，调度可归档旧锁并重派；新 token 接管写入，历史记录保留。每次开始写入前先校验当前 token。

## 文件范围

领取时声明准确文件或目录。相同路径、父子目录及目录内文件视为交叉范围，由调度安排先后执行。工人负责自己的结果和过程文件。

共享状态用 `board.storage.update_json(data_dir, relative_path, transform)` 按字段更新；看板用 `board.workers.update_board(data_dir, task, status)` 改对应行；交流及任务结果用 `board.workers.append_shared(data_dir, relative_path, text)` 追加。工具跨进程加锁，写前保留原字节。

## 并行与额度

工人数量为额度允许数量、三人常规上限和本机 CPU 余量三者的最小值。额度估算复用每小时预算与单次成本：先预留未来一天预算的三成，再按单次成本计算人数；比例低于一成或普通调用关闭时，派发数量归零。现有活任务按当前授权完成手头工作。

部署可在用户明确授权后，为有限时间窗口配置最多六名工人；有效数量同时受CPU余量约束。配置位于 `data/attachments/state.json` 的 `worker_pool_policy`，其中 `temporary_override` 包含 `authorized_by: "user"`、改写的授权摘要 `authorization`、`starts_unix`、`expires_unix` 与 `max_workers`，CPU限制使用 `cpu_slots`。`board.workers.effective_worker_limit` 在新领取时应用窗口，到期回到常规人数，已有领取继续完成授权范围。包内提供一般机制与虚构回归用例，各部署自行填写授权和时间。

GPU占用另算物理卡，生成、评分和加载合计。特殊窗口采用用户明确的窗口额度，窗口外采用常规额度；部署的保护卡、共享例外、TTY额度和容量线均按当前项目规则执行。

## 目标与接续

获用户授权的长任务创建独立 goal，写清成果、完成条件、可检查结果与需人工决定的边界。主线程保留实验持续推进目标，研究工人复用服务器控制器、原断点和物理锁。

进程按账号、创建身份和完整命令核对。活进程继续运行；异常退出查原因后修复，临时资源恢复后继续。首次换卡先核对同种子回放；原始样本、种子、模型和评分口径由研究负责人审核。

## 交付

领取后三十分钟内写预计时间、把握和依据；依赖任务采用条件式预计时间。延期更新原因和新时间，完成时记录预计与实际用于校准。

工人在交流板标题标工人编号，正文最多三句。任务结果最多十行，进度、进程身份、断点与长记录集中到 data/attachments。面向用户的讨论室只发结果及必要决定。

使用 `python scripts/workers.py release TASK-ID --token TOKEN --status 待验收` 交回任务；研究审核与最终验收沿现有看板完成。

本仓库默认数据目录为 data/，锁记录在 data/attachments/locks/。领取命令的 --allowed-workers 采用调度按实际额度和CPU余量算出的值，示例中的2是演示许可值。board.workers.quota_capacity提供对应额度计算。共享工具的 relative_path 是 data/ 内的相对路径，state使用 attachments/state.json，文档使用 board.md 与 exchange.md。


当前执行采用最简固定队列、完整X/N进度、每任务每小时一条结果消息与两至三名工人。具体五条与十一项执行条件见execution.zh-CN.md。

## 生命周期任务

通过 `scripts/task_flow.py` 登记的任务，将工人身份、范围和心跳与任务状态分别保存。释放工人租约表示交接给派发者；提交证据与负责人验收通过生命周期命令完成。旧租约释放后，已归档任务继续保持关闭。既有独立租约保留兼容行为。
