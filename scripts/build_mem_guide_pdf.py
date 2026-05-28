#!/usr/bin/env python3
"""Build a SCUT MEM styled reading PDF from the thesis guide markdown."""

from __future__ import annotations

import html
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ModuleNotFoundError:
    print(
        "缺少 Python 依赖 beautifulsoup4，请先运行：python3 -m pip install beautifulsoup4",
        file=sys.stderr,
    )
    raise SystemExit(1)

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        HRFlowable,
        Image,
        PageBreak,
        PageTemplate,
        Paragraph,
        Preformatted,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.platypus.tableofcontents import TableOfContents
except ModuleNotFoundError as exc:
    package = {"reportlab": "reportlab", "PIL": "pillow"}.get(exc.name, exc.name)
    print(
        f"缺少 Python 依赖 {package}，请先运行：python3 -m pip install {package}",
        file=sys.stderr,
    )
    raise SystemExit(1)


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "非全日制MEM毕业论文实战指南.md"
OUTPUT = ROOT / "非全日制MEM毕业论文实战指南_SCUT阅读版.pdf"

SCUT_SKILL = Path("/Users/tiredboy/.claude/skills/scut-mem-html-slide")
SCUT_LOGO = SCUT_SKILL / "assets/scut-logo.png"
CNSBA_LOGO = SCUT_SKILL / "assets/cnsba-logo.png"

SIGNATURE = "华南理工大学 2025 级非全日制 MEM (2) 班 陈小生 整理制作，本指南仅供交流参考，具体要求以学校最新规定为准"

BLUE = colors.HexColor("#2154a6")
DEEP_BLUE = colors.HexColor("#204285")
ACCENT = colors.HexColor("#1a4280")
WINE = colors.HexColor("#8f3759")
TEAL = colors.HexColor("#36768f")
TEXT = colors.HexColor("#303133")
MUTED = colors.HexColor("#606266")
LIGHT_TEXT = colors.HexColor("#909499")
PALE_BLUE = colors.HexColor("#f0f5ff")
PALE_BLUE_2 = colors.HexColor("#fafcff")
BORDER = colors.HexColor("#dce0e6")
FINE_BORDER = colors.HexColor("#e9edf2")


def register_fonts() -> tuple[str, str, str]:
    regular_candidates = [
        "/Users/tiredboy/Library/Fonts/PingFang-SC-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]
    bold_candidates = [
        "/Users/tiredboy/Library/Fonts/PingFang-SC-Bold.ttf",
        "/Users/tiredboy/Library/Fonts/PingFang-SC-Regular.ttf",
    ]
    code_candidates = [
        "/Users/tiredboy/Library/Fonts/LXGWWenKaiMono-Regular.ttf",
        "/Users/tiredboy/Library/Fonts/LXGWWenKai-Regular.ttf",
        "/Users/tiredboy/Library/Fonts/PingFang-SC-Regular.ttf",
    ]

    def first_font(name: str, candidates: list[str]) -> str:
        for candidate in candidates:
            if Path(candidate).exists():
                pdfmetrics.registerFont(TTFont(name, candidate))
                return name
        return "Helvetica"

    return (
        first_font("PFRegular", regular_candidates),
        first_font("PFBold", bold_candidates),
        first_font("GuideCode", code_candidates),
    )


FONT_REG, FONT_BOLD, FONT_CODE = register_fonts()


def make_styles():
    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "GuideBase",
        parent=styles["Normal"],
        fontName=FONT_REG,
        fontSize=10.2,
        leading=17,
        textColor=TEXT,
        alignment=TA_JUSTIFY,
        spaceAfter=5,
        wordWrap="CJK",
    )
    return {
        "body": base,
        "small": ParagraphStyle(
            "GuideSmall", parent=base, fontSize=8.4, leading=12.4, textColor=MUTED
        ),
        "caption": ParagraphStyle(
            "GuideCaption", parent=base, fontSize=8.2, leading=12, textColor=LIGHT_TEXT
        ),
        "h1": ParagraphStyle(
            "Heading1",
            parent=base,
            fontName=FONT_BOLD,
            fontSize=22,
            leading=29,
            textColor=BLUE,
            spaceBefore=8,
            spaceAfter=13,
            keepWithNext=True,
            alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=base,
            fontName=FONT_BOLD,
            fontSize=18,
            leading=24,
            textColor=DEEP_BLUE,
            spaceBefore=15,
            spaceAfter=9,
            keepWithNext=True,
            alignment=TA_LEFT,
            borderPadding=(5, 8, 5, 8),
            backColor=colors.HexColor("#edf4ff"),
            borderColor=colors.HexColor("#d0e0f5"),
            borderWidth=0.6,
        ),
        "h3": ParagraphStyle(
            "Heading3",
            parent=base,
            fontName=FONT_BOLD,
            fontSize=14.5,
            leading=20,
            textColor=ACCENT,
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True,
            alignment=TA_LEFT,
        ),
        "h4": ParagraphStyle(
            "Heading4",
            parent=base,
            fontName=FONT_BOLD,
            fontSize=12,
            leading=17,
            textColor=WINE,
            spaceBefore=7,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "quote": ParagraphStyle(
            "GuideQuote",
            parent=base,
            leftIndent=8,
            rightIndent=4,
            fontSize=9.6,
            leading=15.5,
            textColor=colors.HexColor("#43536a"),
        ),
        "code": ParagraphStyle(
            "GuideCodeBlock",
            parent=base,
            fontName=FONT_CODE,
            fontSize=8.2,
            leading=11.2,
            textColor=colors.HexColor("#24364b"),
            backColor=colors.HexColor("#f7f9fc"),
            borderColor=colors.HexColor("#d8e2f0"),
            borderWidth=0.4,
            borderPadding=6,
            leftIndent=0,
            wordWrap="CJK",
        ),
        "toc_title": ParagraphStyle(
            "TocTitle",
            parent=base,
            fontName=FONT_BOLD,
            fontSize=18,
            leading=24,
            textColor=BLUE,
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
    }


STYLES = make_styles()


class AnchorParagraph(Paragraph):
    """Paragraph that also exposes an outline/bookmark target."""

    def __init__(self, text: str, style: ParagraphStyle, bookmark: str, level: int):
        super().__init__(text, style)
        self._bookmarkName = bookmark
        self._bookmarkLevel = level
        self._plainText = re.sub(r"<[^>]+>", "", text)


class GuideDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, AnchorParagraph):
            key = flowable._bookmarkName
            text = flowable._plainText
            level = flowable._bookmarkLevel
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=max(0, level - 1), closed=False)
            if level <= 2:
                self.notify("TOCEntry", (level - 1, text, self.page - 1, key))


def pandoc_html(markdown_path: Path) -> str:
    cmd = [
        "pandoc",
        "-f",
        "markdown_github",
        "-t",
        "html5",
        "--section-divs",
        str(markdown_path),
    ]
    return subprocess.check_output(cmd, cwd=ROOT, text=True)


def draw_gradient(canvas, width: float, height: float, c1=BLUE, c2=DEEP_BLUE):
    steps = 90
    r1, g1, b1 = c1.red, c1.green, c1.blue
    r2, g2, b2 = c2.red, c2.green, c2.blue
    for i in range(steps):
        t = i / max(1, steps - 1)
        canvas.setFillColor(colors.Color(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))
        canvas.rect(i * width / steps, 0, width / steps + 1, height, stroke=0, fill=1)


def draw_logo(canvas, path: Path, x: float, y: float, w: float, h: float, mask="auto"):
    if path.exists():
        canvas.drawImage(ImageReader(str(path)), x, y, width=w, height=h, preserveAspectRatio=True, mask=mask)


def draw_cover(canvas, doc):
    width, height = A4
    canvas.saveState()
    draw_gradient(canvas, width, height)
    canvas.setFillColor(colors.white)
    canvas.setFont(FONT_REG, 11)
    canvas.drawCentredString(width / 2, height - 58 * mm, "SOUTH CHINA UNIVERSITY OF TECHNOLOGY · MEM")
    canvas.setStrokeColor(colors.Color(1, 1, 1, alpha=0.55))
    canvas.setLineWidth(1.2)
    canvas.line(width / 2 - 45 * mm, height - 66 * mm, width / 2 + 45 * mm, height - 66 * mm)

    canvas.setFont(FONT_BOLD, 30)
    canvas.drawCentredString(width / 2, height - 88 * mm, "非全日制 MEM")
    canvas.drawCentredString(width / 2, height - 103 * mm, "工程管理硕士毕业论文实战指南")
    canvas.setFont(FONT_REG, 14)
    canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.88))
    canvas.drawCentredString(width / 2, height - 120 * mm, "结构化选题 · 数据证据链 · 开题到盲审全流程")

    canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.16))
    canvas.roundRect(33 * mm, 139 * mm, width - 66 * mm, 34 * mm, 7 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont(FONT_REG, 10.5)
    canvas.drawCentredString(width / 2, 158 * mm, "面向白天上班、晚上写论文的非全日制 MEM 学生")
    canvas.drawCentredString(width / 2, 149 * mm, "目标：每一步都知道做什么、怎么做、做到什么程度算合格")

    draw_logo(canvas, SCUT_LOGO, width / 2 - 43 * mm, 52 * mm, 23 * mm, 23 * mm)
    draw_logo(canvas, CNSBA_LOGO, width / 2 - 15 * mm, 54 * mm, 58 * mm, 18 * mm)
    canvas.setFont(FONT_REG, 9.5)
    canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.82))
    canvas.drawCentredString(width / 2, 31 * mm, SIGNATURE)
    canvas.restoreState()


def on_page(canvas, doc):
    width, height = A4
    if doc.page == 1:
        draw_cover(canvas, doc)
        return

    canvas.saveState()
    page_no = doc.page - 1
    top_y = height - 14 * mm
    canvas.setFillColor(BLUE)
    canvas.rect(0, height - 8 * mm, width, 8 * mm, stroke=0, fill=1)
    canvas.setFont(FONT_BOLD, 8.5)
    canvas.setFillColor(DEEP_BLUE)
    canvas.drawString(18 * mm, top_y, "SCUT MEM · 毕业论文实战指南")
    canvas.setFont(FONT_REG, 8.2)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - 18 * mm, top_y, f"第 {page_no} 页")

    footer_y = 12 * mm
    canvas.setStrokeColor(colors.HexColor("#d0e0f5"))
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, footer_y + 7 * mm, width - 18 * mm, footer_y + 7 * mm)
    draw_logo(canvas, SCUT_LOGO, 18 * mm, footer_y - 1 * mm, 7.5 * mm, 7.5 * mm)
    draw_logo(canvas, CNSBA_LOGO, 28 * mm, footer_y + 0.5 * mm, 24 * mm, 6.5 * mm)
    canvas.setFont(FONT_REG, 7.8)
    canvas.setFillColor(LIGHT_TEXT)
    canvas.drawRightString(width - 18 * mm, footer_y + 1.2 * mm, SIGNATURE)
    canvas.restoreState()


def inline_to_rl(node) -> str:
    if isinstance(node, NavigableString):
        return html.escape(str(node))
    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()
    if name in {"script", "style"}:
        return ""
    if name == "br":
        return "<br/>"
    content = "".join(inline_to_rl(child) for child in node.children)
    if name in {"strong", "b"}:
        return f"<b>{content}</b>"
    if name in {"em", "i"}:
        return f"<i>{content}</i>"
    if name == "code":
        return f'<font name="{FONT_CODE}" color="#1a4280">{content}</font>'
    if name == "a":
        href = html.escape(node.get("href", ""))
        if href:
            return f'<a href="{href}" color="#2154a6">{content}</a>'
        return content
    if name in {"span", "small", "sup", "sub"}:
        return content
    return content


def paragraph_from_tag(tag: Tag, style: ParagraphStyle | None = None) -> Paragraph:
    text = inline_to_rl(tag).strip()
    if not text:
        text = "&nbsp;"
    return Paragraph(text, style or STYLES["body"])


def table_from_tag(tag: Tag) -> Table:
    rows = []
    for tr in tag.find_all("tr"):
        row = []
        cells = tr.find_all(["th", "td"], recursive=False)
        for cell in cells:
            cell_text = inline_to_rl(cell).strip() or "&nbsp;"
            style = ParagraphStyle(
                "TableCell",
                parent=STYLES["small"],
                fontName=FONT_BOLD if cell.name == "th" else FONT_REG,
                textColor=colors.white if cell.name == "th" else TEXT,
                alignment=TA_CENTER if cell.name == "th" else TA_LEFT,
                leading=11.2,
                wordWrap="CJK",
            )
            row.append(Paragraph(cell_text, style))
        if row:
            rows.append(row)
    if not rows:
        return Table([[""]])

    max_cols = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (max_cols - len(row)))

    usable_width = A4[0] - 36 * mm
    col_width = usable_width / max_cols
    table = Table(rows, colWidths=[col_width] * max_cols, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REG),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for row_idx in range(1, len(rows)):
        if row_idx % 2 == 1:
            commands.append(("BACKGROUND", (0, row_idx), (-1, row_idx), PALE_BLUE_2))
    table.setStyle(TableStyle(commands))
    return table


def quote_flowable(tag: Tag):
    content = []
    for child in tag.children:
        if isinstance(child, Tag):
            content.extend(flowables_from_node(child))
        elif isinstance(child, NavigableString) and child.strip():
            content.append(Paragraph(html.escape(str(child).strip()), STYLES["quote"]))
    if not content:
        content = [paragraph_from_tag(tag, STYLES["quote"])]
    box = Table([[content]], colWidths=[A4[0] - 42 * mm])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#d0e0f5")),
                ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return [box, Spacer(1, 5)]


def list_flowable(tag: Tag):
    ordered = tag.name == "ol"
    flows = []
    list_style = ParagraphStyle(
        "GuideListItem",
        parent=STYLES["body"],
        leftIndent=13,
        firstLineIndent=0,
        spaceAfter=3,
        bulletIndent=1,
    )
    for idx, li in enumerate(tag.find_all("li", recursive=False), start=1):
        parts = []
        inline_bits = []
        for child in li.children:
            if isinstance(child, NavigableString):
                if str(child).strip():
                    inline_bits.append(html.escape(str(child)))
            elif isinstance(child, Tag) and child.name not in {"ul", "ol"}:
                inline_bits.append(inline_to_rl(child))
            elif isinstance(child, Tag):
                if inline_bits:
                    bullet = f"{idx}." if ordered else "•"
                    parts.append(Paragraph("".join(inline_bits).strip(), list_style, bulletText=bullet))
                    inline_bits = []
                parts.extend(flowables_from_node(child))
        if inline_bits:
            bullet = f"{idx}." if ordered else "•"
            parts.insert(0, Paragraph("".join(inline_bits).strip(), list_style, bulletText=bullet))
        if not parts:
            bullet = f"{idx}." if ordered else "•"
            parts = [Paragraph("&nbsp;", list_style, bulletText=bullet)]
        flows.extend(parts)
    flows.append(Spacer(1, 3))
    return flows


def image_flowables(tag: Tag) -> list:
    src = unquote(tag.get("src", ""))
    path = (ROOT / src).resolve()
    if not path.exists():
        return []

    img = Image(str(path))
    max_w = A4[0] - 44 * mm
    max_h = 72 * mm
    scale = min(max_w / img.drawWidth, max_h / img.drawHeight, 1)
    img.drawWidth *= scale
    img.drawHeight *= scale
    flows = [Spacer(1, 4), img]

    alt = tag.get("alt", "").strip()
    if alt:
        flows.append(Paragraph(alt, STYLES["caption"]))
    flows.append(Spacer(1, 8))
    return flows


heading_counter = 0


def flowables_from_node(node) -> list:
    global heading_counter
    if isinstance(node, NavigableString):
        if node.strip():
            return [Paragraph(html.escape(str(node).strip()), STYLES["body"])]
        return []
    if not isinstance(node, Tag):
        return []

    name = node.name.lower()
    if name in {"section", "div", "body"}:
        out = []
        for child in node.children:
            out.extend(flowables_from_node(child))
        return out

    if name in {"h1", "h2", "h3", "h4"}:
        level = int(name[1])
        heading_counter += 1
        text = inline_to_rl(node).strip()
        bookmark = f"h-{heading_counter}"
        style = STYLES.get(name, STYLES["h4"])
        flows = []
        if level == 2:
            flows.append(Spacer(1, 3))
        flows.append(AnchorParagraph(text, style, bookmark, min(level, 3)))
        return flows

    if name == "p":
        direct_images = node.find_all("img", recursive=False)
        if direct_images and not node.get_text(strip=True):
            flows = []
            for image in direct_images:
                flows.extend(image_flowables(image))
            return flows
        return [paragraph_from_tag(node), Spacer(1, 2)]
    if name in {"ul", "ol"}:
        return list_flowable(node)
    if name == "blockquote":
        return quote_flowable(node)
    if name == "pre":
        text = node.get_text("\n").rstrip()
        return [Preformatted(text, STYLES["code"], maxLineLength=92), Spacer(1, 6)]
    if name == "table":
        return [Spacer(1, 3), table_from_tag(node), Spacer(1, 8)]
    if name == "hr":
        return [
            Spacer(1, 5),
            HRFlowable(width="100%", thickness=0.5, color=FINE_BORDER),
            Spacer(1, 6),
        ]
    if name == "img":
        return image_flowables(node)

    return [paragraph_from_tag(node), Spacer(1, 2)]


def build_story(html_text: str):
    soup = BeautifulSoup(html_text, "html.parser")
    story = [Spacer(1, 1), PageBreak()]

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOC1",
            fontName=FONT_BOLD,
            fontSize=10.5,
            leading=15,
            leftIndent=0,
            firstLineIndent=0,
            textColor=DEEP_BLUE,
        ),
        ParagraphStyle(
            "TOC2",
            fontName=FONT_REG,
            fontSize=9.2,
            leading=13,
            leftIndent=12,
            firstLineIndent=0,
            textColor=MUTED,
        ),
    ]
    story.extend(
        [
            Paragraph("目录速览", STYLES["toc_title"]),
            Paragraph(
                "这份 PDF 保留指南中的细节，并按章节建立目录与书签。阅读时建议先看第零章、第三章、第七章和附录的一页纸选题卡。",
                STYLES["body"],
            ),
            Spacer(1, 10),
            toc,
            PageBreak(),
        ]
    )

    body = soup.body or soup
    for child in body.children:
        story.extend(flowables_from_node(child))
    return story


def main() -> int:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT
    html_text = pandoc_html(input_path)
    story = build_story(html_text)

    width, height = A4
    frame = Frame(
        18 * mm,
        23 * mm,
        width - 36 * mm,
        height - 42 * mm,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc = GuideDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=19 * mm,
        bottomMargin=23 * mm,
        title="非全日制 MEM 工程管理硕士毕业论文实战指南",
        author="华南理工大学 2025 级非全日制 MEM 2 班 陈小生",
    )
    doc.addPageTemplates([PageTemplate(id="guide", frames=[frame], onPage=on_page)])
    doc.multiBuild(story)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
