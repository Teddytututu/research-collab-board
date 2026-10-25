# 看板与交流维护

维护工具全部位于本仓库，运行资料位于 data/，使用与工人相同的跨进程工作区锁。

```sh
python scripts/task_number.py --title "一项具体工作"
python scripts/maintenance.py board
python scripts/maintenance.py exchange
```

任务号工具同时扫描 tasks/ 下的任务文件、board.md、tasks/archive.md和既有编号预留，以独占文件预留下一个T编号。调度随后登记任务及范围，工人再领取。

看板维护只把已通过、取消或归档的任务行转入 data/tasks/archive.md；正在执行和待验收任务继续留在原位。归档保留原行，源文件写前保留完整旧字节，重复执行保持已有归档。

交流维护按带日期的三级标题分块，代码围栏中的相同标题作为原消息内容保留。原全文完整保存到 data/exchange/history-<hash>.md，各日记录写入 data/exchange/YYYY-MM-DD.md，exchange.md硬链接到当天文件。使用 board.workers.append_shared追加时同时更新当日别名，完整旧字节进入history。源文件与日文件位于同一支持硬链接的文件系统。

角色与授权边界见[协作分工](roles.zh-CN.md)，领取与共享写入见[多工人协议](workers.zh-CN.md)。任务页面的进一步ETA显示可在对应界面版本完成后更新，当前源包保留状态层的预计时间与依据。
