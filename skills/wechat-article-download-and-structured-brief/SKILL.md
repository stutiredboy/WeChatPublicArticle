---
name: wechat-article-download-and-structured-brief
description: Download a WeChat public article to the user's local WeChatPublicArticle archive, verify markdown/images were saved correctly, then provide a structured brief focused on 内容要点、背景、建议如何、补充判断, plus the final saved path.
---

# WeChat Article Download and Structured Brief

## When to use

- 用户发送 `https://mp.weixin.qq.com` 文章链接
- 用户希望你直接代做下载落盘，而不是只讲方法
- 需要校验 Markdown 与图片是否已正确保存
- 用户还希望拿到文章解读，而不只是文件路径
- 适合输出“内容要点 / 背景 / 建议如何 / 补充判断”的结构化总结

## Steps

1. 先用一句话确认已开始处理，避免用户等待时不知道进度。
2. 优先复用现有能力：如 `wechat-article-downloader` 工作流、现成脚本，或环境中的 `exec` 调用既有下载工具；不要重复造轮子。
3. 将文章保存到：`/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/YYYY/MM/文章标题/`。
4. 下载完成后，用 `read_file` 检查主 `.md` 文件是否存在、非空、正文基本完整。
5. 如流程返回图片目录或图片数量，继续核对 `images/` 是否已生成；若当前工具不能直接列目录，就明确说明图片校验依据来自脚本输出。注意：下载脚本 frontmatter 的 `images` 字段统计的是图片引用次数而非唯一图片文件数，汇总图片数时必须去重并说明（如 13 次引用去重后 7 张）。
6. 基于落盘后的 Markdown 提炼文章内容，抓四部分：
   - 内容要点：文章到底说了什么
   - 背景：这篇文章为什么会出现，相关上下文是什么
   - 建议如何：作者或你认为对读者最有用的行动建议是什么
   - 补充判断：文章立场、风险提示、样本偏差、时效性约束或营销倾向等需要提醒用户的判断
7. 最后同时返回：保存目录、Markdown 路径、图片情况、校验结果、结构化解读。

## Output format

先给结果，再给解读。推荐格式：

- 结果：成功 / 失败
- 标题：...
- 目录：...
- Markdown：...
- 图片：无 / 有（N 张，若数量可确认）
- 校验：已完成 / 部分完成 / 失败

然后输出：

### 内容要点
- ...
- ...

### 背景
- ...
- ...

### 建议如何
- ...
- ...

### 补充判断
- 如无必要可省略；有争议、营销倾向、样本偏差、时效性强时应补充

## Tool guidance

- 用 `read_file` 校验生成的 Markdown 内容，并据此做解读。
- 用 `write_file` 仅在需要创建说明文件或技能文件时使用，不替代下载流程。
- 若环境提供 `exec`，优先调用现有下载脚本并读取输出日志。
- 若环境提供 `web_search`，仅用于补背景或核对公开信息，不替代本地落盘校验。
- 若已有 `wechat-article-download-and-verify` 或 `wechat-article-downloader` 技能，可把它们视为下游能力复用。

## Quality bar

- 不要只复述标题，要提炼核心论点。
- “背景”不能空泛，要解释事件、行业、人物或时间点。
- “建议如何”必须面向自然人可执行，避免纯口号。
- 如果文章内容明显不足以支撑强结论，要直接说明证据边界。
- 用户对等待敏感，过程中至少给一次真实进度更新。

## Example

### Example: success

用户：帮我下载并看看这篇公众号文章 https://mp.weixin.qq.com/s/abc

过程回复：
- 已开始处理，先下载正文并校验落盘。
- 下载完成，正在检查 Markdown 和图片，并整理内容解读。

最终输出：
- 结果：成功
- 标题：某篇文章
- 目录：`/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/04/某篇文章/`
- Markdown：`/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/04/某篇文章/某篇文章.md`
- 图片：有（8 张）
- 校验：已完成

### 内容要点
- 文章先讲某个行业现象，再拆成 3 个原因。
- 作者重点强调真正的问题不在工具，而在组织流程。

### 背景
- 这篇文章出现于 AI 工具快速渗透期，行业里对效率和风险都很敏感。
- 作者引用的案例主要来自近期舆论热点，因此传播性强，但也可能带有样本偏差。

### 建议如何
- 如果你是普通读者，重点看作者提出的问题框架，而不是直接照搬结论。
- 如果你要落地实践，先做小范围验证，再决定是否全面采用。

### 补充判断
- 文章有启发，但结论偏经验型；若用于决策，建议再补一手数据源。

### Example: failure

- 结果：失败
- 标题：未知
- 目录：未生成
- Markdown：未生成
- 图片：未知
- 校验：失败

### 建议如何
- 链接可能失效或下载流程异常；应重新抓取一次，并检查脚本输出与目录权限。
