---
name: wechat-article-download-and-verify
description: Download WeChat public articles into the user's WeChatPublicArticle YYYY/MM/title/ archive, verify that markdown and image files were written correctly, and report progress plus final saved paths succinctly. Use when the user provides an mp.weixin.qq.com article URL and expects a fast status update and a verified local result.
---

# WeChat Article Download and Verify

## When to use

- 用户提供 `https://mp.weixin.qq.com` 文章链接
- 目标是下载到本地归档，而不只是摘要或浏览
- 需要校验落盘结果是否完整
- 用户对等待敏感，需要尽快反馈进度

## Steps

1. 先快速回复一句已开始处理，避免长时间静默。
2. 优先使用现有的 `wechat-article-downloader` skill 或现成脚本，不要重复发明下载流程。下载命令：
   `cd ~/.nanobot/workspace/skills/wechat-article-downloader/scripts && python3 download_wechat_article.py "<URL>"`（系统无 `python`，一律用 `python3`）。
3. 将文章保存到仓库：`/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/YYYY/MM/文章标题/`。
4. 下载完成后，用 `read_file` 检查生成的 `.md` 是否存在且非空。
5. 如流程返回了图片目录或图片数量，继续核对 `images/` 是否已生成，并记录图片数量；若当前可用工具无法直接列目录，就明确说明“已由脚本报告生成 images/，数量以脚本输出为准”。
   - 注意：脚本 frontmatter 的 `images` 字段统计的是图片引用次数而非唯一图片文件数（如 13 次引用去重后实为 7 张），报告图片数量时必须按 `images/` 目录实际文件去重。
6. 提炼最终结果：标题、保存目录、主 Markdown 路径、是否有图片、是否成功。
7. 若失败，直接说失败点（如链接无效、抓取失败、写入失败、校验失败）和下一步动作。

## Rendering fallbacks

- 正文为空（`#js_content` 存在但无文本，新版页面由 JS 动态渲染）：用 Chromium headless shell 渲染后提取正文，shell 位于 `~/.cache/ms-playwright`；环境未安装 playwright / cairosvg Python 模块，直接调用该二进制即可。已验证命令：`/home/tiredboy/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome --headless --no-sandbox --disable-gpu --virtual-time-budget=12000 --dump-dom "<URL>"`，再用正则去标签取文本；`--virtual-time-budget` 控制等待 JS 渲染的毫秒数。
- 脚本报告 0 张图片但正文含插图：插图可能是内联 SVG；用 Chromium headless 将 SVG 渲染成 PNG，写入 `images/` 并在 Markdown 中原位置回填引用。
- 报告图片数量始终按 `images/` 目录实际文件去重。

## OCR fallback for image-only articles

- 情形：方案/文档分享类公众号文章的正文是纯扫描页图片，落盘的 `.md` 只有导语文字；先确认图片为大尺寸文档扫描页（如 1080×1398、数十页）。
- 环境已装 `/usr/bin/tesseract`，含 `chi_sim`/`eng`/`osd` 语言包。逐页识别：`tesseract images/x.jpg out -l chi_sim --psm 6`——文字页识别良好，架构图/示意图页基本乱码，可跳过或只留图。
- 把各页输出合并写回同一目录的 `正文OCR文本（自动提取）.md`；需要 PDF 时用 PIL 按原图顺序合成（保持原分辨率，成品约十几 MB 量级）。
- 交付时必须声明：OCR 文本为机器提取、未校对，架构图内容不可靠，原始扫描页仍是唯一权威副本。

## Progress reporting

- 开始后尽快给一次状态：如“已开始下载，正在抓取正文”。
- 如果下载或转换耗时，补一句短进度：如“还在处理图片/落盘校验中”。
- 不要写空泛套话；每次进度都要说明当前阶段。

## Output format

成功时用简洁要点：

- 结果：成功/失败
- 标题：...
- 目录：...
- Markdown：...
- 图片：无 / 有（N 张，若数量可确认）
- 备注：是否已完成校验

失败时用简洁要点：

- 结果：失败
- 阶段：抓取 / 转换 / 写入 / 校验
- 原因：...
- 建议下一步：...

## Tool guidance

- 用 `read_file` 校验生成的 Markdown 内容。
- 用 `write_file` 仅在需要补充说明文件或创建技能文件时使用，不用于替代既有下载脚本。
- 若环境提供 `exec`，可用于调用现有下载脚本与检查输出。
- 若环境提供 `web_search`，仅用于辅助确认文章信息，不替代下载。

## Example

### Example: success

用户：下载这个公众号文章 https://mp.weixin.qq.com/s/abc

响应过程：
- 已开始下载，先抓取正文并落盘。
- 已完成下载，正在校验 markdown 和图片。

最终输出：
- 结果：成功
- 标题：某篇文章
- 目录：`/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/04/某篇文章/`
- Markdown：`/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/04/某篇文章/某篇文章.md`
- 图片：有（12 张）
- 备注：已完成落盘校验

### Example: failure

- 结果：失败
- 阶段：校验
- 原因：脚本报告写入成功，但未找到生成的 Markdown 文件
- 建议下一步：重新执行下载脚本，并检查输出目录权限
