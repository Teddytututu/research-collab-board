# Research report writing / 研究报告写法

Read [SKILL.md](SKILL.md), or the [Chinese guidance](references/writing.zh-CN.md), when drafting or revising a research report. Tell the assistant: “Read skills/research-report-writing/SKILL.md and use it for this report.” Direct reading works with either assistant.

写报告或改报告时，让助手读取 [SKILL.md](SKILL.md)，中文规则见[研究报告写法](references/writing.zh-CN.md)。可直接说：“按 skills/research-report-writing/SKILL.md 写这份报告。”两位助手均可通过直接读取使用。

## Optional installation / 可选安装

Copy this whole folder into a skill directory supported by your assistant: `.claude/skills/research-report-writing/` for project-local Claude Code use, or `.agents/skills/research-report-writing/` for project-local Codex use. Reload the assistant's skills after copying. Keep the folder's references and templates together.

也可把整个文件夹复制到助手支持的技能目录：Claude Code 项目内使用 `.claude/skills/research-report-writing/`，Codex 项目内使用 `.agents/skills/research-report-writing/`。复制后重新加载技能，规则、引用资料与模板一起保留。

## Offline HTML helper / 离线 HTML 工具

[templates/report_helpers.py](templates/report_helpers.py) provides SVG charts, JPEG embedding and MathML using the Python standard library. Run it from a chosen temporary output directory to create `report.html`; replace the illustrative data with your evidence and inspect the rendered page.

[templates/report_helpers.py](templates/report_helpers.py) 用 Python 标准库生成 SVG 图、内嵌 JPEG 与 MathML。在选定的临时输出目录运行，得到 `report.html`；以实际研究证据替换演示数据，并检查渲染页面。

The skill's instructions, Chinese reference and helper are self-contained in this folder. Project code and documentation follow the source repository's MIT license; image rights follow the image assets' own terms.

技能规则、中文参考与工具均包含在本文件夹。项目代码与文档沿用源仓库 MIT，图片素材沿用其独立权利条款。
