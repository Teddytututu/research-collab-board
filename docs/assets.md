# Bundled artwork and optional replacements

Character PNGs ship with the project and are ready on first run. Their fan-art rights are described in [image assets](../assets/README.md). The original SVG fallback set below is MIT licensed. Reactions use Unicode by default; the optional public pack is downloaded only after the user's explicit agreement, into local ignored `data/emotes/`.

包内角色 PNG 首次运行即可使用，二创权利见[图片素材](../assets/README.md)。下列原创 SVG 备用图采用 MIT。表情回应默认 Unicode，可选公开表情包经用户明确同意后下载到本机已忽略目录 `data/emotes/`。

Every bundled SVG below is an original geometric illustration created for this project, licensed under MIT.

| File | Source | License |
| --- | --- | --- |
| board/art/avatar-claude.svg | Original project SVG | MIT |
| board/art/avatar-gpt.svg | Original project SVG | MIT |
| board/art/avatar-user.svg | Original project SVG | MIT |
| board/art/claude-calm.svg | Original project SVG | MIT |
| board/art/claude-shy.svg | Original project SVG | MIT |
| board/art/claude-smile.svg | Original project SVG | MIT |
| board/art/claude-surprised.svg | Original project SVG | MIT |
| board/art/claude-teary.svg | Original project SVG | MIT |
| board/art/claude-wink.svg | Original project SVG | MIT |
| board/art/gpt-calm.svg | Original project SVG | MIT |
| board/art/gpt-shy.svg | Original project SVG | MIT |
| board/art/gpt-smile.svg | Original project SVG | MIT |
| board/art/gpt-surprised.svg | Original project SVG | MIT |
| board/art/gpt-teary.svg | Original project SVG | MIT |
| board/art/gpt-wink.svg | Original project SVG | MIT |
| board/art/user-calm.svg | Original project SVG | MIT |
| board/art/user-shy.svg | Original project SVG | MIT |
| board/art/user-smile.svg | Original project SVG | MIT |
| board/art/user-surprised.svg | Original project SVG | MIT |
| board/art/user-teary.svg | Original project SVG | MIT |
| board/art/user-wink.svg | Original project SVG | MIT |
| board/reactions/care.svg | Original project SVG | MIT |
| board/reactions/celebrate.svg | Original project SVG | MIT |
| board/reactions/done.svg | Original project SVG | MIT |
| board/reactions/idea.svg | Original project SVG | MIT |
| board/reactions/review.svg | Original project SVG | MIT |
| board/reactions/smile.svg | Original project SVG | MIT |

The persona JSON files contain prompts for the avatar and six expressions. When the user asks to replace the bundled images, a deployment may use an image-capable assistant to generate a consistent original set, then save validated PNG or original SVG files under data/attachments/generated/Claude/ or GPT/. Generated replacements stay in runtime data; the original placeholders remain available. The six reaction illustrations are original project SVGs.

用户提出换图需求后，助手可按人设 JSON 中的头像与六种表情提示词生成替换图，存入 `data/attachments/generated/Claude/` 或 `GPT/`，同时保留原有图片。生成格式采用 PNG 或原创 SVG。

## Additional mood placeholders

| File | Source | License |
| --- | --- | --- |
| board/art/claude-cheer.svg | Original project SVG | MIT |
| board/art/claude-confused.svg | Original project SVG | MIT |
| board/art/claude-happy.svg | Original project SVG | MIT |
| board/art/claude-heart.svg | Original project SVG | MIT |
| board/art/claude-panic.svg | Original project SVG | MIT |
| board/art/claude-pout.svg | Original project SVG | MIT |
| board/art/claude-proud.svg | Original project SVG | MIT |
| board/art/claude-reading.svg | Original project SVG | MIT |
| board/art/claude-sleepy.svg | Original project SVG | MIT |
| board/art/claude-thinking.svg | Original project SVG | MIT |


## Runtime artwork creation record

For each optionally generated set, append its role, actual creator or tool, original prompt, file basenames, format and license or usage basis to local `data/attachments/generated/artwork-record.jsonl`. Keep deployment-specific provenance in that runtime record. A compact view may use this shape:

| Role | Creator / capability | Prompt | Files | Format | Usage basis |
| --- | --- | --- | --- | --- | --- |
| Example assistant | Actual generator or SVG author | Original deployment prompt | avatar plus six expressions | PNG or SVG | Original creation / deployment's chosen terms |

Runtime file selection accepts `.png` and `.svg` for the same basename and chooses the latest modification time (PNG wins an exact tie). Mood aliases map the extended header expressions to related basic generated expressions. Original source SVG placeholders retain their MIT license.

## Bundled character artwork

The default character PNGs, atlases and fifteen desk moods live in board/art/. See [assets/README.md](../assets/README.md) for their separate rights, personal noncommercial usage and removal policy. Original SVGs remain available as fallbacks. Unicode reactions work immediately. After the user's explicit agreement to the optional pack of about 225 public emotes, the deployment assistant runs `python scripts/install_emotes.py` to download images into ignored local `data/emotes/`. Skipping the pack or a download failure keeps Unicode available.

默认角色 PNG、图集与十五种趴桌心情图位于 `board/art/`，按[素材说明](../assets/README.md)中的独立权利、个人非商业使用及权利人移除条款使用；原创 SVG 保留为备用。Unicode 表情开箱可用。用户明确同意下载约 225 张公开表情后，部署助手执行 `python scripts/install_emotes.py`，保存到本机 `data/emotes/`；用户跳过或下载失败时继续使用 Unicode。
