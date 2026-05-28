#!/usr/bin/env python3
"""
Convert the MEM thesis guide markdown to a SCUT-themed HTML wiki.
Usage: python3 build_wiki.py
"""

import markdown
import re
import os

SKILL_DIR = os.path.expanduser("~/.claude/skills/scut-mem-html-slide")
SRC = os.path.join(os.path.dirname(__file__), "非全日制MEM毕业论文实战指南.md")
DST = os.path.join(os.path.dirname(__file__), "非全日制MEM毕业论文实战指南.html")

# ---------- read logos ----------
with open(os.path.join(SKILL_DIR, "assets", "logos-snippet.js"), "r") as f:
    logos_js = f.read()
logo_scut_match = re.search(r'const LOGO_SCUT\s*=\s*"([^"]+)"', logos_js)
logo_cnsba_match = re.search(r'const LOGO_CNSBA\s*=\s*"([^"]+)"', logos_js)
LOGO_SCUT = logo_scut_match.group(1) if logo_scut_match else ""
LOGO_CNSBA = logo_cnsba_match.group(1) if logo_cnsba_match else ""

# ---------- read and convert markdown ----------
with open(SRC, "r", encoding="utf-8") as f:
    md_text = f.read()

# Convert markdown to HTML
extensions = [
    "tables",
    "fenced_code",
    "codehilite",
    "toc",
    "sane_lists",
]
extension_configs = {
    "toc": {
        "permalink": False,
        "toc_depth": "2-3",
    },
    "codehilite": {
        "css_class": "code-block",
        "guess_lang": False,
    },
}

md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
body_html = md.convert(md_text)
toc_html = md.toc  # auto-generated TOC

# ---------- post-process ----------

# Convert checkbox lists in <li>
body_html = re.sub(
    r'<li>\s*\[ \]\s*',
    '<li class="checklist-item"><input type="checkbox" disabled> ',
    body_html,
)
body_html = re.sub(
    r'<li>\s*\[x\]\s*',
    '<li class="checklist-item checked"><input type="checkbox" checked disabled> ',
    body_html,
    flags=re.IGNORECASE,
)

# Convert checkbox lines that ended up inside <p> tags (markdown didn't make them lists)
# Pattern: "- [ ] text" as raw text within <p>
def convert_checkbox_paragraphs(html):
    """Find <p> blocks containing '- [ ]' or '- [x]' lines and convert to proper checklists."""
    def replacer(match):
        content = match.group(1)
        # Check if it contains checkbox patterns
        if not re.search(r'- \[[ x]\]', content, re.IGNORECASE):
            return match.group(0)
        lines = re.split(r'<br\s*/?>|\n', content)
        result_parts = []
        list_items = []
        for line in lines:
            cb_match = re.match(r'\s*-\s*\[\s*\]\s*(.*)', line)
            cbx_match = re.match(r'\s*-\s*\[x\]\s*(.*)', line, re.IGNORECASE)
            if cb_match:
                list_items.append(f'<li class="checklist-item"><input type="checkbox" disabled> {cb_match.group(1).strip()}</li>')
            elif cbx_match:
                list_items.append(f'<li class="checklist-item checked"><input type="checkbox" checked disabled> {cbx_match.group(1).strip()}</li>')
            else:
                if list_items:
                    result_parts.append('<ul class="checklist">' + '\n'.join(list_items) + '</ul>')
                    list_items = []
                stripped = line.strip()
                if stripped:
                    result_parts.append(f'<p>{stripped}</p>')
        if list_items:
            result_parts.append('<ul class="checklist">' + '\n'.join(list_items) + '</ul>')
        return '\n'.join(result_parts)
    return re.sub(r'<p>(.*?)</p>', replacer, html, flags=re.DOTALL)

body_html = convert_checkbox_paragraphs(body_html)

# Add classes to tables
body_html = body_html.replace("<table>", '<table class="data-table">')

# Wrap blockquotes with class
body_html = body_html.replace("<blockquote>", '<blockquote class="info-box">')

# Style strikethrough
body_html = re.sub(r'~~(.+?)~~', r'<del>\1</del>', body_html)

# Add IDs to h2/h3 for navigation (toc extension already does this, but ensure)
# Wrap each h2 section for better styling
# Add section dividers before h2
body_html = re.sub(
    r'<h2([^>]*)>',
    r'<div class="section-divider"></div><h2\1>',
    body_html,
)

# ---------- build sidebar TOC from toc_html ----------
# The toc extension generates a nested <div class="toc"><ul>...</ul></div>
# We'll use it directly but restyle it

# ---------- assemble HTML ----------
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>非全日制 MEM 工程管理硕士毕业论文实战指南</title>
<style>
/* ===== SCUT MEM Wiki Theme ===== */
:root {{
  --primary: #2154a6;
  --primary-dark: #204285;
  --accent: #1a4280;
  --text-dark: #303133;
  --text-secondary: #606266;
  --text-muted: #909499;
  --text-light: #c0c5cc;
  --bg-blue-light: #f0f5ff;
  --bg-blue-lighter: #fafcff;
  --border-blue: #d0e0f5;
  --border-main: #dce0e6;
  --border-light: #e9edf2;
  --academic-red: #8f3759;
  --academic-terracotta: #b85b50;
  --academic-teal: #36768f;
  --sidebar-width: 300px;
  --header-height: 64px;
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  font-family: 'Microsoft YaHei', '微软雅黑', 'PingFang SC', 'Hiragino Sans GB', -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--text-dark);
  background: #f5f7fa;
  line-height: 1.8;
  font-size: 15px;
}}

/* ===== Header ===== */
.wiki-header {{
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--header-height);
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: #fff;
  display: flex;
  align-items: center;
  padding: 0 24px;
  z-index: 1000;
  box-shadow: 0 2px 12px rgba(33, 84, 166, 0.3);
}}
.header-logos {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-right: 20px;
  flex-shrink: 0;
}}
.header-logos img {{
  height: 40px;
  filter: brightness(0) invert(1);
  opacity: 0.92;
}}
.header-title {{
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.5px;
  white-space: nowrap;
}}
.header-subtitle {{
  font-size: 12px;
  opacity: 0.75;
  margin-left: 16px;
  letter-spacing: 2px;
  text-transform: uppercase;
  white-space: nowrap;
}}
.header-right {{
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}}
.header-search {{
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.25);
  border-radius: 20px;
  padding: 6px 16px;
  color: #fff;
  font-size: 13px;
  width: 220px;
  outline: none;
  transition: all 0.3s;
}}
.header-search::placeholder {{ color: rgba(255,255,255,0.6); }}
.header-search:focus {{
  background: rgba(255,255,255,0.25);
  border-color: rgba(255,255,255,0.5);
  width: 280px;
}}

/* ===== Sidebar ===== */
.wiki-sidebar {{
  position: fixed;
  top: var(--header-height);
  left: 0;
  bottom: 0;
  width: var(--sidebar-width);
  background: #fff;
  border-right: 1px solid var(--border-main);
  overflow-y: auto;
  z-index: 900;
  padding: 16px 0;
  transition: transform 0.3s;
}}
.wiki-sidebar::-webkit-scrollbar {{ width: 4px; }}
.wiki-sidebar::-webkit-scrollbar-thumb {{ background: var(--border-main); border-radius: 2px; }}

.sidebar-section-label {{
  padding: 8px 20px 4px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 2px;
  text-transform: uppercase;
}}

.wiki-sidebar .toc ul {{
  list-style: none;
  padding: 0;
  margin: 0;
}}
.wiki-sidebar .toc > ul > li {{
  margin: 0;
}}
.wiki-sidebar .toc > ul > li > a {{
  display: block;
  padding: 8px 20px;
  color: var(--text-dark);
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
  border-left: 3px solid transparent;
  transition: all 0.2s;
  line-height: 1.4;
}}
.wiki-sidebar .toc > ul > li > a:hover {{
  background: var(--bg-blue-lighter);
  color: var(--primary);
}}
.wiki-sidebar .toc > ul > li > a.active {{
  border-left-color: var(--primary);
  color: var(--primary);
  background: var(--bg-blue-light);
}}

/* nested (h3) */
.wiki-sidebar .toc > ul > li > ul {{
  display: none;
  padding: 0;
}}
.wiki-sidebar .toc > ul > li.expanded > ul {{
  display: block;
}}
.wiki-sidebar .toc > ul > li > ul > li > a {{
  display: block;
  padding: 5px 20px 5px 36px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 400;
  border-left: 3px solid transparent;
  transition: all 0.2s;
  line-height: 1.4;
}}
.wiki-sidebar .toc > ul > li > ul > li > a:hover {{
  color: var(--primary);
  background: var(--bg-blue-lighter);
}}
.wiki-sidebar .toc > ul > li > ul > li > a.active {{
  border-left-color: var(--academic-teal);
  color: var(--primary);
}}

/* ===== Main Content ===== */
.wiki-main {{
  margin-left: var(--sidebar-width);
  margin-top: var(--header-height);
  padding: 32px 48px 80px;
  max-width: 960px;
}}

/* ===== Typography ===== */
.wiki-main h1 {{
  font-size: 32px;
  font-weight: 800;
  color: var(--primary);
  margin: 0 0 8px;
  line-height: 1.3;
}}
.wiki-main > blockquote:first-of-type {{
  font-size: 15px;
  color: var(--text-secondary);
  border-left: none;
  background: none;
  padding: 0 0 20px;
  margin: 0;
  border-bottom: 2px solid var(--border-light);
}}

.section-divider {{
  height: 1px;
  background: linear-gradient(90deg, var(--primary), var(--accent), var(--primary));
  margin: 48px 0 32px;
  opacity: 0.2;
}}
.section-divider:first-of-type {{ display: none; }}

.wiki-main h2 {{
  font-size: 24px;
  font-weight: 700;
  color: var(--primary);
  margin: 0 0 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--bg-blue-light);
  scroll-margin-top: calc(var(--header-height) + 20px);
}}

.wiki-main h3 {{
  font-size: 18px;
  font-weight: 700;
  color: var(--text-dark);
  margin: 28px 0 12px;
  padding-left: 12px;
  border-left: 4px solid var(--primary);
  scroll-margin-top: calc(var(--header-height) + 20px);
}}

.wiki-main h4 {{
  font-size: 16px;
  font-weight: 700;
  color: var(--text-secondary);
  margin: 20px 0 8px;
}}

.wiki-main p {{
  margin: 0 0 14px;
  line-height: 1.85;
}}

.wiki-main strong {{
  color: var(--text-dark);
  font-weight: 700;
}}

.wiki-main del {{
  color: var(--text-muted);
  text-decoration: line-through;
}}

.wiki-main a {{
  color: var(--primary);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s;
}}
.wiki-main a:hover {{
  border-bottom-color: var(--primary);
}}

/* ===== Lists ===== */
.wiki-main ul, .wiki-main ol {{
  margin: 0 0 16px;
  padding-left: 24px;
}}
.wiki-main li {{
  margin-bottom: 6px;
  line-height: 1.75;
}}
.wiki-main li::marker {{
  color: var(--primary);
}}

/* List items whose only content is an inline code path */
.wiki-main li > code:first-child:last-child {{
  display: block;
  padding: 8px 12px;
  margin: 2px 0;
  line-height: 1.55;
  border-radius: 6px;
  font-size: 12.5px;
  word-break: break-all;
}}

/* Checklist */
ul.checklist {{
  list-style: none;
  padding-left: 4px;
  margin: 8px 0 16px;
}}
.checklist-item {{
  list-style: none;
  padding: 4px 0;
}}
.checklist-item input[type="checkbox"] {{
  margin-right: 8px;
  accent-color: var(--primary);
  transform: scale(1.15);
  vertical-align: middle;
}}

/* ===== Tables ===== */
.data-table {{
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0 24px;
  font-size: 14px;
  line-height: 1.6;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}}
.data-table th {{
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: #fff;
  font-weight: 600;
  padding: 10px 14px;
  text-align: left;
  font-size: 13px;
  white-space: nowrap;
}}
.data-table td {{
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-light);
  vertical-align: top;
}}
.data-table tr:nth-child(even) td {{
  background: var(--bg-blue-lighter);
}}
.data-table tr:hover td {{
  background: var(--bg-blue-light);
}}
.data-table td:first-child {{
  font-weight: 600;
  color: var(--text-dark);
}}

/* ===== Code Blocks ===== */
.wiki-main code {{
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'SF Mono', Consolas, monospace;
  font-size: 13px;
  background: var(--bg-blue-light);
  color: var(--primary-dark);
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-word;
}}
.wiki-main pre {{
  background: #1e2736;
  color: #e4e8ee;
  padding: 20px 24px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 16px 0 24px;
  line-height: 1.65;
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
  border-left: 4px solid var(--primary);
}}
.wiki-main pre code {{
  background: none;
  color: inherit;
  padding: 0;
  font-size: 13px;
}}

/* ===== Blockquotes / Info Boxes ===== */
.info-box {{
  background: var(--bg-blue-light);
  border-left: 4px solid var(--primary);
  padding: 14px 20px;
  margin: 16px 0 24px;
  border-radius: 0 8px 8px 0;
  color: var(--text-secondary);
  font-size: 14px;
}}
.info-box p {{ margin-bottom: 6px; }}
.info-box p:last-child {{ margin-bottom: 0; }}
.info-box strong {{ color: var(--primary-dark); }}

/* ===== Back to Top ===== */
.back-to-top {{
  position: fixed;
  bottom: 32px;
  right: 32px;
  width: 44px;
  height: 44px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(33, 84, 166, 0.4);
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.3s;
  z-index: 800;
}}
.back-to-top.visible {{
  opacity: 1;
  transform: translateY(0);
}}
.back-to-top:hover {{
  background: var(--primary-dark);
  transform: translateY(-2px);
}}

/* ===== Footer ===== */
.wiki-footer {{
  margin-left: var(--sidebar-width);
  padding: 24px 48px;
  background: #fff;
  border-top: 4px solid var(--primary);
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}}
.footer-logos {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 10px;
}}
.footer-logos img {{
  height: 36px;
  opacity: 0.7;
}}

/* ===== Sidebar Toggle (mobile) ===== */
.sidebar-toggle {{
  display: none;
  position: fixed;
  bottom: 32px;
  left: 16px;
  width: 44px;
  height: 44px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  font-size: 18px;
  z-index: 1100;
  box-shadow: 0 4px 12px rgba(33, 84, 166, 0.4);
  align-items: center;
  justify-content: center;
}}

/* ===== Progress Bar ===== */
.progress-bar {{
  position: fixed;
  top: var(--header-height);
  left: 0;
  right: 0;
  height: 3px;
  background: var(--border-light);
  z-index: 950;
}}
.progress-bar-fill {{
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--academic-teal));
  width: 0%;
  transition: width 0.15s;
}}

/* ===== Search Highlight ===== */
mark.search-highlight {{
  background: #fef3cd;
  color: var(--text-dark);
  padding: 1px 2px;
  border-radius: 2px;
}}

/* ===== Responsive ===== */
@media (max-width: 1024px) {{
  .wiki-sidebar {{
    transform: translateX(-100%);
  }}
  .wiki-sidebar.open {{
    transform: translateX(0);
    box-shadow: 4px 0 20px rgba(0,0,0,0.15);
  }}
  .wiki-main, .wiki-footer {{
    margin-left: 0;
  }}
  .wiki-main {{
    padding: 24px 20px 80px;
  }}
  .wiki-footer {{
    padding: 24px 20px;
  }}
  .sidebar-toggle {{
    display: flex;
  }}
  .header-subtitle {{
    display: none;
  }}
  .header-search {{
    width: 160px;
  }}
  .header-search:focus {{
    width: 200px;
  }}
}}

@media (max-width: 640px) {{
  .header-search {{ display: none; }}
  .wiki-main h1 {{ font-size: 24px; }}
  .wiki-main h2 {{ font-size: 20px; }}
  .data-table {{ font-size: 12px; }}
  .data-table th, .data-table td {{ padding: 6px 8px; }}
}}

/* ===== Print ===== */
@media print {{
  .wiki-header, .wiki-sidebar, .back-to-top, .sidebar-toggle, .progress-bar {{ display: none !important; }}
  .wiki-main, .wiki-footer {{ margin-left: 0; }}
  .wiki-main {{ padding: 0; max-width: 100%; }}
  .data-table {{ box-shadow: none; border: 1px solid #ddd; }}
  .data-table th {{ background: #eee !important; color: #333 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  pre {{ white-space: pre-wrap; border: 1px solid #ddd; }}
}}
</style>
</head>
<body>

<!-- Header -->
<header class="wiki-header">
  <div class="header-logos">
    <img id="header-logo-scut" alt="华南理工大学">
    <img id="header-logo-cnsba" alt="工商管理学院">
  </div>
  <span class="header-title">非全日制 MEM 毕业论文实战指南</span>
  <span class="header-subtitle">SCUT School of Business Administration</span>
  <div class="header-right">
    <input type="text" class="header-search" id="searchInput" placeholder="搜索关键词..." />
  </div>
</header>

<!-- Progress Bar -->
<div class="progress-bar"><div class="progress-bar-fill" id="progressFill"></div></div>

<!-- Sidebar -->
<nav class="wiki-sidebar" id="sidebar">
  <div class="sidebar-section-label">目录导航</div>
  <div class="toc" id="tocContainer">
    {toc_html}
  </div>
</nav>

<!-- Main Content -->
<main class="wiki-main" id="mainContent">
{body_html}
</main>

<!-- Footer -->
<footer class="wiki-footer">
  <div class="footer-logos">
    <img id="footer-logo-scut" alt="华南理工大学">
    <img id="footer-logo-cnsba" alt="工商管理学院">
  </div>
  <p>华南理工大学 工商管理学院 MEM 工程管理硕士</p>
  <p>本指南仅供学习参考，具体要求以学校最新规定为准</p>
</footer>

<!-- Back to Top -->
<button class="back-to-top" id="backToTop" title="返回顶部">&#8593;</button>

<!-- Sidebar Toggle (mobile) -->
<button class="sidebar-toggle" id="sidebarToggle">&#9776;</button>

<script>
// Logo injection
const LOGO_SCUT = "{LOGO_SCUT}";
const LOGO_CNSBA = "{LOGO_CNSBA}";

document.getElementById('header-logo-scut').src = LOGO_SCUT;
document.getElementById('header-logo-cnsba').src = LOGO_CNSBA;
document.getElementById('footer-logo-scut').src = LOGO_SCUT;
document.getElementById('footer-logo-cnsba').src = LOGO_CNSBA;

// Progress bar
function updateProgress() {{
  const winH = document.documentElement.scrollHeight - window.innerHeight;
  const pct = winH > 0 ? (window.scrollY / winH) * 100 : 0;
  document.getElementById('progressFill').style.width = pct + '%';
}}
window.addEventListener('scroll', updateProgress);
updateProgress();

// Back to top
const btn = document.getElementById('backToTop');
window.addEventListener('scroll', () => {{
  btn.classList.toggle('visible', window.scrollY > 400);
}});
btn.addEventListener('click', () => {{
  window.scrollTo({{ top: 0, behavior: 'smooth' }});
}});

// Sidebar toggle (mobile)
const sidebar = document.getElementById('sidebar');
document.getElementById('sidebarToggle').addEventListener('click', () => {{
  sidebar.classList.toggle('open');
}});
// Close sidebar on link click (mobile)
sidebar.querySelectorAll('a').forEach(a => {{
  a.addEventListener('click', () => {{
    if (window.innerWidth <= 1024) sidebar.classList.remove('open');
  }});
}});

// Active TOC tracking
const tocLinks = Array.from(document.querySelectorAll('.toc a'));
const headings = tocLinks.map(link => {{
  const id = link.getAttribute('href')?.replace('#', '');
  return id ? document.getElementById(id) : null;
}}).filter(Boolean);

function updateActiveToc() {{
  const offset = 100;
  let activeIdx = 0;
  for (let i = headings.length - 1; i >= 0; i--) {{
    if (headings[i].getBoundingClientRect().top <= offset) {{
      activeIdx = i;
      break;
    }}
  }}
  tocLinks.forEach(l => l.classList.remove('active'));
  if (tocLinks[activeIdx]) {{
    tocLinks[activeIdx].classList.add('active');
    // expand parent
    const parentLi = tocLinks[activeIdx].closest('li');
    document.querySelectorAll('.toc > ul > li').forEach(li => li.classList.remove('expanded'));
    if (parentLi) {{
      const topLi = parentLi.closest('.toc > ul > li') || parentLi;
      topLi.classList.add('expanded');
    }}
    // scroll into view in sidebar
    tocLinks[activeIdx].scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
  }}
}}
window.addEventListener('scroll', updateActiveToc);
updateActiveToc();

// Smooth scroll for TOC links
tocLinks.forEach(link => {{
  link.addEventListener('click', e => {{
    e.preventDefault();
    const id = link.getAttribute('href')?.replace('#', '');
    const target = id ? document.getElementById(id) : null;
    if (target) {{
      target.scrollIntoView({{ behavior: 'smooth' }});
      history.pushState(null, '', '#' + id);
    }}
  }});
}});

// Simple search
const searchInput = document.getElementById('searchInput');
let searchTimeout;
searchInput.addEventListener('input', () => {{
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(doSearch, 300);
}});
function doSearch() {{
  // Remove old highlights
  document.querySelectorAll('mark.search-highlight').forEach(m => {{
    const parent = m.parentNode;
    parent.replaceChild(document.createTextNode(m.textContent), m);
    parent.normalize();
  }});
  const q = searchInput.value.trim();
  if (!q || q.length < 2) return;
  const main = document.getElementById('mainContent');
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, null, false);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const regex = new RegExp('(' + q.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
  let firstMatch = null;
  nodes.forEach(node => {{
    if (node.parentNode.tagName === 'SCRIPT' || node.parentNode.tagName === 'STYLE') return;
    if (!regex.test(node.textContent)) return;
    regex.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let lastIdx = 0;
    let match;
    while ((match = regex.exec(node.textContent)) !== null) {{
      if (match.index > lastIdx) frag.appendChild(document.createTextNode(node.textContent.slice(lastIdx, match.index)));
      const mark = document.createElement('mark');
      mark.className = 'search-highlight';
      mark.textContent = match[1];
      frag.appendChild(mark);
      if (!firstMatch) firstMatch = mark;
      lastIdx = regex.lastIndex;
    }}
    if (lastIdx < node.textContent.length) frag.appendChild(document.createTextNode(node.textContent.slice(lastIdx)));
    node.parentNode.replaceChild(frag, node);
  }});
  if (firstMatch) firstMatch.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
}}
</script>
</body>
</html>"""

with open(DST, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Done! Output: {DST}")
print(f"File size: {os.path.getsize(DST) / 1024:.0f} KB")
