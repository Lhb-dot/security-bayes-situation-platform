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
"""
from __future__ import annotations

import logging
import os
import queue
import re
import threading
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from markdown_it import MarkdownIt

logger = logging.getLogger(__name__)

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


def markdown_to_html(markdown_text: str) -> str:
    """Markdown 正文 → HTML 片段。"""
    return _MD.render(markdown_text or "")


def render_html_document(title: str, markdown_text: str) -> str:
    """Markdown 正文 → 完整的 HTML 文档（带打印友好样式）。"""
    body = markdown_to_html(markdown_text)
    safe_title = (title or "态势报告").replace("<", "&lt;").replace(">", "&gt;")
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
        result = holder[0] if holder else RuntimeError("PDF 渲染线程未返回结果")
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


def build_export(title: str, markdown_text: str, report_id: int, fmt: str) -> ExportFile:
    """按目标格式产出可下载文件。"""
    if fmt == "markdown":
        content = (markdown_text or "").encode("utf-8")
    elif fmt == "html":
        content = render_html_document(title, markdown_text).encode("utf-8")
    elif fmt == "pdf":
        content = html_to_pdf(render_html_document(title, markdown_text))
    else:
        raise ValueError(f"不支持的导出格式: {fmt}")
    return ExportFile(
        content=content,
        filename=safe_filename(title, report_id, fmt),
        media_type=MEDIA_TYPES[fmt],
    )
