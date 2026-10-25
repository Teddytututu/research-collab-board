# 图片素材

board/art 中的 PNG 包括角色头像、橘发角色贴纸、三人图集、15 张趴桌心情图，以及补全边缘后的贴纸。界面默认使用这些图片，项目原创 SVG 提供备用显示。部署后生成的个人角色图优先使用。

这些二创图片的权利归原角色与原作者，仅供个人非商业使用。代码的 MIT 协议适用于项目代码与原创 SVG；二创 PNG 图片另按其权利人许可使用。权利人提出要求时，项目维护者会删除对应素材。

表情回应默认使用 Unicode。public-emotes.json 保存 225 个 Bilibili 表情的名称与公开下载地址。首次运行时，部署助手询问用户是否下载这套表情；用户明确同意后执行 python scripts/install_emotes.py，将图片保存到本机 data/emotes/。选择跳过或下载失败时继续使用 Unicode；获准后再次执行同一命令可接续下载。data/ 属于已忽略的本机运行数据目录，下载图片随本机部署独立保存。

# Image assets

The PNG files under board/art contain character avatars, orange-haired character stickers, three-character atlases, fifteen desk mood illustrations and stickers with restored margins. They are the default artwork. Original project SVGs provide fallbacks, and a deployment's generated personal artwork takes priority.

Fan art remains the property of the original character owners and artists and is provided for personal, noncommercial use. The MIT code license covers project code and original project SVGs. Fan-art PNGs have separate rights and require the rights holders' permission for other uses. Maintainers will remove affected assets upon a rights holder's request.

Reactions use Unicode by default. public-emotes.json lists 225 Bilibili emotes and their public source URLs. On first run, the deployment assistant offers this optional pack; after the user's explicit agreement it runs python scripts/install_emotes.py to save the images in local data/emotes/. Skipping the pack or a download failure keeps Unicode available. An authorized repeat of the command resumes the download. Downloaded images remain in the ignored local runtime data/ directory.
