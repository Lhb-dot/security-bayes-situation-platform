"""报告导出：把报告正文（Markdown）转成 Markdown / HTML / PDF 三种格式的文件。

依赖与选型
----------
- **md → html**：markdown-it-py（`markdown-it-py`，纯 Python，无系统依赖）。
  用 CommonMark 预设而不是 Python-Markdown：报告正文里子项是**缩进 2 空格**的
  （`_render_content` 的写法），CommonMark 认为这就是嵌套列表，Python-Markdown 却
  要求 4 空格、会把父子项拍平成同级。前端预览用的是 `marked`（同为 CommonMark 系），
  所以这里也走 CommonMark 才能和界面上看到的结构一致。
  另外把 `html` 关掉：正文里夹带的标签会被转义成文本，而不是当 HTML 执行。
- **html → pdf**：Playwright + Chromium 的 `page.pdf()`。
  选它而不是 weasyprint / xhtml2pdf 的原因：weasyprint 依赖 GTK/Pango 等原生库，
  Windows 上装不动、和 Linux 服务器不一致；xhtml2pdf 只支持 CSS 子集、中文还要自己塞字体。
  Chromium 用系统字体（中文开箱可用）、CSS 支持完整，且 md→html 与 html→pdf
  共用同一份 HTML，两种格式产物天然一致。

部署注意
--------
服务器上需要：
    pip install -r requirements.txt
    playwright install chromium          # 首次需下载浏览器内核
Debian/Ubuntu 若缺中文字体，再装 `fonts-noto-cjk`，否则 PDF 里中文会变方块。

线程模型
--------
Playwright 的同步 API 绑定在「创建它的那个线程」上，而 FastAPI 的同步端点跑在
threadpool 里（同一端点的多次请求可能落在不同线程），所以**不能让请求线程直接持有
浏览器**。这里用一个常驻后台线程独占 Chromium，请求方把 HTML 丢进队列、等结果，
既避开线程亲和性问题，也让浏览器只启动一次。

空闲退出
--------
浏览器常驻约 280 MB（217 MB 内存 + 65 MB swap），而 PDF 导出是低频操作（历史上
只被用过个位数次）。所以渲染线程在队列空闲 IDLE_EXIT_SECONDS 后主动退出并关闭浏览器，
下一次导出再重新拉起 —— 代价是空闲后的首次导出多约 1–2 秒冷启动。
环境变量 PDF_IDLE_EXIT_SECONDS 可覆盖（置 0 表示永不退出，即改动前的行为）。

图表
----
界面上「报告详情」里的图表是前端拿 `report_data` 用 ECharts 现画的，而 `report.content`
（Markdown 正文）里只有文字和表格，所以导出文件里一张图都没有。
这里补上：把 `report_data` 里的分布/概率数据用**纯 Python 生成 SVG** 塞进导出的 HTML，
PDF 走同一份 HTML 渲染，于是两种格式的图一致。

选 SVG 手写而不是在导出页里引 ECharts，原因是：
- 导出的 HTML 是给人下载后**离线打开**的，引 CDN 会在断网/内网环境里变成空白；
- PDF 由服务端 Chromium 渲染，引 CDN 还要求服务器能出网，多一个失败点；
- SVG 在 PDF 里是矢量，缩放不糊，比位图截图更适合打印。

markdown 格式仍然是纯文本（Markdown 本身没有可靠的图表表达方式，嵌 base64 图片
会让文件不可读），这是有意保留的差异。
"""
from __future__ import annotations

import html as _html
import math
import os
import queue
import re
import threading
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from markdown_it import MarkdownIt

from app.utils.common import get_logger

# get_logger("report_export") 与原来的 logging.getLogger(__name__) 同名（app.services.report_export），
# 只是统一走项目的 logger 工厂，日志前缀口径与其它 service 一致。
logger = get_logger("report_export")

#: 单次 PDF 渲染的等待上限（秒）。冷启动 + 多页渲染实测 1 秒出头，留足余量。
PDF_TIMEOUT_SECONDS = 120

#: 渲染线程空闲多久后退出并释放浏览器（秒）。0 = 常驻不退出。
IDLE_EXIT_SECONDS = 600

EXTENSIONS = {"markdown": "md", "html": "html", "pdf": "pdf"}

MEDIA_TYPES = {
    "markdown": "text/markdown; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "pdf": "application/pdf",
}

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

# ---------------------------------------------------------------------------
# HTML 模板（浅色「蓝墨稿纸」：白纸 + 蓝墨，适合打印，屏幕上也是同一份）
# ---------------------------------------------------------------------------
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{title}</title>
<style>
  :root {{
    --ink: #1b2b44;
    --ink-soft: #5a6b85;
    --accent: #1f5fa9;
    --rule: #d9e3f0;
    --paper: #ffffff;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    background: var(--paper);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei",
      "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Source Han Sans SC",
      sans-serif;
    font-size: 14px;
    line-height: 1.78;
    -webkit-font-smoothing: antialiased;
  }}
  .report {{ max-width: 820px; margin: 0 auto; }}
  .report h1 {{
    font-size: 22px;
    line-height: 1.4;
    margin: 0 0 6px;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--accent);
  }}
  .report h2 {{
    font-size: 16px;
    margin: 26px 0 10px;
    padding-left: 10px;
    border-left: 3px solid var(--accent);
    break-after: avoid;
  }}
  .report h3 {{ font-size: 14px; margin: 18px 0 8px; break-after: avoid; }}
  .report p {{ margin: 8px 0; }}
  .report ul, .report ol {{ margin: 8px 0; padding-left: 22px; }}
  .report ul ul, .report ul ol, .report ol ul, .report ol ol {{ margin: 2px 0; }}
  .report li {{ margin: 4px 0; break-inside: avoid; }}
  .report strong {{ color: var(--accent); }}
  .report hr {{ border: 0; border-top: 1px solid var(--rule); margin: 26px 0 10px; }}
  .report code {{
    background: #f1f5fa;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 12.5px;
    font-family: "Cascadia Mono", Consolas, "Courier New", monospace;
  }}
  .report pre {{ background: #f4f8fd; border: 1px solid var(--rule); border-radius: 8px; padding: 12px; overflow-x: auto; }}
  .report pre code {{ background: none; padding: 0; }}
  .report table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
  .report th, .report td {{ border: 1px solid var(--rule); padding: 6px 10px; text-align: left; }}
  .report th {{ background: #f4f8fd; }}
  .report tr {{ break-inside: avoid; }}
  .report blockquote {{
    margin: 10px 0;
    padding: 2px 0 2px 12px;
    border-left: 3px solid var(--rule);
    color: var(--ink-soft);
  }}
  /* 图表：每张图自身不跨页断开（PDF）；单个 chart-block 可能装多张图，
     整块超过一页时 Chromium 会忽略块级约束，所以约束要落在 svg 上 */
  .report .chart-block {{ margin: 14px 0 18px; }}
  .report .chart-block svg {{ display: block; width: 100%; height: auto; break-inside: avoid; }}
  .report .chart-block text {{ font-family: inherit; }}
  /* 屏幕上给一点留白和卡片感；打印/PDF 走 @page 的边距，不加内边距 */
  @media screen {{
    body {{ background: #eef2f8; padding: 36px 20px; }}
    .report {{
      background: var(--paper);
      padding: 44px 52px;
      border-radius: 6px;
      box-shadow: 0 10px 34px rgba(27, 43, 68, 0.13);
    }}
  }}
  @page {{ size: A4; }}
</style>
</head>
<body>
<article class="report">
{body}
</article>
</body>
</html>
"""

#: Chromium 的页脚模板：字号必须显式写在行内，否则会掉到极小
_FOOTER_TEMPLATE = (
    '<div style="width:100%;font-size:9px;color:#8896ab;text-align:center;'
    'font-family:sans-serif;">第 <span class="pageNumber"></span> / '
    '<span class="totalPages"></span> 页</div>'
)
_EMPTY_HEADER_TEMPLATE = '<div style="display:none"></div>'


@dataclass
class ExportFile:
    """一次导出的产物。"""

    content: bytes
    filename: str
    media_type: str


#: CommonMark + 表格；html=False 表示正文里的原始标签一律转义成文本
_MD = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable(
    "table"
)

# ---------------------------------------------------------------------------
# 图表：report_data → SVG
# ---------------------------------------------------------------------------
#: 与报告正文同一套浅色「蓝墨稿纸」配色
_BAR_FILL = "#2f6fb5"
_PALETTE = [
    "#1f5fa9",
    "#3f8fcf",
    "#4aa8a0",
    "#c08a2e",
    "#8a6fc4",
    "#c25b52",
    "#6b8fb5",
    "#a0632f",
]
_AXIS_LINE = "#c7d5e6"
_GRID_LINE = "#e3ebf5"
_LABEL_INK = "#5a6b85"
_VALUE_INK = "#1b2b44"
_MUTED_INK = "#8896ab"


def _r(v: float) -> float:
    """坐标取两位小数，避免 SVG 里出现一长串浮点尾数。"""
    return round(float(v), 2)


def _xml(text) -> str:
    """SVG 文本节点转义（标签/类别名来自数据，可能带 & 或 <）。"""
    return _html.escape(str(text), quote=True)


def _text_width(text: str, size: float) -> float:
    """粗略估算文本宽度：中日韩字符按 1 em，其余按 0.55 em。

    只用来决定标签要不要截断，不需要精确 —— SVG 里没有排版引擎可以先量后画。
    """
    return sum(size * (1.0 if ord(ch) > 0x2E80 else 0.55) for ch in text)


def _ellipsize(text: str, size: float, max_width: float) -> str:
    """超宽标签截断加省略号。"""
    text = str(text)
    if _text_width(text, size) <= max_width:
        return text
    out = ""
    for ch in text:
        if _text_width(out + ch + "…", size) > max_width:
            break
        out += ch
    return (out + "…") if out else "…"


def _fmt_num(v) -> str:
    """整数不带小数点，其余保留三位。"""
    if v is None:
        return "—"
    f = float(v)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return f"{f:.3f}"


def _fmt_tick(v: float) -> str:
    """坐标轴刻度：0.25 → 0.25、0.5 → 0.5、1.0 → 1。"""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    if abs(v) < 1:
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{v:g}"


def _nice_axis(max_value: float, ticks: int = 4) -> tuple:
    """给坐标轴找一组好看的 (上限, 步长)。"""
    max_value = float(max_value or 0)
    if max_value <= 0:
        return float(ticks), 1.0
    raw = max_value / ticks
    mag = 10 ** math.floor(math.log10(raw))
    step = mag * 10
    for mult in (1, 2, 2.5, 5, 10):
        if mult * mag >= raw:
            step = mult * mag
            break
    top = step * ticks
    while top < max_value:
        top += step
    return top, step


def _svg_open(width: float, height: float, title: str) -> str:
    return (
        f'<svg class="chart" viewBox="0 0 {_r(width)} {_r(height)}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
        f"<title>{_xml(title)}</title>"
    )


def _chart_title(title: str, x: float, y: float, max_width: float = 0) -> str:
    if max_width:
        title = _ellipsize(title, 13, max_width)
    return (
        f'<text x="{_r(x)}" y="{_r(y)}" font-size="13" font-weight="700" '
        f'fill="{_VALUE_INK}">{_xml(title)}</text>'
    )


def _legend_items(series, width, x0, y0, max_lines=2) -> str:
    """多系列图例；一行放不下就折行，超过 max_lines 就不再画。"""
    parts, x, y, lines = [], x0, y0, 1
    for idx, item in enumerate(series):
        name = str(item.get("name") or f"系列 {idx + 1}")
        color = _PALETTE[idx % len(_PALETTE)]
        need = 14 + _text_width(name, 12) + 18
        if x + need > width and lines < max_lines:
            x, y, lines = x0, y + 18, lines + 1
        if x + need > width:
            break
        parts.append(
            f'<rect x="{_r(x)}" y="{_r(y - 8)}" width="10" height="10" rx="2" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{_r(x + 15)}" y="{_r(y + 1)}" font-size="12" '
            f'fill="{_LABEL_INK}">{_xml(name)}</text>'
        )
        x += need
    return "".join(parts)


def _vbar_svg(title: str, categories, values, width: float = 720, height: float = 264) -> str:
    """垂直柱状图（预测标签分布）。"""
    pad_l, pad_r, pad_t, pad_b = 58.0, 18.0, 44.0, 54.0
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    top, step = _nice_axis(max(values) if values else 0)

    parts = [
        _svg_open(width, height, title),
        _chart_title(title, pad_l, 24, width - pad_l - pad_r),
    ]
    ticks = int(round(top / step)) if step else 0
    for i in range(ticks + 1):
        v = step * i
        y = pad_t + plot_h * (1 - v / top)
        parts.append(
            f'<line x1="{_r(pad_l)}" y1="{_r(y)}" x2="{_r(pad_l + plot_w)}" y2="{_r(y)}" '
            f'stroke="{_GRID_LINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{_r(pad_l - 8)}" y="{_r(y + 4)}" text-anchor="end" font-size="11" '
            f'fill="{_MUTED_INK}">{_fmt_tick(v)}</text>'
        )
    parts.append(
        f'<line x1="{_r(pad_l)}" y1="{_r(pad_t + plot_h)}" x2="{_r(pad_l + plot_w)}" '
        f'y2="{_r(pad_t + plot_h)}" stroke="{_AXIS_LINE}" stroke-width="1"/>'
    )

    n = len(categories)
    band = plot_w / n if n else plot_w
    bar_w = min(48.0, band * 0.6)
    for i, (cat, val) in enumerate(zip(categories, values)):
        cx = pad_l + band * (i + 0.5)
        h = plot_h * (float(val) / top) if top else 0.0
        y = pad_t + plot_h - h
        if h > 0:
            parts.append(
                f'<rect x="{_r(cx - bar_w / 2)}" y="{_r(y)}" width="{_r(bar_w)}" '
                f'height="{_r(h)}" rx="3" fill="{_BAR_FILL}"/>'
            )
        parts.append(
            f'<text x="{_r(cx)}" y="{_r(y - 6)}" text-anchor="middle" font-size="11" '
            f'fill="{_VALUE_INK}">{_fmt_num(val)}</text>'
        )
        label = _ellipsize(cat, 12, max(band - 6, 24))
        parts.append(
            f'<text x="{_r(cx)}" y="{_r(pad_t + plot_h + 20)}" text-anchor="middle" '
            f'font-size="12" fill="{_LABEL_INK}">{_xml(label)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _hbar_svg(title: str, categories, values, width: float = 720, row_h: float = 34) -> str:
    """横向柱状图（风险概率区间分布）。"""
    pad_l, pad_r, pad_t, pad_b = 78.0, 46.0, 44.0, 34.0
    n = len(categories)
    height = pad_t + n * row_h + pad_b
    plot_w = width - pad_l - pad_r
    top, step = _nice_axis(max(values) if values else 0)

    parts = [_svg_open(width, height, title), _chart_title(title, pad_l, 24, width - pad_l - pad_r)]
    ticks = int(round(top / step)) if step else 0
    for i in range(ticks + 1):
        v = step * i
        x = pad_l + plot_w * (v / top)
        parts.append(
            f'<line x1="{_r(x)}" y1="{_r(pad_t)}" x2="{_r(x)}" y2="{_r(pad_t + n * row_h)}" '
            f'stroke="{_GRID_LINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{_r(x)}" y="{_r(pad_t + n * row_h + 18)}" text-anchor="middle" '
            f'font-size="11" fill="{_MUTED_INK}">{_fmt_tick(v)}</text>'
        )
    parts.append(
        f'<line x1="{_r(pad_l)}" y1="{_r(pad_t)}" x2="{_r(pad_l)}" y2="{_r(pad_t + n * row_h)}" '
        f'stroke="{_AXIS_LINE}" stroke-width="1"/>'
    )

    bar_h = min(18.0, row_h * 0.56)
    for i, (cat, val) in enumerate(zip(categories, values)):
        cy = pad_t + row_h * (i + 0.5)
        w = plot_w * (float(val) / top) if top else 0.0
        if w > 0:
            parts.append(
                f'<rect x="{_r(pad_l)}" y="{_r(cy - bar_h / 2)}" width="{_r(w)}" '
                f'height="{_r(bar_h)}" rx="3" fill="{_BAR_FILL}"/>'
            )
        parts.append(
            f'<text x="{_r(pad_l - 10)}" y="{_r(cy + 4)}" text-anchor="end" font-size="12" '
            f'fill="{_LABEL_INK}">{_xml(cat)}</text>'
        )
        parts.append(
            f'<text x="{_r(pad_l + w + 8)}" y="{_r(cy + 4)}" font-size="11" '
            f'fill="{_VALUE_INK}">{_fmt_num(val)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _ring_point(cx: float, cy: float, r: float, deg: float) -> tuple:
    rad = math.radians(deg - 90)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _ring_segment(cx, cy, r_out, r_in, a0, a1) -> str:
    """环形扇区路径（a0/a1 为角度，0 = 12 点方向，顺时针）。"""
    x0, y0 = _ring_point(cx, cy, r_out, a0)
    x1, y1 = _ring_point(cx, cy, r_out, a1)
    x2, y2 = _ring_point(cx, cy, r_in, a1)
    x3, y3 = _ring_point(cx, cy, r_in, a0)
    large = 1 if (a1 - a0) > 180 else 0
    return (
        f"M {_r(x0)} {_r(y0)} A {_r(r_out)} {_r(r_out)} 0 {large} 1 {_r(x1)} {_r(y1)} "
        f"L {_r(x2)} {_r(y2)} A {_r(r_in)} {_r(r_in)} 0 {large} 0 {_r(x3)} {_r(y3)} Z"
    )


def _donut_svg(title: str, items, width: float = 720, height: Optional[float] = None) -> str:
    """环形图（类别概率）；items = [{label, value, color}]。"""
    items = [it for it in items if (it.get("value") or 0) > 0]
    total = sum(float(it["value"]) for it in items)
    if not items or total <= 0:
        return ""

    pad_t = 44.0
    # 图例一行 22px，类别多的时候把画布拉高，别让图例被裁掉
    if height is None:
        height = max(236.0, pad_t + len(items) * 22 + 14)
    cx, cy = 152.0, pad_t + 78
    r_out, r_in = 80.0, 48.0
    parts = [_svg_open(width, height, title), _chart_title(title, 16, 24, width - 32)]

    if len(items) == 1:
        parts.append(
            f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r((r_out + r_in) / 2)}" fill="none" '
            f'stroke="{items[0]["color"]}" stroke-width="{_r(r_out - r_in)}"/>'
        )
    else:
        angle = 0.0
        for it in items:
            sweep = 360.0 * float(it["value"]) / total
            parts.append(
                f'<path d="{_ring_segment(cx, cy, r_out, r_in, angle, angle + sweep)}" '
                f'fill="{it["color"]}"/>'
            )
            angle += sweep

    lx, ly = 300.0, pad_t + 2
    legend_w = width - lx - 16
    for it in items:
        pct = float(it["value"]) / total * 100
        text = _ellipsize(f"{it['label']} {pct:.1f}%", 12, legend_w - 16)
        parts.append(
            f'<rect x="{_r(lx)}" y="{_r(ly - 9)}" width="10" height="10" rx="2" '
            f'fill="{it["color"]}"/>'
        )
        parts.append(
            f'<text x="{_r(lx + 16)}" y="{_r(ly)}" font-size="12" '
            f'fill="{_LABEL_INK}">{_xml(text)}</text>'
        )
        ly += 22
    parts.append("</svg>")
    return "".join(parts)


def _grouped_bar_svg(
    title: str, categories, series, width: float = 720, height: float = 300
) -> str:
    """分组柱状图（多视图概率对比）；series = [{name, data}]。"""
    pad_l, pad_r, pad_t, pad_b = 58.0, 18.0, 64.0, 54.0
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    flat = [v for s in series for v in s.get("data") or []]
    top, step = _nice_axis(max(flat) if flat else 0)

    parts = [
        _svg_open(width, height, title),
        _chart_title(title, pad_l, 24, width - pad_l - pad_r),
        _legend_items(series, width - pad_r, pad_l, 46),
    ]
    ticks = int(round(top / step)) if step else 0
    for i in range(ticks + 1):
        v = step * i
        y = pad_t + plot_h * (1 - v / top)
        parts.append(
            f'<line x1="{_r(pad_l)}" y1="{_r(y)}" x2="{_r(pad_l + plot_w)}" y2="{_r(y)}" '
            f'stroke="{_GRID_LINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{_r(pad_l - 8)}" y="{_r(y + 4)}" text-anchor="end" font-size="11" '
            f'fill="{_MUTED_INK}">{_fmt_tick(v)}</text>'
        )
    parts.append(
        f'<line x1="{_r(pad_l)}" y1="{_r(pad_t + plot_h)}" x2="{_r(pad_l + plot_w)}" '
        f'y2="{_r(pad_t + plot_h)}" stroke="{_AXIS_LINE}" stroke-width="1"/>'
    )

    n, m = len(categories), len(series)
    band = plot_w / n if n else plot_w
    group_w = band * 0.72
    bar_w = group_w / m if m else group_w
    show_values = bar_w >= 22
    for i, cat in enumerate(categories):
        base = pad_l + band * i + (band - group_w) / 2
        for j, s in enumerate(series):
            data = s.get("data") or []
            val = float(data[i]) if i < len(data) else 0.0
            h = plot_h * (val / top) if top else 0.0
            x = base + bar_w * j
            y = pad_t + plot_h - h
            if h > 0:
                parts.append(
                    f'<rect x="{_r(x + 1)}" y="{_r(y)}" width="{_r(max(bar_w - 2, 1))}" '
                    f'height="{_r(h)}" rx="2" fill="{_PALETTE[j % len(_PALETTE)]}"/>'
                )
            if show_values:
                parts.append(
                    f'<text x="{_r(x + bar_w / 2)}" y="{_r(y - 5)}" text-anchor="middle" '
                    f'font-size="10" fill="{_VALUE_INK}">{_fmt_num(val)}</text>'
                )
        label = _ellipsize(cat, 12, max(band - 6, 24))
        parts.append(
            f'<text x="{_r(pad_l + band * (i + 0.5))}" y="{_r(pad_t + plot_h + 20)}" '
            f'text-anchor="middle" font-size="12" fill="{_LABEL_INK}">{_xml(label)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


#: 图表插到哪一段之后：锚点是「下一节的标题」，插在它之前。
#: 这两个字符串必须与 report_service._render_content 渲染出的 <h2> 标题逐字一致
#: （那里直接 import 本模块的常量来拼标题，避免两处各写一份而静默失配）。
SECTION_VIEWS = "四、不同视图预测结果与概率"
SECTION_FEATURES = "五、特征加权条件概率（Top 10）"


def build_chart_blocks(report_data) -> list:
    """report_data → [(锚点标题, 图表 HTML)]。

    没有 report_data（旧报告）或数据全空时返回空列表，导出结果与改动前一致。
    """
    if not isinstance(report_data, dict) or not report_data.get("report_info"):
        return []

    blocks = []

    pred = report_data.get("prediction") or {}
    charts = []
    dist = pred.get("label_distribution") or []
    if dist and any((d.get("count") or 0) for d in dist):
        charts.append(
            _vbar_svg(
                "预测标签分布",
                [d.get("label") or "未知" for d in dist],
                [d.get("count") or 0 for d in dist],
            )
        )
    probs = [
        (c.get("class") or "未知", float(c.get("probability") or 0))
        for c in (pred.get("class_probability") or [])
    ]
    if probs and any(v > 0 for _c, v in probs):
        charts.append(
            _donut_svg(
                "类别概率",
                [
                    {"label": c, "value": v, "color": _PALETTE[i % len(_PALETTE)]}
                    for i, (c, v) in enumerate(probs)
                ],
            )
        )
    buckets = pred.get("risk_prob_buckets") or []
    if buckets and any((b.get("count") or 0) for b in buckets):
        charts.append(
            _hbar_svg(
                "风险概率区间分布",
                [b.get("range") or "—" for b in buckets],
                [b.get("count") or 0 for b in buckets],
            )
        )
    if charts:
        blocks.append((SECTION_VIEWS, "".join(charts)))

    charts = []
    for m in report_data.get("model_analysis") or []:
        views = [v for v in (m.get("views") or []) if v.get("distribution")]
        if len(views) < 2:
            continue
        categories = [d.get("class") for d in views[0]["distribution"]]
        if not categories:
            continue
        series = []
        for v in views:
            lookup = {d.get("class"): d.get("probability") or 0 for d in v["distribution"]}
            series.append(
                {
                    "name": v.get("name") or "视图",
                    "data": [float(lookup.get(c) or 0) for c in categories],
                }
            )
        name = m.get("algorithm_name") or m.get("algorithm_code") or "模型"
        charts.append(
            _grouped_bar_svg(
                f"{name}（模型 {m.get('model_version_id')}）多视图概率对比", categories, series
            )
        )
    if charts:
        blocks.append((SECTION_FEATURES, "".join(charts)))

    return blocks


def _inject_charts(body: str, report_data) -> str:
    """把图表插到对应章节末尾（即「下一节标题」之前）。

    找不到锚点（正文被改过或结构不同）时退化为追加到文末，宁可位置差一点，
    也不要整块图丢掉。
    """
    blocks = build_chart_blocks(report_data)
    if not blocks:
        return body
    for heading, charts in blocks:
        html = f'<div class="chart-block">{charts}</div>'
        marker = f"<h2>{heading}</h2>"
        idx = body.find(marker)
        if idx == -1:
            body = body + html
        else:
            body = body[:idx] + html + body[idx:]
    return body


def markdown_to_html(markdown_text: str) -> str:
    """Markdown 正文 → HTML 片段。"""
    return _MD.render(markdown_text or "")


def render_html_document(title: str, markdown_text: str, report_data=None) -> str:
    """Markdown 正文 → 完整的 HTML 文档（带打印友好样式 + 图表）。"""
    body = _inject_charts(markdown_to_html(markdown_text), report_data)
    # 标题只出现在 <title> 里。原来手写 replace 只挡了 < >，标题里的 & 会原样落进文档
    # （非法 HTML，且与 _xml/_html.escape 的其它转义点口径不一致），统一走 _html.escape。
    safe_title = _html.escape(title or "态势报告", quote=True)
    return _HTML_TEMPLATE.format(title=safe_title, body=body)


class _PdfRenderer:
    """常驻后台线程独占一个 Chromium，串行把 HTML 渲染成 PDF；空闲超时后退出。"""

    def __init__(self, idle_exit_seconds: Optional[int] = None) -> None:
        self._jobs: "queue.Queue[Optional[tuple]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._guard = threading.Lock()
        self._idle_exit = (
            _env_idle_exit_seconds() if idle_exit_seconds is None else idle_exit_seconds
        )

    def render(self, html: str, timeout: int = PDF_TIMEOUT_SECONDS) -> bytes:
        holder: list = []
        done = threading.Event()
        # 「确保线程存在」与「投递任务」必须在同一把锁里：否则两步之间渲染线程可能
        # 恰好空闲超时退出，任务就投进了一个没人消费的队列，调用方要白等到超时。
        with self._guard:
            self._ensure_thread_locked()
            self._jobs.put((html, holder, done))
        if not done.wait(timeout):
            raise TimeoutError(f"PDF 渲染超过 {timeout} 秒未完成")
        if not holder:
            # 事件已置位却没有结果：渲染线程在投递结果前异常退出
            raise RuntimeError("PDF 渲染线程未返回结果")
        result = holder[0]
        if isinstance(result, BaseException):
            raise result
        return result

    def is_ready(self) -> bool:
        """渲染线程当前是否活着（浏览器是否已启动）。"""
        with self._guard:
            return self._thread is not None and self._thread.is_alive()

    def _ensure_thread_locked(self) -> None:
        """确保渲染线程在跑（调用方必须已持 ``_guard``）。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._serve, name="report-pdf-renderer", daemon=True
        )
        self._thread.start()

    def _serve(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._retire(
                RuntimeError("未安装 playwright，无法导出 PDF（pip install playwright）")
            )
            return
        try:
            with sync_playwright() as pw:
                # --no-sandbox：容器里以 root 跑时 Chromium 必须有它才能启动
                browser = pw.chromium.launch(args=["--no-sandbox"])
                try:
                    while True:
                        try:
                            job = self._jobs.get(timeout=self._idle_exit or None)
                        except queue.Empty:
                            # 空闲超时：确认队列真的空了才退（退出后浏览器被关闭，
                            # 约 280 MB 归还给系统）。_thread 置空后下一次 render()
                            # 会重新拉起线程 + 重新 launch。
                            with self._guard:
                                if not self._jobs.empty():
                                    continue
                                self._thread = None
                            logger.info("PDF 渲染线程空闲超时退出，浏览器已释放")
                            break
                        if job is None:
                            break
                        html, holder, done = job
                        try:
                            page = browser.new_page()
                            try:
                                page.set_content(html, wait_until="load")
                                holder.append(
                                    page.pdf(
                                        format="A4",
                                        print_background=True,
                                        display_header_footer=True,
                                        header_template=_EMPTY_HEADER_TEMPLATE,
                                        footer_template=_FOOTER_TEMPLATE,
                                        margin={
                                            "top": "16mm",
                                            "bottom": "18mm",
                                            "left": "14mm",
                                            "right": "14mm",
                                        },
                                    )
                                )
                            finally:
                                page.close()
                        except Exception as exc:  # noqa: BLE001 —— 单条失败不拖垮渲染线程
                            logger.warning("PDF 渲染失败: %s", exc)
                            holder.append(exc)
                        finally:
                            done.set()
                finally:
                    browser.close()
        except Exception as exc:  # noqa: BLE001 —— 浏览器起不来时，排队的请求统一失败
            logger.warning("Chromium 启动失败: %s", exc)
            self._retire(
                RuntimeError(
                    "Chromium 不可用，无法导出 PDF（先执行 playwright install chromium）"
                )
            )

    def _retire(self, exc: BaseException) -> None:
        """线程退出前的收尾：先标记线程已退出，再让排队的请求统一失败。

        两步必须同锁：否则 render() 可能在「排空队列」与「置空 _thread」之间塞进新任务，
        任务落到一个已经死掉的线程上，调用方白等 120 秒。
        """
        with self._guard:
            self._thread = None
            self._fail_pending(exc)

    def _fail_pending(self, exc: BaseException) -> None:
        while True:
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                return
            if job is None:
                continue
            job[1].append(exc)
            job[2].set()


def _env_idle_exit_seconds() -> int:
    """读 PDF_IDLE_EXIT_SECONDS；解析失败或为负时回落到默认值。"""
    try:
        return max(0, int(os.getenv("PDF_IDLE_EXIT_SECONDS", IDLE_EXIT_SECONDS)))
    except ValueError:
        return IDLE_EXIT_SECONDS


_renderer = _PdfRenderer()


def html_to_pdf(html: str) -> bytes:
    """HTML 文档 → PDF 字节流。"""
    return _renderer.render(html)


def safe_filename(title: str, report_id: int, fmt: str) -> str:
    """按报告标题生成安全的下载文件名。"""
    ext = EXTENSIONS.get(fmt, "txt")
    name = _UNSAFE_FILENAME_CHARS.sub("_", (title or "").strip()).strip(" .")
    # 超长标题在部分文件系统上会踩路径长度限制，截断到 60 字
    name = name[:60] or f"report_{report_id}"
    return f"{name}.{ext}"


def content_disposition(filename: str, report_id: int, fmt: str) -> str:
    """带中文文件名的 Content-Disposition（RFC 5987，另给 ASCII 兜底名）。"""
    ext = EXTENSIONS.get(fmt, "txt")
    quoted = quote(filename, safe="")
    return f"attachment; filename=\"report_{report_id}.{ext}\"; filename*=UTF-8''{quoted}"


def build_export(
    title: str,
    markdown_text: str,
    report_id: int,
    fmt: str,
    report_data=None,
) -> ExportFile:
    """按目标格式产出可下载文件。

    report_data 用于给 html / pdf 补图表（见模块头「图表」一节）；不传或为 None 时
    产物与改动前完全一致，markdown 格式也始终只用正文。
    """
    if fmt == "markdown":
        content = (markdown_text or "").encode("utf-8")
    elif fmt == "html":
        content = render_html_document(title, markdown_text, report_data).encode("utf-8")
    elif fmt == "pdf":
        content = html_to_pdf(render_html_document(title, markdown_text, report_data))
    else:
        raise ValueError(f"不支持的导出格式: {fmt}")
    return ExportFile(
        content=content,
        filename=safe_filename(title, report_id, fmt),
        media_type=MEDIA_TYPES[fmt],
    )
