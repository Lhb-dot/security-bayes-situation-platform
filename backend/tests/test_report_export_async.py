"""报告导出异步化测试：渲染线程空闲退出、竞态不变量、导出任务表、产物形状不变。

改动前 tests/ 没有覆盖 PDF 渲染，而空闲退出与投递竞态正是这次要碰的地方。
浏览器用假对象替代（不真的起 Chromium），只验证调度与生命周期。
"""
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services import export_job_service  # noqa: E402
from app.services.report_export import (  # noqa: E402
    _PdfRenderer,
    build_export,
    content_disposition,
    safe_filename,
)
from app.services.report_service import ReportService  # noqa: E402

PDF_BYTES = b"%PDF-1.4 fake-pdf"


class FakeDb:
    def __init__(self):
        self.rollbacks = 0
        self.closed = False

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class FakePage:
    def __init__(self, payload):
        self.payload = payload
        self.closed = False
        self.html = None

    def set_content(self, html, wait_until=None):
        self.html = html

    def pdf(self, **_kwargs):
        return self.payload

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, payload):
        self.payload = payload
        self.closed = 0
        self.pages = []

    def new_page(self):
        page = FakePage(self.payload)
        self.pages.append(page)
        return page

    def close(self):
        self.closed += 1


class FakeChromium:
    def __init__(self, payload=PDF_BYTES, launch_error=None):
        self.payload = payload
        self.launch_error = launch_error
        self.browsers = []

    def launch(self, args=None):
        if self.launch_error is not None:
            raise self.launch_error
        browser = FakeBrowser(self.payload)
        self.browsers.append(browser)
        return browser


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def fake_playwright(chromium):
    return patch("playwright.sync_api.sync_playwright", return_value=FakePlaywright(chromium))


class PdfRendererTests(unittest.TestCase):
    def test_render_returns_pdf_bytes(self):
        chromium = FakeChromium()
        renderer = _PdfRenderer(idle_exit_seconds=0)
        with fake_playwright(chromium):
            self.assertEqual(renderer.render("<html/>"), PDF_BYTES)

        self.assertEqual(len(chromium.browsers), 1)
        self.assertTrue(chromium.browsers[0].pages[0].closed)

    def test_idle_exit_releases_browser_and_next_render_relaunches(self):
        chromium = FakeChromium()
        renderer = _PdfRenderer(idle_exit_seconds=1)
        with fake_playwright(chromium):
            self.assertEqual(renderer.render("<html/>"), PDF_BYTES)
            self.assertTrue(renderer.is_ready())

            deadline = time.monotonic() + 5
            while renderer.is_ready() and time.monotonic() < deadline:
                time.sleep(0.1)

            self.assertFalse(renderer.is_ready(), "空闲超时后渲染线程应已退出")
            self.assertEqual(chromium.browsers[0].closed, 1, "退出时应关闭浏览器")

            self.assertEqual(renderer.render("<html/>"), PDF_BYTES)

        self.assertEqual(len(chromium.browsers), 2, "空闲退出后应重新拉起浏览器")

    def test_render_holds_guard_while_enqueuing(self):
        """投递任务与「确保线程存在」必须同锁，否则空闲退出瞬间的任务会丢。"""
        renderer = _PdfRenderer(idle_exit_seconds=0)
        probe = {}

        def spy():
            # 同线程再拿同一把非可重入锁：render() 若持锁则拿不到
            acquired = renderer._guard.acquire(blocking=False)
            if acquired:
                renderer._guard.release()
            probe["acquired"] = acquired
            raise RuntimeError("stop here")

        renderer._ensure_thread_locked = spy
        with self.assertRaises(RuntimeError):
            renderer.render("<html/>", timeout=1)
        self.assertFalse(probe["acquired"])

    def test_launch_failure_fails_pending_render(self):
        chromium = FakeChromium(launch_error=RuntimeError("no chromium binary"))
        renderer = _PdfRenderer(idle_exit_seconds=0)
        with fake_playwright(chromium):
            with self.assertRaises(RuntimeError) as ctx:
                renderer.render("<html/>", timeout=5)

        self.assertIn("Chromium 不可用", str(ctx.exception))
        self.assertFalse(renderer.is_ready(), "启动失败后线程标记应已清空")

    def test_render_timeout_still_raises(self):
        chromium = FakeChromium()
        renderer = _PdfRenderer(idle_exit_seconds=0)
        with fake_playwright(chromium), patch.object(
            FakePage, "pdf", side_effect=lambda **_kw: time.sleep(2)
        ):
            with self.assertRaises(TimeoutError):
                renderer.render("<html/>", timeout=1)


class ExportJobStoreTests(unittest.TestCase):
    def setUp(self):
        with export_job_service._jobs_lock:
            export_job_service._jobs.clear()
        while not export_job_service._queue.empty():
            export_job_service._queue.get_nowait()

    def tearDown(self):
        with export_job_service._jobs_lock:
            export_job_service._jobs.clear()

    def test_job_view_hides_content(self):
        job_id = export_job_service.create_job(1, 3, "pdf", "测试报告")
        view = export_job_service.get_job(job_id, 1)

        self.assertEqual(view["status"], export_job_service.STATUS_PENDING)
        self.assertFalse(view["ready"])
        self.assertEqual(view["report_id"], 3)
        self.assertNotIn("content", view)

    def test_job_is_not_visible_to_other_users(self):
        job_id = export_job_service.create_job(1, 3, "pdf", "测试报告")
        self.assertIsNone(export_job_service.get_job(job_id, 2))
        self.assertIsNone(export_job_service.get_job_record(job_id, 2))
        self.assertEqual(export_job_service.list_jobs(2), [])

    def test_execute_fills_content_and_marks_done(self):
        job_id = export_job_service.create_job(1, 3, "pdf", "测试报告")
        db = FakeDb()
        exported = SimpleNamespace(
            content=PDF_BYTES, filename="测试报告.pdf", media_type="application/pdf"
        )
        with patch("app.db.SessionLocal", return_value=db), patch.object(
            ReportService, "load_export_source", return_value=("测试报告", "# 正文", None)
        ), patch("app.services.report_export.build_export", return_value=exported):
            export_job_service._execute(job_id)

        view = export_job_service.get_job(job_id, 1)
        self.assertEqual(view["status"], export_job_service.STATUS_DONE)
        self.assertTrue(view["ready"])
        self.assertEqual(view["filename"], "测试报告.pdf")
        self.assertEqual(export_job_service.get_job_record(job_id, 1).content, PDF_BYTES)
        self.assertTrue(db.closed)

    def test_execute_marks_failed_on_error(self):
        job_id = export_job_service.create_job(1, 3, "pdf", "测试报告")
        db = FakeDb()
        with patch("app.db.SessionLocal", return_value=db), patch.object(
            ReportService, "load_export_source", side_effect=RuntimeError("报告不存在")
        ):
            export_job_service._execute(job_id)

        view = export_job_service.get_job(job_id, 1)
        self.assertEqual(view["status"], export_job_service.STATUS_FAILED)
        self.assertEqual(view["error"], "报告不存在")
        self.assertEqual(db.rollbacks, 1)
        self.assertTrue(db.closed)

    def test_finished_job_is_immediately_ready(self):
        exported = SimpleNamespace(
            content="# 正文".encode("utf-8"),
            filename="测试报告.md",
            media_type="text/markdown; charset=utf-8",
        )
        job_id = export_job_service.create_finished_job(1, 3, "markdown", "测试报告", exported)

        view = export_job_service.get_job(job_id, 1)
        self.assertEqual(view["status"], export_job_service.STATUS_DONE)
        self.assertTrue(view["ready"])
        self.assertEqual(export_job_service._queue.qsize(), 0, "同步完成的格式不应入队")

    def test_expired_terminal_job_is_purged_on_next_submit(self):
        stale_id = export_job_service.create_job(1, 3, "pdf", "测试报告")
        stale = export_job_service._jobs[stale_id]
        stale.status = export_job_service.STATUS_DONE
        stale.finished_at = time.time() - 99999

        with patch.dict("os.environ", {"EXPORT_JOB_TTL_SECONDS": "10"}):
            export_job_service.create_job(1, 3, "pdf", "测试报告")

        self.assertIsNone(export_job_service.get_job(stale_id, 1))

    def test_pending_job_is_never_purged(self):
        live_id = export_job_service.create_job(1, 3, "pdf", "测试报告")
        export_job_service._jobs[live_id].created_at = time.time() - 99999

        with patch.dict("os.environ", {"EXPORT_JOB_TTL_SECONDS": "10", "EXPORT_JOB_MAX": "1"}):
            export_job_service.create_job(1, 3, "pdf", "测试报告")

        self.assertIsNotNone(export_job_service.get_job(live_id, 1))

    def test_submit_is_rejected_before_start(self):
        self.assertFalse(export_job_service.is_running())


class SubmitExportTests(unittest.TestCase):
    REPORT = SimpleNamespace(id=3, title="测试报告", content="# 正文", format="markdown")

    def setUp(self):
        self.service = ReportService(FakeDb())
        with export_job_service._jobs_lock:
            export_job_service._jobs.clear()
        while not export_job_service._queue.empty():
            export_job_service._queue.get_nowait()

    def tearDown(self):
        with export_job_service._jobs_lock:
            export_job_service._jobs.clear()

    def test_markdown_completes_without_queueing(self):
        with patch.object(ReportService, "_load_visible", return_value=self.REPORT):
            resp = self.service.submit_export(SimpleNamespace(id=1), 3, "markdown")

        self.assertEqual(resp.code, 0)
        self.assertEqual(resp.message, "导出完成")
        self.assertEqual(export_job_service._queue.qsize(), 0)
        self.assertEqual(
            export_job_service.get_job(resp.data["job_id"], 1)["status"],
            export_job_service.STATUS_DONE,
        )

    def test_pdf_is_queued(self):
        pdf_report = SimpleNamespace(id=3, title="测试报告", content="# 正文", format="pdf")
        with patch.object(ReportService, "_load_visible", return_value=pdf_report), patch(
            "app.services.export_job_service.is_running", return_value=True
        ):
            resp = self.service.submit_export(SimpleNamespace(id=1), 3, "pdf")

        self.assertEqual(resp.code, 0)
        self.assertEqual(resp.message, "导出任务已提交")
        self.assertEqual(export_job_service._queue.qsize(), 1)
        self.assertEqual(
            export_job_service.get_job(resp.data["job_id"], 1)["status"],
            export_job_service.STATUS_PENDING,
        )

    def test_pdf_requires_runner(self):
        pdf_report = SimpleNamespace(id=3, title="测试报告", content="# 正文", format="pdf")
        with patch.object(ReportService, "_load_visible", return_value=pdf_report), patch(
            "app.services.export_job_service.is_running", return_value=False
        ):
            resp = self.service.submit_export(SimpleNamespace(id=1), 3, "pdf")

        self.assertEqual(resp.code, 503)

    def test_file_is_409_until_ready(self):
        job_id = export_job_service.create_job(1, 3, "pdf", "测试报告")
        resp = self.service.read_export_file(
            SimpleNamespace(id=1, status="ENABLED"), job_id
        )
        self.assertEqual(resp.code, 409)

    def test_file_returns_payload_after_ready(self):
        exported = SimpleNamespace(
            content=PDF_BYTES, filename="测试报告.pdf", media_type="application/pdf"
        )
        job_id = export_job_service.create_finished_job(1, 3, "pdf", "测试报告", exported)
        resp = self.service.read_export_file(SimpleNamespace(id=1, status="ENABLED"), job_id)

        self.assertEqual(resp.code, 0)
        self.assertEqual(resp.data["content"], PDF_BYTES)
        self.assertEqual(resp.data["report_id"], 3)
        self.assertEqual(resp.data["format"], "pdf")

    def test_failed_job_reports_its_error(self):
        job_id = export_job_service.create_job(1, 3, "pdf", "测试报告")
        export_job_service._jobs[job_id].status = export_job_service.STATUS_FAILED
        export_job_service._jobs[job_id].error = "Chromium 不可用"
        resp = self.service.read_export_file(SimpleNamespace(id=1, status="ENABLED"), job_id)

        self.assertEqual(resp.code, 500)
        self.assertEqual(resp.message, "Chromium 不可用")

    def test_unknown_job_is_404(self):
        user = SimpleNamespace(id=1, status="ENABLED")
        self.assertEqual(self.service.get_export_job(user, "nope").code, 404)
        self.assertEqual(self.service.read_export_file(user, "nope").code, 404)


class BuildExportContractTests(unittest.TestCase):
    """三种格式的产物形状是「功能零区别」的验收点，锁住。"""

    def test_markdown_is_utf8_of_content(self):
        exported = build_export("标题", "# 正文", 7, "markdown")
        self.assertEqual(exported.content, "# 正文".encode("utf-8"))
        self.assertEqual(exported.filename, "标题.md")
        self.assertEqual(exported.media_type, "text/markdown; charset=utf-8")

    def test_html_wraps_markdown_into_document(self):
        exported = build_export("标题", "# 正文", 7, "html")
        html = exported.content.decode("utf-8")
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("<h1>正文</h1>", html)
        self.assertEqual(exported.filename, "标题.html")

    def test_pdf_renders_the_same_html_document(self):
        with patch(
            "app.services.report_export.html_to_pdf", return_value=PDF_BYTES
        ) as render:
            exported = build_export("标题", "# 正文", 7, "pdf")

        self.assertEqual(exported.content, PDF_BYTES)
        self.assertEqual(exported.media_type, "application/pdf")
        self.assertEqual(exported.filename, "标题.pdf")
        self.assertTrue(render.call_args.args[0].startswith("<!DOCTYPE html>"))

    def test_unsupported_format_still_raises(self):
        with self.assertRaises(ValueError):
            build_export("标题", "正文", 7, "docx")

    def test_safe_filename_truncates_long_titles(self):
        self.assertEqual(safe_filename("a" * 80, 7, "markdown"), f"{'a' * 60}.md")
        self.assertEqual(safe_filename("   ", 7, "pdf"), "report_7.pdf")

    def test_content_disposition_is_unchanged(self):
        self.assertEqual(
            content_disposition("测试报告.pdf", 7, "pdf"),
            "attachment; filename=\"report_7.pdf\"; "
            "filename*=UTF-8''%E6%B5%8B%E8%AF%95%E6%8A%A5%E5%91%8A.pdf",
        )


class ChartExportTests(unittest.TestCase):
    """导出文件里要带上界面上那些图（report_data → SVG）。"""

    #: 模板 CSS 里也有 `.chart-block`，所以断言只认带 class= 的那个
    MARKER = 'class="chart-block"'

    CONTENT = "\n".join(
        [
            "# 月度态势报告",
            "## 三、最终预测结果与概率",
            "- 预测标签分布：风险 7 条、正常 3 条",
            "## 四、不同视图预测结果与概率",
            "- PMWNB（模型 12）：",
            "## 五、特征加权条件概率（Top 10）",
            "- 无特征解释数据",
        ]
    )

    @staticmethod
    def report_data():
        return {
            "report_info": {"title": "月度态势报告", "generated_by": "admin"},
            "prediction": {
                "label_distribution": [
                    {"label": "风险", "count": 7},
                    {"label": "正常", "count": 3},
                ],
                "class_probability": [
                    {"class": "风险", "probability": 0.72},
                    {"class": "正常", "probability": 0.28},
                ],
                "risk_prob_buckets": [
                    {"range": "0-0.2", "count": 0},
                    {"range": "0.6-0.8", "count": 3},
                ],
                "low_confidence_count": 2,
            },
            "model_analysis": [
                {
                    "model_version_id": 12,
                    "algorithm_name": "PMWNB",
                    "algorithm_code": "PMWNB",
                    "has_views": True,
                    "views": [
                        {
                            "name": "流量视图",
                            "distribution": [
                                {"class": "风险", "probability": 0.8},
                                {"class": "正常", "probability": 0.2},
                            ],
                        },
                        {
                            "name": "载荷视图",
                            "distribution": [
                                {"class": "风险", "probability": 0.6},
                                {"class": "正常", "probability": 0.4},
                            ],
                        },
                    ],
                }
            ],
        }

    def html(self, report_data):
        exported = build_export("月度态势报告", self.CONTENT, 7, "html", report_data)
        return exported.content.decode("utf-8")

    def test_html_embeds_charts_inside_the_right_sections(self):
        html = self.html(self.report_data())

        self.assertIn(self.MARKER, html)
        self.assertEqual(html.count("<svg"), html.count("</svg>"))
        self.assertGreater(html.count("<svg"), 1)
        # 三节的图插在「四、」之前，四节的图插在「五、」之前
        self.assertLess(html.index(self.MARKER), html.index("<h2>四、"))
        self.assertLess(html.index("<h2>四、"), html.rindex(self.MARKER))
        self.assertLess(html.rindex(self.MARKER), html.index("<h2>五、"))

    def test_html_without_report_data_stays_text_only(self):
        html = self.html(None)

        self.assertNotIn(self.MARKER, html)
        self.assertNotIn("<svg", html)

    def test_legacy_report_data_without_report_info_is_ignored(self):
        html = self.html({"prediction": {"label_distribution": [{"label": "风险", "count": 1}]}})

        self.assertNotIn("<svg", html)

    def test_markdown_export_never_carries_charts(self):
        exported = build_export("月度态势报告", self.CONTENT, 7, "markdown", self.report_data())

        self.assertEqual(exported.content.decode("utf-8"), self.CONTENT)

    def test_pdf_renders_the_same_html_with_charts(self):
        with patch(
            "app.services.report_export.html_to_pdf", return_value=PDF_BYTES
        ) as render:
            build_export("月度态势报告", self.CONTENT, 7, "pdf", self.report_data())

        self.assertIn(self.MARKER, render.call_args.args[0])

    def test_chart_labels_are_xml_escaped(self):
        data = self.report_data()
        data["prediction"]["label_distribution"] = [
            {"label": "<script>x</script>", "count": 4}
        ]
        html = self.html(data)

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_all_zero_data_skips_the_charts(self):
        data = self.report_data()
        data["prediction"]["label_distribution"] = [{"label": "风险", "count": 0}]
        data["prediction"]["class_probability"] = [{"class": "风险", "probability": 0}]
        data["prediction"]["risk_prob_buckets"] = [{"range": "0-0.2", "count": 0}]
        data["model_analysis"] = []

        self.assertNotIn("<svg", self.html(data))

    def test_single_view_model_has_no_grouped_chart(self):
        data = self.report_data()
        data["model_analysis"][0]["views"] = data["model_analysis"][0]["views"][:1]
        html = self.html(data)

        self.assertNotIn("多视图概率对比", html)

    def test_chart_anchor_falls_back_to_document_end(self):
        """正文结构变了也不能把图整块丢掉。"""
        exported = build_export("月度态势报告", "# 只有标题", 7, "html", self.report_data())
        html = exported.content.decode("utf-8")

        self.assertIn(self.MARKER, html)
        self.assertLess(html.index("</h1>"), html.index(self.MARKER))


class RouteWiringTests(unittest.TestCase):
    def test_async_routes_registered_alongside_the_old_export_route(self):
        from app.main import app

        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/reports/{report_id}/export/jobs", paths)
        self.assertIn("/api/v1/reports/export/jobs", paths)
        self.assertIn("/api/v1/reports/export/jobs/{job_id}", paths)
        self.assertIn("/api/v1/reports/export/jobs/{job_id}/file", paths)
        self.assertIn("/api/v1/reports/{report_id}/export", paths)


if __name__ == "__main__":
    unittest.main()
