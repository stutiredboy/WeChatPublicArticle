import os

md_path = '/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/02/insurance_article/article.md'
html_path = '/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/02/insurance_article/article.html'

with open(md_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

html_body = ""
in_quote = False

for line in lines:
    line = line.strip()
    if not line:
        continue
    
    # Header 1
    if line.startswith('# '):
        html_body += f"<h1>{line[2:]}</h1>\n"
    # Header 2
    elif line.startswith('## '):
        html_body += f"<h2>{line[3:]}</h2>\n"
    # Header 3
    elif line.startswith('### '):
        html_body += f"<h3>{line[4:]}</h3>\n"
    # Blockquote (Summary)
    elif line.startswith('> '):
        if not in_quote:
            html_body += "<blockquote>\n"
            in_quote = True
        html_body += line[2:] + "<br>\n"
    # Image
    elif line.startswith('!['):
        alt = line[line.find('[')+1:line.find(']')]
        src = line[line.find('(')+1:line.find(')')]
        html_body += f'<img src="{src}" alt="{alt}">\n'
    # List
    elif line.startswith('* '):
        html_body += f"<li>{line[2:]}</li>\n"
    # Paragraph
    else:
        if in_quote:
            html_body += "</blockquote>\n"
            in_quote = False
        # Bold handling
        line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
        html_body += f"<p>{line}</p>\n"

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
    li {{ margin: 10px 0; }}
</style>
</head>
<body>
{html_body}
</body>
</html>
"""

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(full_html)
