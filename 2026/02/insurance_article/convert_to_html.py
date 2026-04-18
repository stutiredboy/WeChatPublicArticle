import markdown
import os

md_path = '/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/02/insurance_article/article.md'
html_path = '/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/02/insurance_article/article.html'

with open(md_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 简单的转换，加入一些基础样式
html_content = markdown.markdown(text, extensions=['extra'])

full_html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
    body {{
        font-family: -apple-system-font, BlinkMacSystemFont, "Helvetica Neue", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", "Microsoft YaHei", Arial, sans-serif;
        line-height: 1.6;
        color: #333;
        padding: 20px;
        max-width: 677px;
        margin: 0 auto;
    }}
    h1 {{ font-size: 22px; font-weight: bold; margin-bottom: 20px; text-align: center; }}
    h2 {{ font-size: 18px; font-weight: bold; border-left: 4px solid #07c160; padding-left: 10px; margin-top: 30px; }}
    h3 {{ font-size: 16px; font-weight: bold; margin-top: 25px; color: #07c160; }}
    blockquote {{
        padding: 10px 15px;
        color: #666;
        background-color: #f8f8f8;
        border-left: 4px solid #ccc;
        margin: 20px 0;
        font-size: 14px;
    }}
    img {{
        max-width: 100%;
        height: auto;
        display: block;
        margin: 20px auto;
        border-radius: 8px;
    }}
    p {{ margin: 15px 0; }}
    strong {{ color: #d9453d; }}
</style>
</head>
<body>
{html_content}
</body>
</html>
"""

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(full_html)

print(f"HTML generated at {html_path}")
