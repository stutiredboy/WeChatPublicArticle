---
name: wechat-article-downloader
description: Download WeChat public articles from mp.weixin.qq.com links, convert to markdown, and save to local repository with images. Use when user provides a WeChat article URL starting with https://mp.weixin.qq.com. The skill handles HTTP requests with proper User-Agent, HTML-to-markdown conversion, image downloading, and organizes files in YYYY/MM/title/ structure matching existing repository patterns.
---

# WeChat Article Downloader

This skill enables downloading WeChat public articles, converting them to clean markdown format, and saving them to the local repository (`/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle`) with proper directory structure and image assets.

## When to Use

- User sends a message containing a URL starting with `https://mp.weixin.qq.com`
- You need to archive the article for future reference
- You want to convert the article to markdown for editing or analysis

## Quick Start

When you detect a WeChat article URL:

1. **Validate URL**: Ensure it starts with `https://mp.weixin.qq.com`
2. **Run the script**: Execute the download script with the URL as argument
3. **Check output**: Verify the article was saved correctly
4. **Notify user**: Report success/failure and location

Example command:
```bash
cd /home/tiredboy/.nanobot/workspace/skills/wechat-article-downloader/scripts
python3 download_wechat_article.py "https://mp.weixin.qq.com/s/example"
```

## Detailed Workflow

### 1. URL Validation
- Confirm URL starts with `https://mp.weixin.qq.com`
- Reject other domains to avoid unintended downloads

### 2. HTTP Request
- Set User-Agent: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36`
- Add referer: `https://mp.weixin.qq.com/`
- Handle redirects and timeouts (10-second timeout)
- Check HTTP status (200 OK required)

### 3. HTML Parsing
- Extract article title from `<meta property="og:title">` or `<title>`
- Extract publish date from `<meta property="article:published_time">` or current date
- Find main content container (common selectors: `#js_content`, `.rich_media_content`)
- **Known issue (JS 动态渲染)**: 新版公众号页面正文可能不在首屏 HTML 中（`#js_content` 存在但内容为空/隐藏），标准脚本此时只能保存标题+frontmatter、正文为空，不能直接依赖 html2text。可先尝试解析 `var content = ` 赋值或 `.rich_media_area_primary` 等替代容器，但完整正文以 Playwright/Chromium headless 渲染结果为准（Chromium headless shell 已装到 `~/.cache/ms-playwright`）。
- Remove scripts, styles, ads, and unnecessary elements

### 4. Markdown Conversion
- Use `html2text` with careful configuration:
  - Preserve links and images
  - Convert headings properly
  - Handle lists and code blocks
- Clean up extra whitespace and line breaks
- Ensure Chinese punctuation is preserved

### 5. Image Handling
- Find all `<img>` tags in the content
- Download each image to local `images/` directory
- Replace image URLs with relative paths (`images/filename.jpg`)
- Handle duplicate filenames with hashing
- Respect `data-src` attribute (common lazy-load pattern)

### 6. File Organization
- Determine year/month from publish date or current date
- Create directory structure: `YYYY/MM/title/`
- Sanitize title for filesystem safety (remove invalid characters)
- Save markdown file as `title.md`
- Save images to `images/` subdirectory
- Ensure UTF-8 encoding for all files

### 7. Repository Integration
- Target directory: `/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle` (remote: `github.com/stutiredboy/WeChatPublicArticle`)
- Check for existing articles to avoid duplicates
- Maintain consistent structure with existing articles

### 8. Git Auto-Commit & Push
- **Automatic version control**: After saving the article, the script automatically commits changes to git and pushes to remote repository
- **Commit message**: Includes article title for easy tracking
- **Push handling**: Automatically pulls latest changes if push is rejected, then retries push
- **Error resilience**: Git failures don't stop article download; errors are logged and reported
- **User configuration**: Git user email/name are automatically configured if not already set

## Script Usage

### Primary Script: `download_wechat_article.py`

Use system Python 3 (the skill's `.venv` is not set up; system Python 3.12.3 works directly):

```bash
python3 download_wechat_article.py "URL" [--output-dir PATH] [--verbose]
```

**Arguments:**
- `URL`: Required. WeChat article URL to download
- `--output-dir`: Base output directory (default: `/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle`)
- `--verbose`: Enable detailed logging

**Git Integration:**
- Automatically commits downloaded article to git repository and pushes to remote
- Configures git user if not already set
- Handles push rejection by pulling latest changes first
- Git failures are logged but don't cause script to fail

**Returns:**
- Exit code 0 on success, non-zero on error
- Prints saved file path on success
- Error messages on failure

### Dependencies

Dependencies are expected to be available in the system Python environment or installable via pip:
- `requests` (HTTP client)
- `beautifulsoup4` (HTML parsing)
- `html2text` (HTML-to-markdown conversion)
- `soupsieve` (CSS selector support)
- `lxml` or `html.parser` (BeautifulSoup backend)
- `playwright` + Chromium headless shell（JS 动态渲染文章正文提取的 fallback；shell 已装于 `~/.cache/ms-playwright`）

Install missing dependencies if needed:
```bash
pip install requests beautifulsoup4 html2text soupsieve lxml
```

Run via `python3 download_wechat_article.py`.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Invalid URL | URL doesn't match pattern | Check URL starts with https://mp.weixin.qq.com |
| Network error | Connection failed | Check internet, retry with longer timeout |
| 403 Forbidden | Blocked by WeChat | Ensure proper User-Agent and headers |
| No content found | HTML structure changed | Update CSS selectors in script |
| Hidden js_content / 正文为空 | Article loads body via JS（`#js_content` 存在但为空/隐藏），标准脚本只保存标题+frontmatter | 用 Playwright/Chromium headless 渲染页面后提取正文（shell 位于 `~/.cache/ms-playwright`），不要依赖 html2text 直接转换 |
| File system error | Permission or disk full | Check write permissions and disk space |

## Quality Standards

- **JS 渲染校验**: 下载后检查 `.md` 正文是否非空；若只有标题+frontmatter，判定为 JS 动态渲染文章，需用 Playwright/Chromium headless 重新渲染提取正文
- **Complete preservation**: All text content should be captured
- **Readable markdown**: Clean formatting with proper headings and lists
- **Functional images**: All images downloaded and linked correctly
- **Consistent structure**: Matches existing repository organization
- **Metadata retention**: Preserve title, date, and source URL in markdown frontmatter

## Integration with Agent

When you receive a WeChat article URL:

1. **Acknowledge**: "I'll download this WeChat article and save it to your repository."
2. **Execute**: Run the script and monitor for errors
3. **Verify**: Check the output directory for the saved files
4. **Report**: Tell the user where the article was saved and any issues encountered

Always test with a sample URL if uncertain about script functionality.

## Maintenance

- Periodically test with recent WeChat articles to ensure compatibility
- Update CSS selectors if WeChat changes its HTML structure
- Monitor for changes in anti-scraping measures
- Keep dependencies updated

## Examples

### Successful Download
```
Input: https://mp.weixin.qq.com/s/abc123
Output: Saved to /home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/02/示例文章标题/示例文章标题.md
Git: Added to git, committed, and pushed to remote repository
```

### Error Handling
```
Input: https://example.com/not-wechat
Output: Error: URL must start with https://mp.weixin.qq.com
```

### Image Processing
```
Found 12 images, downloaded 12/12
Image links converted to relative paths
```
